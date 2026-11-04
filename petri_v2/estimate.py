"""Dry-run cost estimator: builds every request, counts input tokens, prices them from prices.yaml.

Usage:
  python -m petri_v2.estimate                       # default design: 260 x DEFAULT_PANEL x 2 repeats, 4 dims
  python -m petri_v2.estimate --n 120 --dims cut    # 120 transcripts, 2-dimension cut
  python -m petri_v2.estimate --scenarios --json out.json   # the standard scenario table
  python -m petri_v2.estimate --view-report         # how many transcripts have target rollbacks
  python -m petri_v2.estimate --designs --json out.json     # J = 3 / 6 / 8 design options (Session 2)

Input tokens: with ANTHROPIC_API_KEY set and --count-endpoint, Anthropic judges are counted with
POST /v1/messages/count_tokens (free, rate-limited; docs: platform.claude.com/docs/en/build-with-claude/token-counting,
checked 2026-10-09). Otherwise every judge uses a tokenizer approximation: tiktoken `o200k_base`
(OpenAI's GPT-5-family encoding) on the exact system and user strings, plus a fixed per-message
overhead. For Claude and Gemini this is an approximation of a different tokenizer and is labelled as such.
Output tokens are not knowable before the run; the estimate uses the spec's low case (4,000, measured
in the cheap-judge pilot) and high case (10,000 = Petri's reasoning budget), and prints the hard cap
(max_tokens = 32,000) as the worst case.
"""
import argparse
import json
import os
import sys

import yaml

from . import corpus, http, jobs as jobs_mod, judges, prompts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICES_PATH = os.path.join(ROOT, "prices.yaml")
OUT_LOW, OUT_HIGH = 4000, 10000
MESSAGE_OVERHEAD = 12  # approx. tokens for role/format wrappers of a system + one user message
_ENC = None


def load_prices(path=PRICES_PATH):
    return yaml.safe_load(open(path, encoding="utf-8"))


TOKENIZER_LABEL = "approximation: tiktoken o200k_base"


