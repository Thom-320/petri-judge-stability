"""Provider-independent batch runner: resumable submission, polling, collection and the spend gate.

State lives in `<out>/<provider>/`:
  batches.jsonl  append-only batch events; the last line per batch_id is its current state
  results.jsonl  one record per collected request, keyed by custom_id = transcript x judge x repeat

Resumability: a job is skipped when results.jsonl already holds a `responded` record for it, or when
it belongs to a batch that is still pending. Errored, expired or canceled items are resubmitted on
the next `submit`.

Spend gate (SPEC-v2 item 1): `submit` refuses unless BOTH `--confirm-spend` is given AND
`--budget-usd` is given and the dry-run estimate for exactly the jobs about to be submitted
(batch prices, high case of 10,000 output tokens per request) does not exceed it. The hard-cap case
(32,000 output tokens) is printed alongside.

Keys: read from the provider's env var only when a request is made. They are never printed,
logged or written; error text is passed through `http.redact`.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

from . import corpus, estimate, http, jobs as jobs_mod, judges, parse, prompts


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def append_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


class SpendRefused(SystemExit):
    pass


class BatchRunner:
    provider = None
    key_env = None
    max_requests = None
    max_bytes = None

    def __init__(self, out_dir, transport=None, sleep=time.sleep, log=print):
        self.dir = os.path.join(out_dir, self.provider)
        self.transport = transport or http.UrllibTransport()
        self.sleep = sleep
        self.log = log

    # ------------------------------------------------------------ provider hooks
    def submit_batch(self, lines, label):
        raise NotImplementedError

    def get_status(self, batch_id):
        """Return (state, meta) with state in running | ended | failed | expired | cancelled."""
        raise NotImplementedError

    def fetch_results(self, batch_id, meta):
        """Yield (custom_id, status, response_or_None, error_or_None); status responded|errored|expired|canceled."""
        raise NotImplementedError

    def normalize(self, response):
        """Return (text, finish_reason, usage_dict)."""
        raise NotImplementedError

    # ------------------------------------------------------------ helpers
    def key(self):
        k = os.environ.get(self.key_env)
        if not k:
            raise SystemExit(f"{self.key_env} is not set; refusing to contact the {self.provider} API")
        return k

    @property
    def batches_path(self):
        return os.path.join(self.dir, "batches.jsonl")

    @property
    def results_path(self):
        return os.path.join(self.dir, "results.jsonl")

    def batches(self):
        state = {}
        for row in read_jsonl(self.batches_path):
            state.setdefault(row["batch_id"], {}).update(row)
        return state

    def done_ids(self):
        return {r["custom_id"] for r in read_jsonl(self.results_path) if r.get("status") == "responded"}

    def pending_ids(self):
        ids = set()
        for b in self.batches().values():
            if not b.get("collected") and b.get("state") not in ("failed", "cancelled", "expired_no_results"):
                ids.update(b.get("custom_ids", []))
        return ids

    MAX_ATTEMPTS = 3  # provider-side failures (errored / expired / missing) per request; parse failures are not retried

    def given_up_ids(self):
        fails = {}
        for r in read_jsonl(self.results_path):
            if r.get("status") != "responded":
                fails[r["custom_id"]] = fails.get(r["custom_id"], 0) + 1
        return {c for c, n in fails.items() if n >= self.MAX_ATTEMPTS}

    def todo(self, job_list):
        skip = self.done_ids() | self.pending_ids() | self.given_up_ids()
        return [j for j in job_list if j["custom_id"] not in skip]

    def chunks(self, job_list):
        cur, size = [], 0
        for j in job_list:
            b = jobs_mod.batch_line_bytes(j)
            if cur and (len(cur) >= self.max_requests or size + b > self.max_bytes):
                yield cur
                cur, size = [], 0
            cur.append(j)
            size += b
        if cur:
            yield cur

    # ------------------------------------------------------------ commands
    def gate(self, job_list, budget_usd, confirm_spend, prices=None):
        prices = prices or estimate.load_prices()
        est = estimate.estimate(job_list, prices, count_endpoint=(self.provider == "anthropic"),
                                transport=self.transport)
        high, cap = est["total_usd"]["batch_high"], est["total_usd"]["batch_cap"]
        self.log(f"[{self.provider}] dry-run estimate for {len(job_list)} requests: batch high ${high:,.2f} "
                 f"(10k output tokens), batch low ${est['total_usd']['batch_low']:,.2f}, "
                 f"hard cap ${cap:,.2f} (32k output tokens)")
        if not confirm_spend:
            raise SpendRefused("refusing to submit: --confirm-spend not given")
        if budget_usd is None:
            raise SpendRefused("refusing to submit: --budget-usd not given")
        if high > budget_usd:
            raise SpendRefused(f"refusing to submit: estimate ${high:,.2f} exceeds --budget-usd ${budget_usd:,.2f}")
        return est

    def submit(self, job_list, budget_usd=None, confirm_spend=False, prices=None):
        for label in sorted({j["judge"] for j in job_list}):
            j = judges.require_served(label)
            if j.provider != self.provider:
                raise SystemExit(f"judge {label} belongs to {j.provider}, not {self.provider}")
        todo = self.todo(job_list)
        if not todo:
            self.log(f"[{self.provider}] nothing to submit ({len(job_list)} jobs already done or pending)")
            return []
        est = self.gate(todo, budget_usd, confirm_spend, prices)
        self.key()
        submitted = []
        for label in sorted({j["judge"] for j in todo}):
            for chunk in self.chunks([j for j in todo if j["judge"] == label]):
                lines = [jobs_mod.batch_line(j) for j in chunk]
                batch_id = self.submit_batch(lines, label)
                row = {"batch_id": batch_id, "provider": self.provider, "judge": label,
                       "model": judges.get(label).model, "state": "running", "submitted_at": now(),
                       "custom_ids": [j["custom_id"] for j in chunk], "dims": chunk[0]["dims"],
                       "view": chunk[0]["view"], "n_requests": len(chunk),
                       "estimate_batch_high_usd_total_submission": est["total_usd"]["batch_high"]}
                append_jsonl(self.batches_path, [row])
                submitted.append(batch_id)
                self.log(f"[{self.provider}] submitted batch {batch_id}: {len(chunk)} requests ({label})")
        return submitted

    def poll(self):
        out = {}
        for bid, b in self.batches().items():
            if b.get("collected") or b.get("state") in ("ended", "failed", "cancelled", "expired_no_results"):
                out[bid] = b.get("state")
                continue
            state, meta = self.get_status(bid)
            append_jsonl(self.batches_path, [{"batch_id": bid, "state": state, "meta": meta, "polled_at": now()}])
            out[bid] = state
            self.log(f"[{self.provider}] batch {bid}: {state}")
        return out

    def collect(self):
        n = 0
        for bid, b in self.batches().items():
            if b.get("collected") or b.get("state") != "ended":
                continue
            dims = b.get("dims") or prompts.STUDY_DIMS
            recs = []
            seen = set()
            for cid, status, resp, err in self.fetch_results(bid, b.get("meta") or {}):
                seen.add(cid)
                recs.append(self.record(cid, status, resp, err, bid, dims))
            for cid in b.get("custom_ids", []):
                if cid not in seen:  # no line for this request: record it so it is retried
                    recs.append(self.record(cid, "missing_from_results", None, "no result line", bid, dims))
            append_jsonl(self.results_path, recs)
            append_jsonl(self.batches_path, [{"batch_id": bid, "collected": True, "collected_at": now(),
                                              "n_results": len(recs)}])
            n += len(recs)
            self.log(f"[{self.provider}] collected {len(recs)} results from {bid}")
        return n

    def record(self, cid, status, resp, err, batch_id, dims):
        tid, label, rep = jobs_mod.split_custom_id(cid)
        rec = {"job": f"{tid}|{label}|{rep}", "custom_id": cid, "transcript_id": tid, "judge": label,
               "model": judges.get(label).model, "repeat": rep, "provider": self.provider,
               "batch_id": batch_id, "status": status, "collected_at": now()}
        text = None
        if status == "responded" and resp is not None:
            text, finish, usage = self.normalize(resp)
            rec.update({"finish_reason": finish, "usage": usage, "content": text})
        else:
            rec["error"] = http.redact(json.dumps(err) if not isinstance(err, str) else err)
        rec["parse"] = parse.parse_response(text, dims, prompts.MAX_SCORE, rec.get("finish_reason"))
        return rec

    def run(self, job_list, budget_usd=None, confirm_spend=False, interval_s=300, max_wait_s=26 * 3600):
        self.submit(job_list, budget_usd, confirm_spend)
        waited = 0
        while True:
            states = self.poll()
            self.collect()
            if not any(s == "running" for s in states.values()):
                break
            if waited >= max_wait_s:
                self.log(f"[{self.provider}] stopped waiting after {waited}s; re-run `poll` and `collect` later")
                break
            self.sleep(interval_s)
            waited += interval_s


# ---------------------------------------------------------------- CLI shared by the three runners
def cli(runner_cls, default_judges, argv=None):
    ap = argparse.ArgumentParser(description=f"{runner_cls.provider} batch runner (see petri_v2/batch.py)")
    ap.add_argument("command", choices=["plan", "submit", "poll", "collect", "run", "status"])
    ap.add_argument("--judges", default=",".join(default_judges))
    ap.add_argument("--n", type=int, default=corpus.N_ANALYSIS, help="analysis-order positions up to n")
    ap.add_argument("--start", type=int, default=0, help="skip the first `start` positions (e.g. 120)")
    ap.add_argument("--repeats", type=int, default=len(judges.REPEATS))
    ap.add_argument("--dims", choices=["all", "cut"], default="all")
    ap.add_argument("--view", choices=["petri", "target_messages"], default="petri")
    ap.add_argument("--data-dir", default=corpus.DEFAULT_DATA)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--budget-usd", type=float, default=None)
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--interval-s", type=int, default=300)
    a = ap.parse_args(argv)
    r = runner_cls(a.out)
    if a.command in ("poll", "collect", "status"):
        if a.command == "status":
            for bid, b in r.batches().items():
                print(json.dumps({k: b.get(k) for k in ("batch_id", "judge", "state", "n_requests", "collected")}))
            return
        r.poll() if a.command == "poll" else r.collect()
        return
    labels = [x for x in a.judges.split(",") if x]
    dims = prompts.CUT_DIMS if a.dims == "cut" else prompts.STUDY_DIMS
    inputs = jobs_mod.build_inputs(a.n, dims, a.view, a.data_dir, a.start)
    job_list = jobs_mod.build_jobs(inputs, labels, list(range(1, a.repeats + 1)))
    if a.command == "plan":
        todo = r.todo(job_list)
        est = estimate.estimate(todo, estimate.load_prices()) if todo else None
        print(json.dumps({"jobs": len(job_list), "todo": len(todo),
                          "batch_high_usd": est and est["total_usd"]["batch_high"]}, indent=1))
        return
    if a.command == "submit":
        r.submit(job_list, a.budget_usd, a.confirm_spend)
    else:
        r.run(job_list, a.budget_usd, a.confirm_spend, a.interval_s)


if __name__ == "__main__":
    sys.exit("use petri_v2.runner_anthropic / runner_gemini / runner_openai")
