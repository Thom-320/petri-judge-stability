"""Confirmatory tests H1' and H2' (pre-registration, Session 2): fixed judges, design-based.

The judges in these tests are FIXED (the three Petri 2.0 facets). Inference is over transcripts
only: a transcript bootstrap stratified by target, which is valid for fixed judges. Nothing here
uses the variance-component model.

H1' (calibration vs ranking). For each judge pair (j, k) and target contrast (A, B):
    D = |mu_j - mu_k| - |Delta_j(A, B) - Delta_k(A, B)|
  mu_j is judge j's calibration level, the unweighted mean of its target means (repeats averaged);
  Delta_j(A, B) is judge j's target gap. D > 0: the judges differ more in level than in the
  contrast. Test statistic per dimension: the mean of D over all pair x contrast cells.

H2' (threshold vs contrast flips under a judge swap), per dimension and cut-off c, transcripts
fixed, one judge and one repeat per panel (J = 1, R = 1), averaged over judge pairs and all repeat
pairings (r, r'):
  primary, target level (Petri's metric is the per-dimension mean over samples):
    threshold flip  FT_c = mean_g 1[(m_gjr >= c) != (m_gkr' >= c)],  m_gjr = target g's mean score
    contrast flip   FC   = mean over target pairs (A, B) of |sign(m_Ajr - m_Bjr) - sign(m_Akr' - m_Bkr')| / 2
    The point value on the observed transcripts is coarse (a few binary comparisons); the reported
    estimate is its mean over the stratified transcript bootstrap, i.e. the judge-swap flip
    probability under transcript resampling, and the bootstrap gives its CI and p-value.
  secondary, transcript level (Petri's per-transcript ScoreBadge flag):
    FT_c = mean_t 1[(X_tjr >= c) != (X_tkr' >= c)]
    FC   = mean over target pairs (A, B), a in A, b in B of |sign(X_ajr - X_bjr) - sign(X_akr' - X_bkr')| / 2
  A tie against a strict order counts as half a flip, which makes FC symmetric in A and B.
  Test statistic: FT_c - FC. The same quantities within one judge (repeat r vs r') are reported
  as the repeat baseline, not tested.

Multiplicity: one-sided bootstrap p-values, Holm across the named confirmatory family.
"""
import itertools

import numpy as np

PETRI_CUTOFFS = (4, 7)  # Petri viewer ScoreBadge.svelte at f02b3ec: >= 7 'score-high', >= 4 'score-medium'
DESCRIPTIVE_CUTOFFS = (2, 3, 5, 6, 8, 9)  # the rest of the scale, reported as a curve FT(c), never tested
B_CONFIRM = 2000
ALPHA = 0.05
H1_SHARE = 2 / 3


def _pairs(J, judge_idx=None):
    idx = list(range(J)) if judge_idx is None else list(judge_idx)
    return list(itertools.combinations(idx, 2))


# ---------------------------------------------------------------- H1'
def h1_cells(Y, groups, gl, judge_idx=None):
    """D for every judge pair x target contrast. Y: n x J x R."""
    groups = np.asarray(groups)
    M = np.array([Y[groups == g].mean(axis=(0, 2)) for g in gl])  # G x J target means per judge
    mu = M.mean(axis=0)
    cells = {}
    for j, k in _pairs(Y.shape[1], judge_idx):
        for ia, ib in itertools.combinations(range(len(gl)), 2):
            dj, dk = M[ia, j] - M[ib, j], M[ia, k] - M[ib, k]
            cells[(j, k, gl[ia], gl[ib])] = {"calibration_offset": abs(mu[j] - mu[k]),
                                             "contrast_discrepancy": abs(dj - dk),
                                             "D": abs(mu[j] - mu[k]) - abs(dj - dk)}
    return cells


# ---------------------------------------------------------------- H2'
def _flag_flip_vectors(Y, c, pairs):
    """Per transcript: mean over judge pairs and repeat pairings of the threshold flip indicator,
    and the within-judge repeat baseline."""
    n, J, R = Y.shape
    F = Y >= c
    swap = np.zeros(n)
    m = 0
    for j, k in pairs:
        for r in range(R):
            for r2 in range(R):
                swap += F[:, j, r] != F[:, k, r2]
                m += 1
    rep = np.zeros(n)
    mr = 0
    js = sorted({x for p in pairs for x in p})
    for j in js:
        for r, r2 in itertools.combinations(range(R), 2):
            rep += F[:, j, r] != F[:, j, r2]
            mr += 1
    return swap / max(m, 1), (rep / mr if mr else np.full(n, np.nan))


