"""phi machinery on simulated data with known components."""
import numpy as np
import pytest

from analysis import phi

TRUE = {"s_t": 1.0, "s_gj": 0.09, "s_j": 0.25, "s_tj": 0.3, "s_e": 0.2}


def simulate(rng, n_per=(400, 400, 400), mu=(0.0, 0.3, 1.5), J=3, R=2, comp=TRUE, judge_eff=None, gj=None):
    G = len(n_per)
    cj = rng.normal(0, np.sqrt(comp["s_j"]), J) if judge_eff is None else judge_eff
    gje = rng.normal(0, np.sqrt(comp["s_gj"]), (G, J)) if gj is None else gj
    Ys, groups = [], []
    for g, n in enumerate(n_per):
        t = rng.normal(0, np.sqrt(comp["s_t"]), n)
        tj = rng.normal(0, np.sqrt(comp["s_tj"]), (n, J))
        e = rng.normal(0, np.sqrt(comp["s_e"]), (n, J, R))
        Ys.append(mu[g] + t[:, None, None] + cj[None, :, None] + gje[g][None, :, None] + tj[:, :, None] + e)
        groups += [f"g{g}"] * n
    return np.concatenate(Ys), np.array(groups)


def test_within_group_components_recovered():
    rng = np.random.default_rng(1)
    Y, g = simulate(rng, n_per=(3000, 3000))
    gs = phi.gstudy(Y, g)
    for grp in ("g0", "g1"):
        p = gs["per_group"][grp]
        assert p["s_t"] == pytest.approx(1.0, rel=0.08)
        assert p["s_tj"] == pytest.approx(0.3, rel=0.08)
        assert p["s_e"] == pytest.approx(0.2, rel=0.05)


def test_judge_components_unbiased_on_average():
    rng = np.random.default_rng(2)
    est_gj, est_j = [], []
    for _ in range(400):
        Y, g = simulate(rng, n_per=(60, 60, 60), J=4)
        gs = phi.gstudy(Y, g)
        est_gj.append(gs["s_gj_raw"])
        est_j.append(gs["s_j_raw"])
    assert np.mean(est_gj) == pytest.approx(TRUE["s_gj"], abs=0.02)
    assert np.mean(est_j) == pytest.approx(TRUE["s_j"], abs=0.06)


def test_phi_formula_matches_monte_carlo_flip_rate():
    """Two independent panels drawn from the true model: flip rate == 2p(1-p) with the true sigma_D."""
    rng = np.random.default_rng(3)
    n, J, R, delta = 40, 3, 2, 0.3
    flips = 0
    sims = 3000
    for _ in range(sims):
        ds = []
        for _panel in range(2):
            Y, g = simulate(rng, n_per=(n, n), mu=(delta, 0.0), J=J, R=R)
            ds.append(Y[g == "g0"].mean() - Y[g == "g1"].mean())
        flips += np.sign(ds[0]) != np.sign(ds[1])
    var = 2 * (TRUE["s_t"] / n + TRUE["s_gj"] / J + TRUE["s_tj"] / (n * J) + TRUE["s_e"] / (n * J * R))
    assert flips / sims == pytest.approx(phi.phi_from(delta, np.sqrt(var)), abs=0.03)


def test_judge_main_effect_cancels_in_contrasts_not_in_thresholds():
    rng = np.random.default_rng(4)
    Y, g = simulate(rng, n_per=(200, 200), mu=(0, 0), judge_eff=np.array([-3.0, 0.0, 3.0]), gj=np.zeros((2, 3)))
    gs = phi.gstudy(Y, g)
    big_j = phi.threshold_var(gs, "g0") - gs["per_group"]["g0"]["s_t"] / 200
    assert gs["s_j"] > 5 and big_j > 1.5
    assert phi.contrast_var(gs, "g0", "g1") < 0.05


def test_dstudy_judge_floor():
    rng = np.random.default_rng(5)
    Y, g = simulate(rng, n_per=(100, 100), mu=(0.2, 0.0), comp={**TRUE, "s_gj": 0.5}, gj=np.array([[0.7, -0.7, 0.0], [-0.7, 0.7, 0.0]]))
    gs = phi.gstudy(Y, g)
    ds = phi.dstudy_contrast(gs, "g0", "g1")
    lim = ds["phi_limit_n_infinite_by_J"]
    assert lim["1"] > lim["3"] > lim["8"]  # more transcripts cannot remove judge disagreement; more judges can


