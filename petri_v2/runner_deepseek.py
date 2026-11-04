"""DeepSeek runner for the open-weight judge `deepseekv4pro` (deepseek-v4-pro = DeepSeek-V4-Pro-0813).

DeepSeek has no Batch API. Its off-peak rate is half the peak rate, so this runner makes
synchronous calls ONLY in the off-peak window, which is what the spend gate prices
(prices.yaml `batch` = off-peak price for this model).

API shapes checked 2026-10-10:
  https://api-docs.deepseek.com/quick_start/pricing
    "Off-peak rates are half of the peak rates. Peak hours are 01:00 - 04:00 and 06:00 - 10:00 UTC,
    Monday through Friday, excluding Chinese public holidays. All other hours are off-peak."
    deepseek-v4-pro: input (cache miss) $0.66 off-peak / $1.32 peak; output $1.98 / $3.96 per MTok.
  https://api-docs.deepseek.com/guides/thinking_mode
    POST https://api.deepseek.com/chat/completions (OpenAI format), Authorization: Bearer key;
    {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}; "Thinking mode does not support
    the temperature, presence_penalty, or frequency_penalty parameters"; the chain of thought is
    returned in `message.reasoning_content`, the answer in `message.content`.

Window rule (conservative): a request is started only if the time from now to the next peak start
is at least `margin_s` (default 15 min, which exceeds the 10-min request timeout, so no request can
run into a peak window). Chinese public holidays are treated as ordinary weekdays (they are
off-peak, so this only ever loses cheap hours, never pays peak prices).

Resumable and keyed exactly like the batch runners: results go to <out>/deepseek/results.jsonl,
done requests are skipped, provider failures are retried at most 3 times per request, parse
failures are not retried. HTTP 401/402/403 (bad key, no balance) abort the run instead of burning
the retry budget.

Usage:
  python -m petri_v2.runner_deepseek plan --start 120 --n 260
  python -m petri_v2.runner_deepseek run  --start 120 --n 260 --budget-usd 10 --confirm-spend   # needs DEEPSEEK_API_KEY
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import sys
import threading
import time

from . import batch, corpus, estimate, http, jobs as jobs_mod, judges, prompts
from .runner_kimi import normalize_chat

API = "https://api.deepseek.com"
PEAK_UTC = ((1, 4), (6, 10))  # [start, end) hours, Monday-Friday
REQUEST_TIMEOUT_S = 600
MARGIN_S = 15 * 60
ABORT_STATUS = (401, 402, 403)


def next_peak_start(t):
    """The first peak-window start at or after t (UTC datetime), or t itself if t is inside a peak window."""
    day = t.replace(hour=0, minute=0, second=0, microsecond=0)
    for d in range(8):
        base = day + dt.timedelta(days=d)
        if base.weekday() >= 5:
            continue
        for a, b in PEAK_UTC:
            start, end = base.replace(hour=a), base.replace(hour=b)
            if start <= t < end:
                return t
            if start > t:
                return start
    raise AssertionError("unreachable")


def peak_end(t):
    """End of the peak window containing t (t must be inside one)."""
    for a, b in PEAK_UTC:
        if a <= t.hour < b:
            return t.replace(hour=b, minute=0, second=0, microsecond=0)
    return t


def can_start(t, margin_s=MARGIN_S):
    return (next_peak_start(t) - t).total_seconds() >= margin_s


def seconds_until_allowed(t, margin_s=MARGIN_S):
    """0 if a request may start now; else seconds until the current/upcoming peak window ends."""
    if can_start(t, margin_s):
        return 0.0
    nps = next_peak_start(t)
    return max((peak_end(nps) - t).total_seconds(), 1.0)


class DeepSeekRunner(batch.BatchRunner):
    provider = "deepseek"
    key_env = "DEEPSEEK_API_KEY"

    def __init__(self, out_dir, transport=None, sleep=time.sleep, log=print, clock=None, concurrency=8,
                 margin_s=MARGIN_S, wait_for_offpeak=True):
        super().__init__(out_dir, transport or http.UrllibTransport(timeout=REQUEST_TIMEOUT_S), sleep, log)
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.concurrency = concurrency
        self.margin_s = margin_s
        self.wait_for_offpeak = wait_for_offpeak
        self._lock = threading.Lock()
        if margin_s < REQUEST_TIMEOUT_S:
            raise ValueError("margin must exceed the request timeout so no request runs into a peak window")

    # no batches: nothing is ever pending between runs
    def pending_ids(self):
        return set()

    def poll(self):
        return {}

    def collect(self):
        return 0

    def normalize(self, body):
        return normalize_chat(body)

    def _call(self, job, key):
        body = jobs_mod.batch_line(job)["body"]
        try:
            r = self.transport.request("POST", f"{API}/chat/completions",
                                       {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                                       json.dumps(body).encode())
            http.check(r)
            return "responded", r.json(), None
        except http.HTTPError as e:
            if e.status in ABORT_STATUS:
                raise
            return "errored", None, {"status": e.status, "message": e.body}
        except Exception as e:  # timeout, connection reset: retried on the next pass
            return "errored", None, {"type": type(e).__name__, "message": http.redact(str(e))[:300]}

    def submit(self, job_list, budget_usd=None, confirm_spend=False, prices=None):
        """Run every outstanding job synchronously, off-peak only. Returns the custom_ids attempted."""
        for label in sorted({j["judge"] for j in job_list}):
            j = judges.require_served(label)
            if j.provider != self.provider:
                raise SystemExit(f"judge {label} belongs to {j.provider}, not {self.provider}")
        todo = self.todo(job_list)
        if not todo:
            self.log(f"[{self.provider}] nothing to run ({len(job_list)} jobs already done)")
            return []
        self.gate(todo, budget_usd, confirm_spend, prices)
        key = self.key()
        attempted = []
        with cf.ThreadPoolExecutor(self.concurrency) as pool:
            while todo:
                wait = seconds_until_allowed(self.clock(), self.margin_s)
                if wait:
                    if not self.wait_for_offpeak:
                        self.log(f"[{self.provider}] peak window: stopping; {len(todo)} requests left (re-run off-peak)")
                        break
                    self.log(f"[{self.provider}] peak window: waiting {wait / 60:.0f} min")
                    self.sleep(wait)
                    continue
                wave = todo[: self.concurrency]
                futs = {pool.submit(self._call, j, key): j for j in wave}
                recs, abort = [], None
                for f in cf.as_completed(futs):
                    j = futs[f]
                    try:
                        status, resp, err = f.result()
                    except http.HTTPError as e:  # 401/402/403: record nothing for this job, stop after the wave
                        abort = e
                        continue
                    recs.append(self.record(j["custom_id"], status, resp, err, "sync", j["dims"]))
                with self._lock:  # paid responses are saved before any abort, so they are never re-bought
                    batch.append_jsonl(self.results_path, recs)
                if abort is not None:
                    raise SystemExit(f"[{self.provider}] aborting: {abort}")
                attempted += [j["custom_id"] for j in wave]
                n_ok = sum(r["status"] == "responded" for r in recs)
                self.log(f"[{self.provider}] wave of {len(wave)}: {n_ok} responded")
                todo = self.todo(job_list)
        return attempted

    def run(self, job_list, budget_usd=None, confirm_spend=False, interval_s=None, max_wait_s=None):
        return self.submit(job_list, budget_usd, confirm_spend)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["plan", "run", "status"])
    ap.add_argument("--judges", default="deepseekv4pro")
    ap.add_argument("--n", type=int, default=corpus.N_ANALYSIS)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=len(judges.REPEATS))
    ap.add_argument("--dims", choices=["all", "cut"], default="all")
    ap.add_argument("--view", choices=["petri", "target_messages"], default="petri")
    ap.add_argument("--data-dir", default=corpus.DEFAULT_DATA)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--budget-usd", type=float, default=None)
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--no-wait", action="store_true", help="stop at a peak window instead of sleeping through it")
    a = ap.parse_args(argv)
    r = DeepSeekRunner(a.out, concurrency=a.concurrency, wait_for_offpeak=not a.no_wait)
    if a.command == "status":
        recs = batch.read_jsonl(r.results_path)
        print(json.dumps({"records": len(recs), "responded": len(r.done_ids()), "given_up": len(r.given_up_ids()),
                          "can_start_now": can_start(r.clock())}, indent=1))
        return
    dims = prompts.CUT_DIMS if a.dims == "cut" else prompts.STUDY_DIMS
    inputs = jobs_mod.build_inputs(a.n, dims, a.view, a.data_dir, a.start)
    job_list = jobs_mod.build_jobs(inputs, [x for x in a.judges.split(",") if x], list(range(1, a.repeats + 1)))
    if a.command == "plan":
        todo = r.todo(job_list)
        est = estimate.estimate(todo, estimate.load_prices()) if todo else None
        print(json.dumps({"jobs": len(job_list), "todo": len(todo), "offpeak_usd_high": est and est["total_usd"]["batch_high"],
                          "can_start_now": can_start(r.clock())}, indent=1))
        return
    r.run(job_list, a.budget_usd, a.confirm_spend)


if __name__ == "__main__":
    sys.exit(main())