def _contrast_flip_matrices(YA, YB, pairs):
    """nA x nB matrices: mean over judge pairs and repeat pairings of |sign_j - sign_k| / 2, and the
    within-judge repeat baseline."""
    nA, J, R = YA.shape
    S = np.sign(YA[:, None, :, :] - YB[None, :, :, :])  # nA x nB x J x R
    swap = np.zeros((nA, YB.shape[0]))
    m = 0
    for j, k in pairs:
        for r in range(R):
            for r2 in range(R):
                swap += np.abs(S[:, :, j, r] - S[:, :, k, r2]) / 2
                m += 1
    rep = np.zeros_like(swap)
    mr = 0
    for j in sorted({x for p in pairs for x in p}):
        for r, r2 in itertools.combinations(range(R), 2):
            rep += np.abs(S[:, :, j, r] - S[:, :, j, r2]) / 2
            mr += 1
    return swap / max(m, 1), (rep / mr if mr else np.full_like(swap, np.nan))


class _H2:
    """Precomputed per-transcript / per-transcript-pair flip contributions, so each bootstrap draw
    is a weighted mean."""

    def __init__(self, Y, groups, gl, cutoffs, judge_idx=None):
        groups = np.asarray(groups)
        self.gl = gl
        self.idx = {g: np.where(groups == g)[0] for g in gl}
        pairs = _pairs(Y.shape[1], judge_idx)
        self.ft = {c: _flag_flip_vectors(Y, c, pairs) for c in cutoffs}
        self.fc = {}
        for a, b in itertools.combinations(gl, 2):
            self.fc[(a, b)] = _contrast_flip_matrices(Y[self.idx[a]], Y[self.idx[b]], pairs)
        self.n = len(groups)

    def stats(self, w=None):
        """w: dict group -> weight vector over that group's transcripts (bootstrap counts)."""
        w = w or {g: np.ones(len(ix)) for g, ix in self.idx.items()}
        allw = np.zeros(self.n)
        for g, ix in self.idx.items():
            np.add.at(allw, ix, w[g])
        fc_swap, fc_rep = [], []
        for (a, b), (sw, rp) in self.fc.items():
            den = w[a].sum() * w[b].sum()
            fc_swap.append(w[a] @ sw @ w[b] / den)
            fc_rep.append(w[a] @ rp @ w[b] / den)
        out = {"FC": float(np.mean(fc_swap)), "FC_repeat": float(np.mean(fc_rep))}
        for c, (sw, rp) in self.ft.items():
            out[f"FT_{c}"] = float(allw @ sw / allw.sum())
            out[f"FT_{c}_repeat"] = float(allw @ rp / allw.sum())
            out[f"diff_{c}"] = out[f"FT_{c}"] - out["FC"]
        return out


def target_level_flips(Y, groups, gl, cutoffs, judge_idx=None):
    """Target-level judge-swap flip rates (and the within-judge repeat baseline) on one sample."""
    groups = np.asarray(groups)
    n, J, R = Y.shape
    pairs = _pairs(J, judge_idx)
    M = np.array([Y[groups == g].mean(axis=0) for g in gl])  # G x J x R
    tp = list(itertools.combinations(range(len(gl)), 2))
    out = {}
    sw, rp = [], []
    for j, k in pairs:
        for r in range(R):
            for r2 in range(R):
                sw += [abs(np.sign(M[a, j, r] - M[b, j, r]) - np.sign(M[a, k, r2] - M[b, k, r2])) / 2 for a, b in tp]
    js = sorted({x for p in pairs for x in p})
    for j in js:
        for r, r2 in itertools.combinations(range(R), 2):
            rp += [abs(np.sign(M[a, j, r] - M[b, j, r]) - np.sign(M[a, j, r2] - M[b, j, r2])) / 2 for a, b in tp]
    out["FC"], out["FC_repeat"] = float(np.mean(sw)), (float(np.mean(rp)) if rp else np.nan)
    for c in cutoffs:
        F = M >= c
        sw = [F[g, j, r] != F[g, k, r2] for j, k in pairs for r in range(R) for r2 in range(R) for g in range(len(gl))]
        rp = [F[g, j, r] != F[g, j, r2] for j in js for r, r2 in itertools.combinations(range(R), 2) for g in range(len(gl))]
        out[f"FT_{c}"] = float(np.mean(sw))
        out[f"FT_{c}_repeat"] = float(np.mean(rp)) if rp else np.nan
        out[f"diff_{c}"] = out[f"FT_{c}"] - out["FC"]
    return out


# ---------------------------------------------------------------- bootstrap, p-values, Holm
def holm(pvals):
    """Holm step-down adjusted p-values for a dict name -> p."""
    names = sorted(pvals, key=lambda k: pvals[k])
    m = len(names)
    adj, run = {}, 0.0
    for i, k in enumerate(names):
        run = max(run, min(1.0, (m - i) * pvals[k]))
        adj[k] = run
    return adj


