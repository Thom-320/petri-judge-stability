"""REML sensitivity analysis: the same score model fitted to ALL valid scores (unbalanced), not
complete cases.

    X = mu_g + c_j + (ac)_gj + t_{t:g} + (tc)_{tj:g} + e
Fixed effects: one mean per target. Random: judge c_j (s_j) and target x judge (s_gj), pooled;
transcript (s_t), transcript x judge (s_tj) and residual (s_e), separate per target, as in the
ANOVA estimator of `analysis.phi`. Fitted by restricted maximum likelihood with dense matrices and
an analytic gradient (L-BFGS-B on log-variances). Dense is fine at this study's size
(N <= ~4,200 scores per dimension); it is not meant for large data.

`gs_like` returns a dict with the keys `analysis.phi.contrast_var` / `threshold_var` read, so the
phi formulas can be re-evaluated with REML components.
"""
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize

FLOOR = 1e-6


def long_form(Y, groups):
    """n x J x R tensor with NaNs (missing) -> long arrays of the observed cells."""
    groups = np.asarray(groups)
    t, j, r = np.where(np.isfinite(Y))
    return Y[t, j, r], t, j, groups[t]


def _masks(t, j, g, gl):
    same_j = j[:, None] == j[None, :]
    same_g = g[:, None] == g[None, :]
    same_t = t[:, None] == t[None, :]
    ms = [("s_j", same_j), ("s_gj", same_j & same_g)]
    for h in gl:
        in_h = (g == h)
        ms.append((f"s_t[{h}]", same_t & in_h[:, None]))
        ms.append((f"s_tj[{h}]", same_t & same_j & in_h[:, None]))
    for h in gl:
        in_h = (g == h)
        ms.append((f"s_e[{h}]", np.diag(in_h)))
    return ms


def fit(Y, groups, group_order=None, maxiter=300):
    groups = np.asarray(groups)
    gl = group_order or sorted(set(groups.tolist()))
    y, t, j, g = long_form(Y, groups)
    keep = np.isin(g, gl)
    y, t, j, g = y[keep], t[keep], j[keep], g[keep]
    N = len(y)
    X = (g[:, None] == np.array(gl)[None, :]).astype(float)
    masks = _masks(t, j, g, gl)
    names = [m[0] for m in masks]
    Ms = [m[1].astype(float) for m in masks]
    v0 = float(np.var(y - X @ np.linalg.lstsq(X, y, rcond=None)[0]))
    eta0 = np.log(np.full(len(Ms), max(v0, 1e-3) / 4))

    def parts(eta):
        th = np.exp(eta) + FLOOR
        V = sum(a * M for a, M in zip(th, Ms))
        cf = cho_factor(V, lower=True, check_finite=False)
        Vi = cho_solve(cf, np.eye(N), check_finite=False)
        XtVi = X.T @ Vi
        A = XtVi @ X
        Ai = np.linalg.inv(A)
        P = Vi - XtVi.T @ Ai @ XtVi
        logdetV = 2 * np.sum(np.log(np.diag(cf[0])))
        logdetA = np.linalg.slogdet(A)[1]
        return th, P, logdetV, logdetA, Ai, XtVi

    def nll(eta):
        try:
            th, P, ldv, lda, _, _ = parts(eta)
        except (np.linalg.LinAlgError, ValueError):
            return 1e12, np.zeros_like(eta)
        Py = P @ y
        val = 0.5 * (ldv + lda + y @ Py)
        grad = np.array([0.5 * (np.sum(P * M) - Py @ M @ Py) for M in Ms]) * (th - FLOOR)
        return val, grad

    res = minimize(nll, eta0, jac=True, method="L-BFGS-B", options={"maxiter": maxiter})
    th, P, _, _, Ai, XtVi = parts(res.x)
    beta = Ai @ (XtVi @ y)
    comp = {n: float(v - FLOOR) for n, v in zip(names, th)}
    n_per = {h: int(len(np.unique(t[g == h]))) for h in gl}
    return {"components": comp, "target_means_gls": {h: float(b) for h, b in zip(gl, beta)},
            "n_scores": int(N), "n_transcripts": n_per, "groups": gl,
            "converged": bool(res.success), "iterations": int(res.nit), "neg_reml_loglik": float(res.fun)}


def gs_like(fitres, J, R):
    """A dict usable by analysis.phi.contrast_var / threshold_var (n = transcripts with any score)."""
    c = fitres["components"]
    per = {h: {"n": fitres["n_transcripts"][h], "s_t": c[f"s_t[{h}]"], "s_tj": c[f"s_tj[{h}]"],
               "s_e": c[f"s_e[{h}]"], "mean": fitres["target_means_gls"][h]} for h in fitres["groups"]}
    return {"groups": fitres["groups"], "J": J, "R": R, "per_group": per,
            "group_means": fitres["target_means_gls"], "s_j": c["s_j"], "s_gj": c["s_gj"]}