def approx_tokens(text):
    """o200k_base token count; falls back to chars/4 (labelled) if the encoding cannot be loaded offline."""
    global _ENC, TOKENIZER_LABEL
    if _ENC is None:
        try:
            import tiktoken
            _ENC = tiktoken.get_encoding("o200k_base").encode
        except Exception:  # tiktoken missing, or its BPE file not cached and no network
            _ENC = lambda t: range((len(t) + 3) // 4)  # noqa: E731
            TOKENIZER_LABEL = "approximation: characters / 4 (tiktoken o200k_base unavailable)"
    if hasattr(_ENC, "__self__"):
        return len(_ENC(text, disallowed_special=()))
    return len(_ENC(text))


def anthropic_count_tokens(job, transport=None):
    """Exact count via the Anthropic endpoint. Requires ANTHROPIC_API_KEY (never printed)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    transport = transport or http.UrllibTransport(timeout=120)
    p = jobs_mod.anthropic_params(job)
    body = {k: p[k] for k in ("model", "system", "messages", "thinking")}
    r = http.check(transport.request(
        "POST", "https://api.anthropic.com/v1/messages/count_tokens",
        {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json.dumps(body).encode()))
    return int(r.json()["input_tokens"])


def price_row(prices, model, input_tokens_per_request):
    row = prices["models"][model]
    tiers = row.get("tiers")
    if tiers:  # e.g. Gemini: price depends on prompt length
        for t in tiers:
            if input_tokens_per_request <= t["max_prompt_tokens"]:
                return t
        return tiers[-1]
    return row


def estimate(job_list, prices, count_endpoint=False, transport=None):
    """Return per-judge token and cost totals for a list of jobs."""
    cache, method = {}, {}
    per = {}
    for job in job_list:
        j = judges.get(job["judge"])
        exact = count_endpoint and j.provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY")
        ck = (job["input_sha256"], j.model if exact else "approx")
        if ck not in cache:
            if exact:
                cache[ck] = anthropic_count_tokens(job, transport)
            else:
                cache[ck] = approx_tokens(job["system"]) + approx_tokens(job["user"]) + MESSAGE_OVERHEAD
        tin = cache[ck]
        mult = prices["models"][j.model].get("input_token_multiplier", 1.0)
        if not exact and mult != 1.0:  # e.g. Claude 4.7+ tokenizer (~30% more tokens than earlier Claude)
            tin = int(round(tin * mult))
            method[job["judge"]] = f"{TOKENIZER_LABEL} x {mult} (provider tokenizer note)"
        method.setdefault(job["judge"], "anthropic count_tokens endpoint" if exact else TOKENIZER_LABEL)
        a = per.setdefault(job["judge"], {"model": j.model, "provider": j.provider, "requests": 0,
                                          "input_tokens": 0, "max_input_tokens_per_request": 0,
                                          "usd": {}})
        a["requests"] += 1
        a["input_tokens"] += tin
        a["max_input_tokens_per_request"] = max(a["max_input_tokens_per_request"], tin)
        pr = price_row(prices, j.model, tin)
        for case, out in (("low", OUT_LOW), ("high", OUT_HIGH), ("cap", judges.MAX_TOKENS)):
            for mode in ("standard", "batch"):
                usd = (tin * pr[mode]["input"] + out * pr[mode]["output"]) / 1e6
                a["usd"][f"{mode}_{case}"] = a["usd"].get(f"{mode}_{case}", 0.0) + usd
    for label, a in per.items():
        a["token_method"] = method[label]
        a["output_tokens_low"] = a["requests"] * OUT_LOW
        a["output_tokens_high"] = a["requests"] * OUT_HIGH
        a["mean_input_tokens"] = a["input_tokens"] / a["requests"]
    total = {k: sum(a["usd"][k] for a in per.values()) for k in next(iter(per.values()))["usd"]} if per else {}
    return {"per_judge": per, "total_usd": total, "requests": len(job_list),
            "prices_checked": prices.get("checked")}


SCENARIOS = [
    ("full_260_4dims", 0, 260, "all"),
    ("pilot_120_4dims", 0, 120, "all"),
    ("untouched_140_4dims", 120, 260, "all"),
    ("cut_260_2dims", 0, 260, "cut"),
    ("cut_120_2dims", 0, 120, "cut"),
]


# Design options (pre-registration §3, Session 2). Each leg: (panel, start, stop, repeats) over the
# 260-transcript analysis order; positions start+1..stop. The Petri panel always runs all 260
# (confirmatory 121-260 first, Opus leg first); extra judges run the confirmatory 140 only.
_CONF, _PILOT = (120, 260), (0, 120)
_NEW6 = [j for j in judges.PANEL_J6 if j not in judges.DEFAULT_PANEL]
_NEW8 = [j for j in judges.PANEL_J8 if j not in judges.DEFAULT_PANEL]
_A = [(judges.DEFAULT_PANEL, *_CONF, [1, 2]), (judges.DEFAULT_PANEL, *_PILOT, [1, 2])]
DESIGNS = {
    "A_J3": {"label": "J = 3: Petri panel only (current design)", "legs": _A},
    "B_J6": {"label": "J = 6: + Gemini 3.8 Flash, DeepSeek V4 Pro, Kimi K2.6 on the confirmatory 140, R = 2",
             "legs": _A + [(_NEW6, *_CONF, [1, 2])]},
    "C_J8": {"label": "J = 8: + Sonnet 5.5, Gemini 3.8 Flash, GPT-5.4 mini, DeepSeek V4 Pro, Kimi K2.6 on the confirmatory 140, R = 2",
             "legs": _A + [(_NEW8, *_CONF, [1, 2])]},
    "C_J8_lite": {"label": "J = 8, cheaper: the 5 extra judges with R = 2 on positions 121-190 and R = 1 on 191-260",
                  "legs": _A + [(_NEW8, 120, 190, [1, 2]), (_NEW8, 190, 260, [1])]},
    "addon_gemma4": {"label": "Optional add-on: Gemma 4 31B (DeepInfra batch, derived price) on the confirmatory 140, R = 2",
                     "legs": [(["gemma4"], *_CONF, [1, 2])]},
    "addon_qwen38max": {"label": "Alternate open-weight judge: Qwen3.8 Max (Fireworks batch, derived price), confirmatory 140, R = 2",
                        "legs": [(["qwen38max"], *_CONF, [1, 2])]},
}


def run_designs(prices, view="petri", count_endpoint=False, data_dir=corpus.DEFAULT_DATA, designs=DESIGNS):
    inputs = jobs_mod.build_inputs(260, prompts.STUDY_DIMS, view, data_dir)
    out = {}
    for name, dsg in designs.items():
        job_list = []
        for panel, start, stop, reps in dsg["legs"]:
            for p in panel:
                judges.require_served(p)
            job_list += jobs_mod.build_jobs(inputs[start:stop], panel, reps)
        r = estimate(job_list, prices, count_endpoint)
        r.update({"label": dsg["label"], "legs": [{"panel": list(p), "positions": [a + 1, b], "repeats": list(rp)}
                                                   for p, a, b, rp in dsg["legs"]]})
        for lab, a in r["per_judge"].items():
            jj = judges.get(lab)
            a.update({"developer": jj.developer, "tier": jj.tier, "runner_in_repo": jj.runner,
                      "price_derived": bool(prices["models"][jj.model].get("derived", False)),
                      "batch_mode": prices["models"][jj.model].get("batch_mode", "Batch API")})
        out[name] = r
    return out


def fmt_designs(res):
    lines = ["| Design | Judges | Requests | Batch low (4k out) | Batch high (10k out) | Batch cap (32k out) | Std high |",
             "|---|---|---|---|---|---|---|"]
    for name, r in res.items():
        t = r["total_usd"]
        lines.append(f"| {name} | {len(r['per_judge'])} | {r['requests']:,} | ${t['batch_low']:,.2f} | ${t['batch_high']:,.2f} | "
                     f"${t['batch_cap']:,.2f} | ${t['standard_high']:,.2f} |")
    lines += ["", "| Judge | Developer | Tier | Requests (in largest design) | Batch low | Batch high | Batch cap | Price mode | Runner in repo |",
              "|---|---|---|---|---|---|---|---|---|"]
    seen = {}
    for r in res.values():
        for lab, a in r["per_judge"].items():
            if lab not in seen or a["requests"] > seen[lab]["requests"]:
                seen[lab] = a
    for lab, a in seen.items():
        u = a["usd"]
        mode = a["batch_mode"] + (" (derived)" if a["price_derived"] else "")
        lines.append(f"| {lab} ({a['model']}) | {a['developer']} | {a['tier']} | {a['requests']:,} | ${u['batch_low']:,.2f} | "
                     f"${u['batch_high']:,.2f} | ${u['batch_cap']:,.2f} | {mode} | {'yes' if a['runner_in_repo'] else 'no'} |")
    return "\n".join(lines)


def dims_of(name):
    return prompts.CUT_DIMS if name == "cut" else prompts.STUDY_DIMS


def run_scenarios(panel, repeats, prices, view="petri", count_endpoint=False, data_dir=corpus.DEFAULT_DATA):
    out = {}
    cache = {}
    for name, start, n, dims in SCENARIOS:
        key = (dims, view)
        if key not in cache:
            cache[key] = jobs_mod.build_inputs(260, dims_of(dims), view, data_dir)
        inputs = cache[key][start:n]
        out[name] = estimate(jobs_mod.build_jobs(inputs, panel, repeats), prices, count_endpoint)
        out[name].update({"n_transcripts": n - start, "dims": dims_of(dims), "view": view})
    return out


def fmt_table(res, title):
    lines = [f"## {title}", "",
             f"Requests: {res['requests']}. Prices checked {res['prices_checked']}.", "",
             "| Judge | Model | Requests | Input tokens | Mean in/request | Token method | Output low / high | "
             "Std low | Std high | Batch low | Batch high | Batch cap (32k out) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for label, a in res["per_judge"].items():
        u = a["usd"]
        lines.append(f"| {label} | {a['model']} | {a['requests']:,} | {a['input_tokens']:,} | "
                     f"{a['mean_input_tokens']:,.0f} | {a['token_method']} | "
                     f"{a['output_tokens_low']:,} / {a['output_tokens_high']:,} | "
                     f"${u['standard_low']:,.2f} | ${u['standard_high']:,.2f} | ${u['batch_low']:,.2f} | "
                     f"${u['batch_high']:,.2f} | ${u['batch_cap']:,.2f} |")
    t = res["total_usd"]
    lines.append(f"| **total** | | {res['requests']:,} | | | | | ${t['standard_low']:,.2f} | "
                 f"${t['standard_high']:,.2f} | ${t['batch_low']:,.2f} | ${t['batch_high']:,.2f} | "
                 f"${t['batch_cap']:,.2f} |")
    return "\n".join(lines)


def view_report(data_dir=corpus.DEFAULT_DATA):
    from . import view as view_mod
    import glob
    rows = corpus.analysis_order(data_dir)
    pos = {r["transcript_key"]: r["pos"] for r in rows}
    files = sorted(glob.glob(os.path.join(data_dir, "transcripts", "*.json")))
    rb = []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        if view_mod.n_target_branches(d) > 1:
            rb.append(os.path.basename(f))
    in_sel = [k for k in rb if k in pos]
    return {"corpus_files": len(files), "with_target_rollbacks": len(rb),
            "analysis_260_with_rollbacks": len(in_sel),
            "pilot_120_with_rollbacks": sum(1 for k in in_sel if pos[k] <= corpus.N_PILOT),
            "untouched_140_with_rollbacks": sum(1 for k in in_sel if pos[k] > corpus.N_PILOT)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", default=",".join(judges.DEFAULT_PANEL))
    ap.add_argument("--repeats", type=int, default=len(judges.REPEATS))
    ap.add_argument("--n", type=int, default=260)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--dims", choices=["all", "cut"], default="all")
    ap.add_argument("--view", choices=["petri", "target_messages"], default="petri")
    ap.add_argument("--data-dir", default=corpus.DEFAULT_DATA)
    ap.add_argument("--count-endpoint", action="store_true", help="use Anthropic count_tokens if a key is set")
    ap.add_argument("--scenarios", action="store_true")
    ap.add_argument("--view-report", action="store_true")
    ap.add_argument("--designs", action="store_true", help="J = 3 / 6 / 8 design options (Session 2)")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if a.view_report:
        print(json.dumps(view_report(a.data_dir), indent=1))
        return
    if a.designs:
        res = run_designs(load_prices(), a.view, a.count_endpoint, a.data_dir)
        print(fmt_designs(res))
        if a.json:
            json.dump(res, open(a.json, "w", encoding="utf-8"), indent=1)
        return
    panel = [p for p in a.panel.split(",") if p]
    for p in panel:
        judges.require_served(p)
    prices = load_prices()
    reps = list(range(1, a.repeats + 1))
    if a.scenarios:
        res = run_scenarios(panel, reps, prices, a.view, a.count_endpoint, a.data_dir)
        for name, r in res.items():
            print(fmt_table(r, f"{name} ({r['n_transcripts']} transcripts, dims={len(r['dims'])}, view={r['view']})"))
            print()
    else:
        inputs = jobs_mod.build_inputs(a.n, dims_of(a.dims), a.view, a.data_dir, a.start)
        res = estimate(jobs_mod.build_jobs(inputs, panel, reps), prices, a.count_endpoint)
        print(fmt_table(res, f"{a.n - a.start} transcripts, dims={a.dims}, view={a.view}"))
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
