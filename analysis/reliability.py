"""Reliability statistics per dimension, numerically identical to the pilot's analyze.py.

Same estimators (imported from the pilot via analysis.pilot_fns), same complete-case rule, same
random stream: one `np.random.default_rng(seed)` shared across dimensions in the pilot's order,
B_CI unstratified transcript resamples for ICC / alpha / transcript share, then B stratified
resamples for rank stability. With the pilot's seed and inputs this reproduces
pilot/results/results_scale120.json (tests/test_regression_pilot.py).
"""
import numpy as np

from .pilot_fns import auc, icc21, kalpha_interval, varcomp

SEED = 20261008
B_RANK = 2000
B_CI = 1000


def _ci(v):
    return [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]


def dim_reliability(Y, tg, labels, judges, targets, rng, b_ci=B_CI, b_rank=B_RANK):
    """Y: n x J x R complete-case scores; tg: target label per transcript; labels: 0/1 planted label."""
    n, J, R = Y.shape
    d = {"score_mean_by_judge_rep1": {judges[j]: float(np.mean(Y[:, j, 0])) for j in range(J)},
         "score_sd_by_judge_rep1": {judges[j]: float(np.std(Y[:, j, 0], ddof=1)) for j in range(J)},
         "n_distinct_values_all": int(len(np.unique(Y)))}
    X1, XA = Y[:, :, 0], Y.mean(axis=2)
    d["icc21_interjudge_rep1"] = float(icc21(X1))
    d["icc21_interjudge_repavg"] = float(icc21(XA))
    d["kalpha_interjudge_rep1"] = float(kalpha_interval(X1))
    d["kalpha_all_raters"] = float(kalpha_interval(Y.reshape(n, -1)))
    tr = {}
    for j in range(J):
        tr[judges[j]] = {"icc21": float(icc21(Y[:, j, :])),
                         "pearson_r": float(np.corrcoef(Y[:, j, 0], Y[:, j, 1])[0, 1]) if np.std(Y[:, j, :]) > 0 else np.nan,
                         "exact_agreement": float(np.mean(Y[:, j, 0] == Y[:, j, 1]))}
    d["test_retest"] = tr
    d["test_retest_icc21_mean_over_judges"] = float(np.nanmean([tr[j]["icc21"] for j in judges]))
    raw, shares = varcomp(Y)
    d["varcomp_raw"] = {k: float(v) for k, v in raw.items()}
    d["varcomp_share"] = {k: float(v) for k, v in shares.items()}
    bi, ba, bs = [], [], []
    for _ in range(b_ci):
        ix = rng.integers(0, n, n)
        bi.append(icc21(X1[ix]))
        ba.append(kalpha_interval(X1[ix]))
        _, sh = varcomp(Y[ix])
        bs.append(sh["transcript"] if not np.isnan(sh["transcript"]) else np.nan)
    d["boot_ci95"] = {"icc21_interjudge_rep1": _ci(bi), "kalpha_interjudge_rep1": _ci(ba),
                      "transcript_variance_share": _ci(bs)}
    # rank stability of targets under judge swaps (stratified transcript bootstrap)
    M = XA
    gl = [g for g in targets if np.any(tg == g)]
    mu = {g: M[tg == g].mean(axis=0) for g in gl}
    point_order = {judges[j]: [gl[i] for i in np.argsort([-mu[g][j] for g in gl], kind="stable")] for j in range(J)}
    cons = {g: mu[g].mean() for g in gl}
    cons_order = [gl[i] for i in np.argsort([-cons[g] for g in gl], kind="stable")]
    pairs = [(a, b) for ia, a in enumerate(gl) for b in gl[ia + 1:]]
    pair_agree = {f"{a}>{b}": 0 for a, b in pairs}
    same_all, match_cons = 0, np.zeros(J)
    grp_ix = [np.where(tg == g)[0] for g in gl]
    for _ in range(b_rank):
        bm = {}
        for g, ix in zip(gl, grp_ix):
            bm[g] = M[rng.choice(ix, size=len(ix), replace=True)].mean(axis=0)
        orders = [[gl[i] for i in np.argsort([-bm[g][j] for g in gl], kind="stable")] for j in range(J)]
        same_all += all(o == orders[0] for o in orders)
        for j in range(J):
            match_cons[j] += orders[j] == cons_order
        for a, b in pairs:
            signs = {np.sign(bm[a][j] - bm[b][j]) for j in range(J)}
            if len(signs) == 1 and list(signs)[0] == np.sign(cons[a] - cons[b]):
                pair_agree[f"{a}>{b}"] += 1
    d["rank_stability"] = {
        "point_order_by_judge": point_order, "consensus_order_mean_over_judges": cons_order,
        "target_means_rep_avg_by_judge": {g: {judges[j]: float(mu[g][j]) for j in range(J)} for g in gl},
        "n_per_target": {g: int(np.sum(tg == g)) for g in gl},
        "P_all_judges_same_order": same_all / b_rank,
        "P_judge_order_equals_consensus": {judges[j]: float(match_cons[j] / b_rank) for j in range(J)},
        "P_pairwise_sign_agrees_across_all_judges": {k: v / b_rank for k, v in pair_agree.items()},
        "B": b_rank}
    val = {"n_positive": int(labels.sum()), "n_negative": int(len(labels) - labels.sum())}
    if 0 < labels.sum() < len(labels):
        val["auc_by_judge"] = {judges[j]: float(auc(M[:, j], labels)) for j in range(J)}
        val["auc_by_judge_mean_of_judges"] = float(auc(M.mean(axis=1), labels))
    d["validity_vs_planted_label"] = val
    return d
