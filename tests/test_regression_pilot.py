"""Regression: the new analysis code reproduces the pilot's published statistics exactly.

Compares every field of pilot/results/results_scale120.json and results_pilot20.json (ICC, alpha,
test-retest, variance components, bootstrap CIs, rank stability, AUC) with analysis.run.analyze on
pilot/scores_pilot120.jsonl (the pilot records without the judges' generated text), same seed,
tolerance 1e-12.
"""
import json
import os

import numpy as np
import pytest

from analysis import data, run
from conftest import ROOT

RENAMED = {"kalpha_all6_raters": "kalpha_all_raters", "P_all_three_judges_same_order": "P_all_judges_same_order"}


def walk(a, b, path=""):
    bad = []
    if isinstance(a, dict):
        for k in a:
            kb = RENAMED.get(k, k)
            if kb not in b:
                bad.append(f"{path}/{k} missing")
            else:
                bad += walk(a[k], b[kb], f"{path}/{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            bad += walk(x, y, f"{path}[{i}]")
    elif isinstance(a, float):
        if not ((np.isnan(a) and np.isnan(b)) or abs(a - b) <= 1e-12):
            bad.append(f"{path}: {a} != {b}")
    elif a != b:
        bad.append(f"{path}: {a!r} != {b!r}")
    return bad


@pytest.mark.parametrize("n,tag", [(120, "scale120"), (20, "pilot20")])
def test_reproduces_pilot_results(n, tag):
    old = json.load(open(os.path.join(ROOT, "pilot", "results", f"results_{tag}.json")))
    recs = data.read_records(os.path.join(ROOT, "pilot", "scores_pilot120.jsonl"))
    meta = data.load_meta(os.path.join(ROOT, "pilot", "sample_meta.json"), n)
    new = run.analyze(recs, meta, data.PILOT_JUDGES, b_phi=0, placebo_perms=0, split_draws=10,
                      b_confirm=0, run_reml=False)
    assert new["n_transcripts_in_sample"] == old["n_transcripts_in_sample"]
    for dim, d in old["dims"].items():
        assert walk(d, new["dims"][dim], dim) == []