def one_sided_p(boot):
    """Bootstrap p-value for H0: theta <= 0 against theta > 0: share of draws <= 0, with the +1 rule."""
    boot = np.asarray(boot, float)
    boot = boot[np.isfinite(boot)]
    return float((1 + np.sum(boot <= 0)) / (len(boot) + 1))


def _ci(v):
    v = np.asarray(v, float)
    return [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]


def confirm_dim(Y, groups, gl, rng, cutoffs=PETRI_CUTOFFS, judge_idx=None, B=B_CONFIRM,
                desc_cutoffs=DESCRIPTIVE_CUTOFFS):
    """H1' and H2' (target level, primary; transcript level, secondary) for one dimension, with
    stratified transcript-bootstrap CIs and one-sided p-values (unadjusted). p-values are computed
    for `cutoffs` only; `desc_cutoffs` add the descriptive FT(c) curve."""
    groups = np.asarray(groups)
    allc = tuple(sorted(set(cutoffs) | set(desc_cutoffs)))
    cells = h1_cells(Y, groups, gl, judge_idx)
    h2 = _H2(Y, groups, gl, allc, judge_idx)
    point_item = h2.stats()
    point_target = target_level_flips(Y, groups, gl, allc, judge_idx)
    keys = list(cells)
    bootD, boot_item, boot_target = [], [], []
    idx = {g: np.where(groups == g)[0] for g in gl}
    for _ in range(B):
        draw = {g: rng.choice(len(ix), len(ix), replace=True) for g, ix in idx.items()}
        ix = np.concatenate([idx[g][draw[g]] for g in gl])
        cb = h1_cells(Y[ix], groups[ix], gl, judge_idx)
        bootD.append([cb[k]["D"] for k in keys])
        w = {g: np.bincount(draw[g], minlength=len(idx[g])).astype(float) for g in gl}
        boot_item.append(h2.stats(w))
        boot_target.append(target_level_flips(Y[ix], groups[ix], gl, allc, judge_idx))
    bootD = np.array(bootD)
    cell_out = {}
    for i, k in enumerate(keys):
        lo, hi = _ci(bootD[:, i])
        cell_out[f"{k[0]}-{k[1]}|{k[2]}|{k[3]}"] = {**{x: float(v) for x, v in cells[k].items()},
                                                   "D_ci95": [lo, hi], "lower_bound_above_0": lo > 0}
    meanD = float(np.mean([c["D"] for c in cells.values()]))
    meanD_boot = bootD.mean(axis=1)
    share = float(np.mean([c["lower_bound_above_0"] for c in cell_out.values()]))
    h1 = {"cells": cell_out, "mean_D": meanD, "mean_D_ci95": _ci(meanD_boot),
          "p_one_sided": one_sided_p(meanD_boot), "share_cells_lower_bound_above_0": share,
          "share_rule": H1_SHARE, "share_rule_met": share >= H1_SHARE - 1e-12}

    def summarize(point, boot, estimate_is_boot_mean):
        o = {"point_observed": point, "estimate": {}, "ci95": {}, "p_one_sided": {}}
        for k in point:
            v = [b[k] for b in boot]
            o["estimate"][k] = float(np.nanmean(v)) if estimate_is_boot_mean else point[k]
            o["ci95"][k] = _ci(v)
        for c in cutoffs:
            o["p_one_sided"][str(c)] = one_sided_p([b[f"diff_{c}"] for b in boot])
        return o
    return {"H1": h1, "H2": summarize(point_target, boot_target, True),
            "H2_transcript_level": summarize(point_item, boot_item, False),
            "B": B, "judge_idx": list(judge_idx) if judge_idx is not None else None}


def family(results, confirm_dims, cutoffs=PETRI_CUTOFFS, alpha=ALPHA):
    """Holm across the confirmatory family: H1' per confirmatory dimension and H2' per
    confirmatory dimension x cut-off. results: dim -> confirm_dim output."""
    p = {}
    for d in confirm_dims:
        if d not in results:
            continue
        p[f"H1|{d}"] = results[d]["H1"]["p_one_sided"]
        for c in cutoffs:
            p[f"H2|{d}|c={c}"] = results[d]["H2"]["p_one_sided"][str(c)]
    adj = holm(p)
    out = {}
    for k, v in p.items():
        rej = adj[k] < alpha
        row = {"p": v, "p_holm": adj[k], "rejected_at_alpha": rej}
        if k.startswith("H1|"):
            d = k.split("|")[1]
            row["share_rule_met"] = results[d]["H1"]["share_rule_met"]
            row["supported"] = bool(rej and row["share_rule_met"])
        else:
            row["supported"] = bool(rej)
        out[k] = row
    return {"alpha": alpha, "method": "Holm", "m": len(p), "tests": out}
