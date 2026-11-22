#!/usr/bin/env bash
# Offline reproduction of the README's headline figures from the committed data. No API keys, no network.
#   1. Re-run the pilot analysis from pilot/scores_pilot120.jsonl into a temp dir and compare it with
#      results/pilot120/ (JSON: relative tolerance 1e-9, 1e-5 for the REML fit; Markdown: byte-identical).
#   2. Read each figure from README.md and recompute it from the regenerated results, the score records
#      and the committed dry-run estimates (results/estimate_*.json). A figure matches if the recomputed
#      value rounds to the published one at the published precision.
# Exits 1 if anything differs. Usage: bash scripts/reproduce_offline.sh   (PYTHON=... to pick the interpreter)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

echo "== 1/2 re-running the pilot analysis (python -m analysis.run, ~2-5 min)"
"$PY" -m analysis.run --judgments pilot/scores_pilot120.jsonl --meta pilot/sample_meta.json \
    --n 120 --judges muse,mimo,deepseek --out "$OUT" --tag pilot120_cheap > "$OUT/run.log"

echo "== 2/2 comparing with the committed results and the README"
"$PY" - "$OUT" <<'PYEOF'
import json, math, os, re, sys

out = sys.argv[1]
fails = []
TAG = "pilot120_cheap"
# The REML sensitivity fit is an iterative scipy optimisation; its last digits move with the scipy version.
REML_REL = 1e-5