def test_placebo_and_negative_control_behave():
    rng = np.random.default_rng(6)
    Y, g = simulate(rng, n_per=(60, 60, 60), mu=(0.0, 0.0, 0.0))
    pl = phi.placebo(Y, g, rng, perms=150, draws=100)
    assert pl["plugin_phi_mean"] == pytest.approx(1 / 3, abs=0.06)
    assert pl["empirical_split_phi_mean"] == pytest.approx(0.5, abs=0.08)
    Y2, g2 = simulate(rng, n_per=(60, 60), mu=(4.0, 0.0))
    res, _ = phi.decisions(Y2, g2)
    assert res["contrasts"]["g0|g1"]["phi_full"] < 1e-6


# ---------------------------------------------------------------- Session 2 additions
def test_bias_corrected_phi_is_closer_to_half_under_the_null():
    rng = np.random.default_rng(11)
    Y, g = simulate(rng, n_per=(60, 60, 60), mu=(0.0, 0.0, 0.0))
    pl = phi.placebo(Y, g, rng, perms=150, draws=50)
    assert pl["plugin_phi_mean"] < pl["bc_phi_mean"] < 0.5
    assert pl["bc_phi_mean"] == pytest.approx(0.425, abs=0.06)  # analytic value under a normal null


def test_phi_interval_covers_true_phi():
    """Inverting the normal interval for Delta covers the true phi at the nominal rate (sd known)."""
    rng = np.random.default_rng(12)
    sd = 1.0
    for z in (0.0, 0.7, 2.0):
        hits = 0
        for _ in range(2000):
            d_hat = z + rng.normal()
            lo, hi = phi.phi_interval(d_hat, 1.0, sd)
            hits += lo - 1e-12 <= phi.phi_from(z, sd) <= hi + 1e-12
        assert hits / 2000 >= 0.94


def test_judge_component_intervals_cover_and_match_df():
    rng = np.random.default_rng(13)
    cover_gj, cover_j = 0, 0
    sims = 300
    for _ in range(sims):
        Y, g = simulate(rng, n_per=(40, 40, 40), J=8)
        ci = phi.judge_component_ci(phi.gstudy(Y, g))
        cover_gj += ci["s_gj"]["ci"][0] <= TRUE["s_gj"] <= ci["s_gj"]["ci"][1]
        cover_j += ci["s_j"]["ci"][0] <= TRUE["s_j"] <= ci["s_j"]["ci"][1]
    assert ci["df_int"] == 14 and ci["df_col"] == 7
    assert cover_gj / sims >= 0.88
    assert cover_j / sims >= 0.85


def test_chi2_fold_range_by_judge_count():
    """The interval width ratio quoted in the pre-registration: about 146x at 2 df, 15x at 5, 9.5x at 7."""
    for df, ratio in ((2, 146), (5, 15.4), (7, 9.5)):
        lo, hi = phi._chi2_interval(1.0, df)
        assert hi / lo == pytest.approx(ratio, rel=0.02)


def test_model_check_bracket_rule():
    mk = lambda sp, pl, bc: {"x": {"phi_empirical": sp, "phi_model_J1R1_half": pl, "phi_bc_model_J1R1_half": bc}}  # noqa: E731
    assert phi.model_check(mk(0.30, 0.25, 0.32))["passed"]
    assert phi.model_check(mk(0.20, 0.25, 0.32))["passed"]       # within plug-in - 0.05
    assert not phi.model_check(mk(0.19, 0.25, 0.32))["passed"]
    assert not phi.model_check(mk(0.38, 0.25, 0.32))["passed"]
    assert not phi.model_check({})["passed"]


def test_floor_bound_brackets_point_and_shrinks_with_J():
    rng = np.random.default_rng(14)
    Y, g = simulate(rng, n_per=(80, 80, 80), mu=(0.0, 0.4, 1.5), J=8)
    fb = phi.floor_bound(phi.gstudy(Y, g), Js=(1, 3, 8), thresholds=(1.0,))
    for kind in ("contrasts", "thresholds"):
        for r in fb[kind].values():
            for J in ("1", "3", "8"):
                lo, hi = r["by_J"][J]["bound"]
                assert lo - 1e-12 <= r["by_J"][J]["point"] <= hi + 1e-12
            assert r["by_J"]["8"]["bound"][1] <= r["by_J"]["1"]["bound"][1] + 1e-12
