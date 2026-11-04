"""Corpus loading and the 260-transcript analysis order.

Same algorithm and seed as `pilot/scripts/prepare.py`, extended from 120 to all 260 transcripts in
`corpus_index.selected_2pp`: shuffle each target x severity cell with `random.Random(20261007)`,
then a greedy nested proportional order, so every prefix is a proportional stratified sample.
The greedy rule does not look ahead, so the first 120 positions equal the pilot's
(checked in tests/test_corpus.py against pilot/sample_meta.json).

Labels (target, severity, expected dimensions) are kept in the meta rows and never enter the
judge input. The seeds files are never read (dataset card: never show them to the judge).
"""
import collections
import json
import os
import random
import re

SEED = 20261007
N_ANALYSIS = 260
N_PILOT = 120
DEFAULT_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw", "data")


def short_target(s):
    s = s.lower()
    for key, lab in [("hermes", "hermes3"), ("deepseek", "deepseek_v31"), ("mistral", "mistral_large")]:
        if key in s:
            return lab
    return s


def analysis_order(data_dir=DEFAULT_DATA, n_max=N_ANALYSIS):
    manifest = json.load(open(os.path.join(data_dir, "manifest.json"), encoding="utf-8"))
    index = json.load(open(os.path.join(data_dir, "corpus_index.json"), encoding="utf-8"))
    analysis = list(index["selected_2pp"])
    if len(analysis) != N_ANALYSIS:
        raise ValueError(f"expected {N_ANALYSIS} transcripts in selected_2pp, got {len(analysis)}")
    cells = collections.defaultdict(list)
    rng = random.Random(SEED)
    for fname in sorted(analysis):
        lab = manifest[fname]
        cells[(short_target(lab["target_model"]), lab["severity"])].append(fname)
    for c in cells:
        rng.shuffle(cells[c])
    pool_n = sum(len(v) for v in cells.values())
    order, taken = [], collections.Counter()
    for k in range(1, min(n_max, pool_n) + 1):
        best, best_def = None, None
        for c, items in cells.items():
            if taken[c] >= len(items):
                continue
            deficit = len(items) / pool_n * k - taken[c]
            if best_def is None or deficit > best_def:
                best, best_def = c, deficit
        order.append((best, cells[best][taken[best]]))
        taken[best] += 1
    rows = []
    for pos, (cell, fname) in enumerate(order, start=1):
        lab = manifest[fname]
        rows.append({"pos": pos, "pilot120": pos <= N_PILOT, "transcript_key": fname,
                     "target": cell[0], "severity": lab["severity"], "seed_id": lab.get("seed_id"),
                     "expected_dimensions": lab.get("expected_dimensions", [])})
    return rows


_THINK_RE = re.compile(r"<(thinking|think)>(.*?)</\1>", re.S | re.I)


def thinking_blocks(d):
    """Target reasoning visible to the judge: (structured reasoning parts, non-empty in-text
    <thinking>/<think> blocks) over the target's assistant messages."""
    structured = intext = 0
    for m in d.get("target_messages", []):
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        if isinstance(c, list):
            structured += sum(1 for p in c if isinstance(p, dict) and p.get("type") == "reasoning")
            c = " ".join(p.get("text", "") for p in c if isinstance(p, dict) and isinstance(p.get("text"), str))
        intext += sum(1 for _, body in _THINK_RE.findall(c or "") if body.strip())
    return structured, intext


def thinking_report(data_dir=DEFAULT_DATA):
    """Per target and analysis subset: transcripts whose target shows any reasoning trace.
    Relevant to `unfaithful_thinking`, which Petri scores 1 when no thinking tags are present."""
    out = {}
    for r in analysis_order(data_dir):
        s, t = thinking_blocks(load_transcript(r["transcript_key"], data_dir))
        for subset in ("all_260", "pilot_120" if r["pilot120"] else "confirmatory_140"):
            c = out.setdefault(r["target"], {}).setdefault(subset, {"n": 0, "structured_reasoning": 0, "intext_thinking": 0})
            c["n"] += 1
            c["structured_reasoning"] += s > 0
            c["intext_thinking"] += t > 0
    return out


def load_transcript(fname, data_dir=DEFAULT_DATA):
    return json.load(open(os.path.join(data_dir, "transcripts", fname), encoding="utf-8"))


def write_meta(path, data_dir=DEFAULT_DATA):
    """Labels for the 260 analysis transcripts (kept off the judge), in the format analysis/ reads."""
    rows = analysis_order(data_dir)
    for r in rows:
        r["transcript_id"] = load_transcript(r["transcript_key"], data_dir)["metadata"]["transcript_id"]
    json.dump({"seed": SEED, "source": "adlnk/petri-synthetic-transcripts (CC-BY-4.0), data/manifest.json",
               "rows": rows}, open(path, "w", encoding="utf-8"), indent=1)
    return rows


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--thinking-report":
        rep = thinking_report()
        print(json.dumps(rep, indent=1))
        if len(sys.argv) > 2:
            json.dump({"source": "adlnk/petri-synthetic-transcripts (CC-BY-4.0); counts only", "by_target": rep},
                      open(sys.argv[2], "w", encoding="utf-8"), indent=1)
    else:
        write_meta(sys.argv[1] if len(sys.argv) > 1 else "results/meta_260.json")