def same(a, b, path, bad, rel=1e-9):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            bad.append(f"{path}: keys differ {sorted(set(a) ^ set(b))}")
        for k in set(a) & set(b):
            same(a[k], b[k], f"{path}/{k}", bad, REML_REL if k == "reml_sensitivity" else rel)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            bad.append(f"{path}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f"{path}[{i}]", bad, rel)
    elif isinstance(a, float) or isinstance(b, float):
        x, y = float(a), float(b)
        if not ((math.isnan(x) and math.isnan(y)) or abs(x - y) <= rel * max(1.0, abs(x), abs(y))):
            bad.append(f"{path}: {a!r} != {b!r}")
    elif a != b:
        bad.append(f"{path}: {a!r} != {b!r}")


committed = json.load(open(f"results/pilot120/results_{TAG}.json"))
R = json.load(open(os.path.join(out, f"results_{TAG}.json")))
bad = []
same(committed, R, "", bad)
md_ok = open(f"results/pilot120/phi_vs_icc_{TAG}.md").read() == open(os.path.join(out, f"phi_vs_icc_{TAG}.md")).read()
print(f"regenerated results_{TAG}.json vs committed (rel tol 1e-9; REML fit 1e-5): {'OK' if not bad else f'{len(bad)} differences'}")
for b in bad[:20]:
    print("   ", b)
print(f"regenerated phi_vs_icc_{TAG}.md vs committed (byte-identical): {'OK' if md_ok else 'DIFFERS'}")
if bad:
    fails.append(f"results_{TAG}.json")
if not md_ok:
    fails.append(f"phi_vs_icc_{TAG}.md")

README = open("README.md", encoding="utf-8").read()
recs = [json.loads(l) for l in open("pilot/scores_pilot120.jsonl")]
meta = json.load(open("pilot/sample_meta.json"))["rows"][:120]
scen = json.load(open("results/estimate_scenarios.json"))
des = json.load(open("results/estimate_designs.json"))
D = R["dims"]
DIMS = list(D)
CD = R["confirm_dims"]
rows = []


def num(s):
    return float(s.replace("−", "-").replace(",", "").replace("$", "").replace("%", ""))


def decimals(s):
    s = s.replace(",", "").replace("$", "").replace("%", "")
    return len(s.split(".")[1]) if "." in s else 0


def find(pattern, label):
    m = re.search(pattern, README)
    if not m:
        rows.append((label, "(text not found in README)", "-", False))
        return None
    return m.groups()


def check(label, pattern, values, digits=None, scale=1.0):
    """Published numbers are the regex groups; each must equal the recomputed value at its precision."""
    g = find(pattern, label)
    if g is None:
        return
    ok = len(g) == len(values)
    shown = []
    for s, v in zip(g, values):
        d = decimals(s) if digits is None else digits
        tol = 0.5 * 10 ** (-d) + 1e-9
        ok &= abs(num(s) - v * scale) <= tol
        x = v * scale
        shown.append(f"{x:,.0f}" if float(x).is_integer() else f"{x:.{d + 2}f}")
    rows.append((label, ", ".join(g), ", ".join(shown), bool(ok)))


def check_bool(label, pattern, cond, shown):
    if find(pattern, label) is not None:
        rows.append((label, "(statement)", shown, bool(cond)))


# --- Setup
check("Pilot judge records", r"holds the pilot's ([\d,]+) judge records", [len(recs)])
check("Transcripts", r"\n- ([\d,]+) transcripts from the public", [R["n_transcripts_in_sample"]])
n_targets = len({r["target"] for r in meta})
check_bool("Three target models", r"(Three) target models", n_targets == 3, str(n_targets))
check_bool("Four Petri dimensions", r"(Four) Petri dimensions", len(DIMS) == 4, str(len(DIMS)))
jr = {(r["transcript_id"], r["judge"], r["repeat"]) for r in recs}
judges = sorted({r["judge"] for r in recs})
twice = len(judges) == 3 and len(jr) == 120 * 3 * 2 == len(recs)
check_bool("Three judges, each scoring every transcript twice", r"(Three) \*\*cheap judges\*\*.*?\*\*twice\*\*", twice,
           f"{len(judges)} judges, {len(jr)} distinct (transcript, judge, repeat)")
mimo = [r for r in recs if r["judge"] == "mimo"]
fail = 1 - sum(len(r["parse"].get("scores") or {}) == 4 for r in mimo) / len(mimo)
check("MiMo calls without a usable score block (%)", r"returned no usable score block on (\d+(?:\.\d+)?)%", [fail], scale=100)

# --- Finding 1
icc = [D[d]["icc21_interjudge_rep1"] for d in DIMS]
check("Inter-judge ICC(2,1) range across dimensions", r"Inter-judge ICC\(2,1\) is (\d+(?:\.\d+)?) to (\d+(?:\.\d+)?)", [min(icc), max(icc)])
c = D["concerning"]
check("ICC(2,1) concerning [95% CI]", r"`concerning` (\d+(?:\.\d+)?) \[(\d+(?:\.\d+)?), (\d+(?:\.\d+)?)\]",
      [c["icc21_interjudge_rep1"], *c["boot_ci95"]["icc21_interjudge_rep1"]])
tr = [D[d]["test_retest"][j]["icc21"] for d in DIMS for j in D[d]["test_retest"]]
check("Test-retest ICC range per judge", r"Test-retest is (\d+(?:\.\d+)?) to (\d+(?:\.\d+)?) per judge", [min(tr), max(tr)])
ts = [D[d]["varcomp_share"]["transcript"] for d in DIMS]
check("Transcript share of variance (%)", r"Transcripts explain (\d+) to (\d+)% of the variance", [min(ts), max(ts)], scale=100)

# --- Finding 2
ct = c["phi"]["contrasts"]
check("ICC(2,1) concerning (finding 2)", r"With the same ICC of (\d+(?:\.\d+)?) on `concerning`", [c["icc21_interjudge_rep1"]])
hm = ct["hermes3|mistral_large"]
check_bool("phi, Hermes vs Mistral, concerning, is about 0 (2 dp)", r"\"Hermes is less concerning than Mistral\" has φ ≈ (0)",
           round(hm["phi_full"], 2) == 0, f"{hm['phi_full']:.2e}")
dm = ct["deepseek_v31|mistral_large"]
check("phi, DeepSeek V3.1 vs Mistral, concerning [95% CI]", r"φ = (\d+(?:\.\d+)?) \[(\d+(?:\.\d+)?), (\d+(?:\.\d+)?)\], close to a coin flip",
      [dm["phi_full"], *dm["phi_ci95_full"]])
fac = {k: dm[f"phi_{k}"] for k in ("transcripts", "judges", "repeats")}
check_bool("Largest facet of that phi is transcript sampling", r"Most of that instability comes from \*\*(transcript sampling)\*\*",
           max(fac, key=fac.get) == "transcripts", ", ".join(f"{k} {v:.3f}" for k, v in fac.items()))

# --- Finding 3
fam = R["confirmatory_family"]
tests = fam["tests"].values()
n_sup = sum(t["supported"] for t in tests)
g = find(r"(None) of the (\d+) pre-specified tests was supported", "Pre-specified tests, none supported")
if g:
    ok = fam["m"] == int(g[1]) == len(fam["tests"]) and n_sup == 0
    rows.append(("Pre-specified tests, none supported", f"0 of {g[1]}", f"{n_sup} of {fam['m']}", ok))
ph = [t["p_holm"] for t in tests]
check("Holm-adjusted p, min", r"Every Holm-adjusted p was (\d+\.\d+)", [min(ph)])
check("Holm-adjusted p, max", r"Every Holm-adjusted p was (\d+\.\d+)", [max(ph)])
g = find(r"exceeded contrast discrepancies on (\d+) of (\d+) judge-pair", "H1 cells with offset > discrepancy (95% lower bound > 0)")
if g:
    cells = {d: D[d]["confirm"]["H1"]["cells"] for d in CD}
    pos = {d: sum(x["lower_bound_above_0"] for x in v.values()) for d, v in cells.items()}
    ok = all(len(v) == int(g[1]) for v in cells.values()) and all(p == int(g[0]) for p in pos.values())
    rows.append(("H1 cells with offset > discrepancy (95% lower bound > 0), per dimension", f"{g[0]} of {g[1]}",
                 "; ".join(f"{d}: {pos[d]} of {len(cells[d])}" for d in CD), ok))
diffs = [D[d]["confirm"]["H2"]["estimate"][f"diff_{k}"] for d in CD for k in (4, 7)]
check("Target-level FT - FC at c = 4, 7 (range)", r"threshold-minus-contrast flip rates ranged from ([−+\-]?\d+\.\d+) to ([−+\-]?\d+\.\d+)",
      [min(diffs), max(diffs)])
e = c["confirm"]["H2"]["estimate"]
check("concerning, c = 5: threshold vs contrast flips", r"threshold flips (\d+(?:\.\d+)?) vs contrast flips (\d+(?:\.\d+)?)", [e["FT_5"], e["FC"]])
gs = c["phi"]["gstudy"]
check("df for judge and repeat components (J = 3, R = 2)", r"give (\d+) df and (\d+) df", [gs["df_j"], gs["R"] - 1])

# --- Cost (committed dry-run estimates; regenerating them needs the corpus in data/raw/)
full = scen["full_260_4dims"]
check("Requests in the full design", r"= ([\d,]+) requests, with four dimensions", [full["requests"]])
pj = full["per_judge"]["opus45"]
check("Mean input tokens per request (nearest 50)", r"about ([\d,]+) per request", [round(pj["mean_input_tokens"] / 50) * 50], digits=0)
check("Output tokens per request, low / high", r"low case ([\d,]+) tokens, high case ([\d,]+) tokens",
      [pj["output_tokens_low"] / pj["requests"], pj["output_tokens_high"] / pj["requests"]])
money = r"\| ([\d,]+) \| \$(\d[\d,]*(?:\.\d+)?) \| \$(\d[\d,]*(?:\.\d+)?) \| \$(\d[\d,]*(?:\.\d+)?) \| \$(\d[\d,]*(?:\.\d+)?) \|"
for label, key in [("Full: 260 transcripts, 4 dims", "full_260_4dims"), ("Pilot set: 120 transcripts", "pilot_120_4dims"),
                   ("Untouched: 140 transcripts", "untouched_140_4dims"), ("Cut: 260 transcripts, 2 dims", "cut_260_2dims"),
                   ("Cut: 120 transcripts, 2 dims", "cut_120_2dims")]:
    t = scen[key]["total_usd"]
    check(f"Cost: {label}", r"\| " + re.escape(label) + " " + money,
          [scen[key]["requests"], t["standard_low"], t["standard_high"], t["batch_low"], t["batch_high"]])
for label, key in [("Claude Opus 4.5", "opus45"), ("Gemini 3.1 Pro Preview", "gemini31pro"), ("GPT-5.1", "gpt51")]:
    u = full["per_judge"][key]["usd"]
    check(f"Batch cost by judge: {label}", r"\| " + re.escape(label) + r" \| \$(\d[\d,]*(?:\.\d+)?) \| \$(\d[\d,]*(?:\.\d+)?) \|",
          [u["batch_low"], u["batch_high"]])
check("Full design at the output cap, batch", r"would cost \$(\d[\d,]*(?:\.\d+)?) at batch prices", [full["total_usd"]["batch_cap"]])
for label, key in [("A, J = 3 (Petri panel)", "A_J3"), ("B, J = 6 (", "B_J6"), ("C, J = 8 (", "C_J8"), ("C-lite, J = 8 (", "C_J8_lite")]:
    t = des[key]["total_usd"]
    check(f"Design {key}", r"\| " + re.escape(label) + r"[^|]*\| ([\d,]+) \| \$(\d[\d,]*(?:\.\d+)?) \| \$(\d[\d,]*(?:\.\d+)?) \| \$(\d[\d,]*(?:\.\d+)?) \|",
          [des[key]["requests"], t["batch_low"], t["batch_high"], t["batch_cap"]])

table = ["| README figure | Published | Recomputed | Matches |", "|---|---|---|---|"]
table += [f"| {a} | {b} | {c_} | {'yes' if ok else 'NO'} |" for a, b, c_, ok in rows]
fails += [a for a, _, _, ok in rows if not ok]
md = "\n".join(table)
print()
print(md)
print(f"\n{sum(ok for *_, ok in rows)}/{len(rows)} README figures reproduce; results files: "
      f"{'OK' if not bad and md_ok else 'DIFFER'}")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write("## Offline reproduction\n\n" + md + "\n")
if fails:
    print("FAILED: " + "; ".join(fails))
    sys.exit(1)
print("OK: all checked figures reproduce")
PYEOF
