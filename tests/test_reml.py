"""REML sensitivity: equals the ANOVA estimates on balanced data, recovers components with missing cells."""
import numpy as np
import pytest

from analysis import phi, reml
from test_phi import simulate, TRUE


def test_reml_equals_anova_on_balanced_data():
    rng = np.random.default_rng(31)
    Y, g = simulate(rng, n_per=(40, 40, 40), J=3, R=2)
    fr = reml.fit(Y, g)
    gs = phi.gstudy(Y, g)
    assert fr["converged"]
    for h in ("g0", "g1", "g2"):
        for c in ("s_t", "s_tj", "s_e"):
            assert fr["components"][f"{c}[{h}]"] == pytest.approx(gs["per_group"][h][c], rel=0.02, abs=2e-3)


def test_reml_with_missing_cells_and_phi_hook():
    rng = np.random.default_rng(32)
    Y, g = simulate(rng, n_per=(60, 60), J=3, R=2)
    Y[rng.random(Y.shape) < 0.15] = np.nan
    fr = reml.fit(Y, g)
    assert fr["n_scores"] == int(np.isfinite(Y).sum())
    for h in ("g0", "g1"):
        assert fr["components"][f"s_t[{h}]"] == pytest.approx(TRUE["s_t"], rel=0.35)
        assert fr["components"][f"s_e[{h}]"] == pytest.approx(TRUE["s_e"], rel=0.3)
    g2 = reml.gs_like(fr, J=3, R=2)
    assert phi.contrast_var(g2, "g0", "g1") > 0
