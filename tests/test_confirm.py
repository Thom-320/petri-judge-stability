"""H1'/H2' (fixed judges, design-based) and the Holm family, on simulated data."""
import numpy as np
import pytest

from analysis import confirm
from test_phi import simulate, TRUE

GL = ["g0", "g1", "g2"]


def test_calibration_only_judges_support_h1():
    """Large judge main effects, no target x judge interaction: levels differ, contrasts agree."""
    rng = np.random.default_rng(21)
    Y, g = simulate(rng, n_per=(50, 50, 50), mu=(1.0, 2.0, 3.0), judge_eff=np.array([-1.0, 0.0, 1.0]),
                    gj=np.zeros((3, 3)))
    r = confirm.confirm_dim(Y, g, GL, rng, B=300)
    assert r["H1"]["mean_D"] > 0.5
    assert r["H1"]["p_one_sided"] < 0.01
    assert r["H1"]["share_rule_met"]


def test_ranking_only_judges_reject_h1():
    """No judge main effect, large target x judge interaction: contrasts disagree more than levels."""
    rng = np.random.default_rng(22)
    gj = np.array([[1.0, -1.0, 0.0], [-1.0, 1.0, 0.0], [0.0, 0.0, 0.0]])
    Y, g = simulate(rng, n_per=(50, 50, 50), judge_eff=np.zeros(3), gj=gj)
    r = confirm.confirm_dim(Y, g, GL, rng, B=300)
    assert r["H1"]["mean_D"] < 0
    assert r["H1"]["p_one_sided"] > 0.5


def test_h2_threshold_flips_exceed_contrast_flips_under_calibration_offsets():
    """Target means straddle c = 4 and judges disagree in level only: thresholds flip, contrasts do not."""
    rng = np.random.default_rng(23)
    Y, g = simulate(rng, n_per=(50, 50, 50), mu=(4.0, 1.0, 7.5), judge_eff=np.array([-0.6, 0.0, 0.6]),
                    gj=np.zeros((3, 3)), comp={**TRUE, "s_t": 0.5})
    r = confirm.confirm_dim(Y, g, GL, rng, B=300)
    est = r["H2"]["estimate"]
    assert est["FT_4"] > 0.2 and est["FC"] < 0.02
    assert r["H2"]["p_one_sided"]["4"] < 0.01


def test_contrast_flip_counts_ties_as_half():
    YA = np.array([[[2.0], [2.0]]])  # one transcript of target A, judges j0, j1, one repeat
    YB = np.array([[[1.0], [2.0]]])
    sw, _ = confirm._contrast_flip_matrices(YA, YB, [(0, 1)])
    assert sw[0, 0] == pytest.approx(0.5)  # j0: A > B, j1: tie
    YB2 = np.array([[[1.0], [3.0]]])
    sw2, _ = confirm._contrast_flip_matrices(YA, YB2, [(0, 1)])
    assert sw2[0, 0] == pytest.approx(1.0)  # strict reversal


def test_judge_subset_restricts_pairs():
    rng = np.random.default_rng(24)
    Y, g = simulate(rng, n_per=(20, 20, 20), J=5)
    cells = confirm.h1_cells(Y, g, GL, judge_idx=[0, 1, 2])
    assert {k[:2] for k in cells} == {(0, 1), (0, 2), (1, 2)}


def test_holm_matches_manual():
    adj = confirm.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.20})
    assert adj["a"] == pytest.approx(0.04)
    assert adj["c"] == pytest.approx(0.09)
    assert adj["b"] == pytest.approx(0.09)  # monotone: max(0.04*2, 0.09)
    assert adj["d"] == pytest.approx(0.20)


def test_family_requires_share_rule_for_h1():
    res = {"d": {"H1": {"p_one_sided": 0.001, "share_rule_met": False},
                 "H2": {"p_one_sided": {"4": 0.001, "7": 0.5}}}}
    fam = confirm.family(res, ["d"])
    assert fam["m"] == 3
    assert fam["tests"]["H1|d"]["rejected_at_alpha"] and not fam["tests"]["H1|d"]["supported"]
    assert fam["tests"]["H2|d|c=4"]["supported"] and not fam["tests"]["H2|d|c=7"]["supported"]


def test_petri_cutoffs_match_pinned_viewer():
    assert confirm.PETRI_CUTOFFS == (4, 7)
