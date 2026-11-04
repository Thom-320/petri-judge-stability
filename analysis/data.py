"""Load judge records (pilot or v2 runners) into score tensors n x J x R per dimension.

Accepted records: one JSON object per line with transcript_id, judge, repeat, status and
parse.scores (dict dim -> int). Pilot records (pilot/scores_pilot120.jsonl; the raw outputs, not
redistributed, are pilot/raw/judgments_final.jsonl) and v2 runner records (runs/<provider>/results.jsonl)
both have this shape. Missing scores (parse failure, refusal,
API error) stay NaN; they are counted, never floored.
"""
import json

import numpy as np

PILOT_JUDGES = ["muse", "mimo", "deepseek"]
TARGETS = ["hermes3", "deepseek_v31", "mistral_large"]


def read_records(paths):
    recs = []
    for p in paths if isinstance(paths, (list, tuple)) else [paths]:
        for line in open(p, encoding="utf-8"):
            if line.strip():
                recs.append(json.loads(line))
    return recs


def load_meta(path, n_max=None):
    m = json.load(open(path, encoding="utf-8"))
    rows = sorted(m["rows"] if isinstance(m, dict) else m, key=lambda r: r["pos"])
    if n_max is not None:
        rows = [r for r in rows if r["pos"] <= n_max]
    return rows


def score_tensor(recs, meta_rows, dim, judges, repeats=(1, 2), petri_floor=False):
    """petri_floor=True reproduces Petri's silent floor for SENSITIVITY ONLY: a response whose score
    for `dim` is missing counts as 1 (Petri does this after its retries are exhausted)."""
    tids = [r["transcript_id"] for r in meta_rows]
    ti = {t: i for i, t in enumerate(tids)}
    Y = np.full((len(tids), len(judges), len(repeats)), np.nan)
    for r in recs:
        if r.get("status") != "responded" or r.get("transcript_id") not in ti or r.get("judge") not in judges:
            continue
        if r.get("repeat") not in repeats:
            continue
        s = (r.get("parse") or {}).get("scores", {}).get(dim)
        if s is None and petri_floor:
            s = 1
        if s is None:
            continue
        Y[ti[r["transcript_id"]], judges.index(r["judge"]), list(repeats).index(r["repeat"])] = s
    return Y


def complete(Y):
    return ~np.any(np.isnan(Y), axis=(1, 2))


def missing_summary(recs, judges, dims):
    """Counts of missing scores by judge and reason code (v2 records) or by status (pilot records)."""
    out = {}
    for j in judges:
        rs = [r for r in recs if r.get("judge") == j]
        reasons = {}
        for r in rs:
            p = r.get("parse") or {}
            miss = p.get("missing")
            if isinstance(miss, dict):
                for d, why in miss.items():
                    if d in dims:
                        reasons[why] = reasons.get(why, 0) + 1
            elif isinstance(miss, list):
                for d in miss:
                    if d in dims:
                        key = "no_scores_block" if not p.get("scores") else "dim_missing"
                        reasons[key] = reasons.get(key, 0) + 1
            if r.get("status") != "responded" and not isinstance(miss, dict):  # pilot-style record
                reasons["no_response"] = reasons.get("no_response", 0) + len(dims)
        out[j] = {"calls": len(rs), "missing_cells_by_reason": reasons}
    return out


def missing_by_stratum(recs, meta_rows, judges, dims, repeats=(1, 2), key="severity"):
    """Failure rate per judge x stratum (default: planted severity) x dimension.

    Expected cells = transcripts in the stratum x repeats; a cell is valid only if a responded call
    returned a 1-10 score for the dimension. Reasons are counted from v2 parse records
    (`parse.missing` dict) and from non-responded calls; cells with no record at all count as
    `no_record`. This is the check for missingness that depends on severity (e.g. refusals or
    content filters on the most severe misuse transcripts)."""
    strat = {r["transcript_id"]: r.get(key) for r in meta_rows}
    levels = sorted({v for v in strat.values() if v is not None})
    out = {}
    for j in judges:
        out[j] = {}
        for dim in dims:
            cells = {lv: {"expected": 0, "valid": 0, "reasons": {}} for lv in levels}
            for lv in levels:
                cells[lv]["expected"] = sum(1 for v in strat.values() if v == lv) * len(repeats)
            seen = set()
            for r in recs:
                t = r.get("transcript_id")
                if r.get("judge") != j or t not in strat or r.get("repeat") not in repeats:
                    continue
                if (t, r["repeat"]) in seen:
                    continue
                seen.add((t, r["repeat"]))
                c = cells[strat[t]]
                p = r.get("parse") or {}
                if r.get("status") == "responded" and (p.get("scores") or {}).get(dim) is not None:
                    c["valid"] += 1
                    continue
                miss = p.get("missing")
                why = miss.get(dim) if isinstance(miss, dict) else None
                why = why or ("dim_missing" if r.get("status") == "responded" else (r.get("status") or "no_response"))
                c["reasons"][why] = c["reasons"].get(why, 0) + 1
            for lv, c in cells.items():
                c["missing"] = c["expected"] - c["valid"]
                nr = c["missing"] - sum(c["reasons"].values())
                if nr > 0:
                    c["reasons"]["no_record"] = nr
                c["failure_rate"] = c["missing"] / c["expected"] if c["expected"] else float("nan")
            out[j][dim] = cells
    return out
