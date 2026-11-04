"""Decision stability: nested G-study, flip probability phi, decision-level D-study, controls.

Score model (SPEC-v2), transcripts t nested in groups g (targets), crossed with judges j,
repeats r nested in transcript x judge cells:
    X_gtjr = mu + a_g + t_{t:g} + c_j + (ac)_gj + (tc)_{tj:g} + e_{gtjr}
Variance components are estimated by ANOVA / expected mean squares (method of moments), with
transcript-level components estimated separately per group (no homogeneity assumption):
  within group h (balanced n_h x J x R):
    sigma2_e(h)  = MS_e
    sigma2_tj(h) = (MS_tj - MS_e) / R
    sigma2_t(h)  = (MS_t - MS_tj) / (J R)
  across groups, from the G x J table of group-by-judge means M_gj, whose cells carry noise
  v_g = sigma2_tj(g)/n_g + sigma2_e(g)/(n_g R) (the t:g main effect is common to a row and
  cancels in column and interaction contrasts):
    E[SS_int] = (G-1)(J-1) sigma2_gj + (J-1)(1-1/G) sum_g v_g
    E[SS_col] = G(J-1) sigma2_j + (J-1) sigma2_gj + (J-1)/G sum_g v_g
Negative estimates are truncated at 0 (reported raw as well).

Decisions and their error variance for a panel of J judges, R repeats, n_g transcripts per group:
  contrast "A > B":   Var = s_t(A)/n_A + s_t(B)/n_B + 2 s_gj/J + s_tj(A)/(n_A J) + s_tj(B)/(n_B J)
                            + s_e(A)/(n_A J R) + s_e(B)/(n_B J R)        (judge main effect cancels)
  threshold "A <= c": Var = s_t(A)/n_A + s_j/J + s_gj/J + s_tj(A)/(n_A J) + s_e(A)/(n_A J R)
                                                                        (judge main effect does not cancel)
  phi = P(D(panel) != D(panel')) for two independent panels = 2 p (1 - p), p = Phi(-|Delta| / sigma_D),
  with the plug-in Delta = observed mean difference (or mean - c).
Facets: "full" re-draws transcripts, judges and repeats; "judges" keeps the transcripts and
re-draws judges and repeats; "repeats" keeps transcripts and judges; "transcripts" keeps the judges.

Known limits (stated in the docs): with J = 3 the judge components have 2 (s_j) and
(G-1)(J-1) = 4 (s_gj) degrees of freedom; transcript-bootstrap CIs do not include judge-sampling
uncertainty, so `judge_component_ci` gives chi-square / Satterthwaite intervals for them; the
plug-in |Delta| is biased upward, so the plug-in phi is biased downward near Delta = 0 (under a
true null it averages about 1/3, not 0.5; see `placebo`).

Model-based phi reporting (pre-registration, Session 2). No estimator of phi from one Delta_hat is
unbiased everywhere: with z = |Delta|/sd, the plug-in is biased down for z < ~1.2 (-0.17 at z = 0)
and up above (+0.07 at z = 2); `phi_bc`, which replaces |Delta_hat| by
sqrt(max(Delta_hat^2 - Var(Delta_hat), 0)), is less biased near 0 (-0.075) and more above
(+0.13 at z = 1.5). Primary report: the plug-in point with `phi_interval`, a confidence interval
by inverting the normal interval for Delta; phi_bc is reported alongside. The design-based
split-half estimator (`empirical_split`) is the model check (`model_check`).
"""
import itertools

import numpy as np
from scipy.stats import chi2, norm


# ---------------------------------------------------------------- G-study
def within_group(Yh):
    n, J, R = Yh.shape
    m = Yh.mean()
    yt, yj, ytj = Yh.mean(axis=(1, 2)), Yh.mean(axis=(0, 2)), Yh.mean(axis=2)
    ss_t = J * R * np.sum((yt - m) ** 2)
    ss_tj = R * np.sum((ytj - yt[:, None] - yj[None, :] + m) ** 2)
    ss_e = np.sum((Yh - ytj[:, :, None]) ** 2)
    ms_t = ss_t / (n - 1)
    ms_tj = ss_tj / ((n - 1) * (J - 1))
    ms_e = ss_e / (n * J * (R - 1)) if R > 1 else np.nan
    s_e = ms_e
    s_tj = (ms_tj - ms_e) / R if R > 1 else ms_tj
    s_t = (ms_t - ms_tj) / (J * R)
    return {"n": n, "s_t_raw": s_t, "s_tj_raw": s_tj, "s_e": s_e,
            "s_t": max(s_t, 0.0), "s_tj": max(s_tj, 0.0), "mean": m, "judge_means": yj}


def gstudy(Y, groups, group_order=None):
    """Y: n x J x R (complete cases); groups: length-n labels. Returns variance components."""
    groups = np.asarray(groups)
    gl = group_order or sorted(set(groups.tolist()))
    gl = [g for g in gl if np.sum(groups == g) >= 2]
    n, J, R = Y.shape
    per = {g: within_group(Y[groups == g]) for g in gl}
    G = len(gl)
    M = np.array([per[g]["judge_means"] for g in gl])  # G x J
    v = np.array([per[g]["s_tj"] / per[g]["n"] + (per[g]["s_e"] if R > 1 else 0.0) / (per[g]["n"] * R) for g in gl])
    out = {"groups": gl, "J": J, "R": R, "per_group": per,
           "group_means": {g: per[g]["mean"] for g in gl}}
    if G >= 2 and J >= 2:
        rm, cm, gm = M.mean(axis=1), M.mean(axis=0), M.mean()
        ss_int = np.sum((M - rm[:, None] - cm[None, :] + gm) ** 2)
        s_gj = (ss_int - (J - 1) * (1 - 1 / G) * v.sum()) / ((G - 1) * (J - 1))
        ss_col = G * np.sum((cm - gm) ** 2)
        s_j = (ss_col / (J - 1) - max(s_gj, 0.0) - v.sum() / G) / G
        # E[MS_int] = s_gj + V/G and E[MS_col] = G s_j + s_gj + V/G, with V = sum_g v_g
        out.update({"ms_int": ss_int / ((G - 1) * (J - 1)), "ms_col": ss_col / (J - 1), "v_over_G": v.sum() / G})
    else:
        s_gj, s_j = np.nan, np.nan
    out.update({"s_gj_raw": s_gj, "s_j_raw": s_j, "s_gj": max(s_gj, 0.0) if np.isfinite(s_gj) else np.nan,
                "s_j": max(s_j, 0.0) if np.isfinite(s_j) else np.nan,
                "df_gj": (G - 1) * (J - 1), "df_j": J - 1})
    return out


# ---------------------------------------------------------------- phi
def phi_from(delta, sd):
    if sd <= 0:
        return 0.0 if delta != 0 else 0.5
    p = norm.cdf(-abs(delta) / sd)
    return float(2 * p * (1 - p))


def debias_delta(delta, var_delta_hat):
    """sqrt(max(Delta_hat^2 - Var(Delta_hat), 0)): Delta_hat^2 - Var(Delta_hat) is unbiased for Delta^2."""
    return float(np.sqrt(max(delta ** 2 - var_delta_hat, 0.0)))


def phi_bc(delta, var_delta_hat, sd):
    """Bias-corrected phi: the plug-in formula at the debiased |Delta|."""
    return phi_from(debias_delta(delta, var_delta_hat), sd)


def phi_interval(delta, var_delta_hat, sd, level=0.95):
    """Confidence interval for phi by inverting the normal interval for Delta:
    Delta in Delta_hat +- z sqrt(Var(Delta_hat)); phi is decreasing in |Delta|, so
    [phi(max |Delta| in CI), phi(min |Delta| in CI)], and the upper end is 0.5 when the CI holds 0.
    Coverage holds given sd (sigma_D) and Var(Delta_hat); their own uncertainty is not included."""
    h = norm.ppf(0.5 + level / 2) * np.sqrt(max(var_delta_hat, 0.0))
    lo_d, hi_d = delta - h, delta + h
    near = 0.0 if lo_d <= 0 <= hi_d else min(abs(lo_d), abs(hi_d))
    far = max(abs(lo_d), abs(hi_d))
    return [phi_from(far, sd), phi_from(near, sd)]


# ---------------------------------------------------------------- judge-component intervals
def _chi2_interval(est, df, level=0.95):
    a = 1 - level
    if not np.isfinite(est) or not np.isfinite(df) or df <= 0:
        return [np.nan, np.nan]
    q_lo = chi2.ppf(a / 2, df)
    hi = float(df * est / q_lo) if q_lo > 0 else np.inf  # tiny Satterthwaite df: unbounded above
    return [float(df * est / chi2.ppf(1 - a / 2, df)), hi]


def satterthwaite(coefs, ms, dfs, const=0.0, level=0.95):
    """Normal-theory interval for theta = sum_k c_k E[MS_k] - const (const treated as known).

    All c_k > 0: Satterthwaite interval for the linear combination, then shifted by const.
    Mixed signs (const must be 0): Satterthwaite on the estimate itself; if the estimate is <= 0
    its df is undefined and the interval is [0, upper of the positive part]. Truncated at 0."""
    coefs, ms, dfs = (np.asarray(x, float) for x in (coefs, ms, dfs))
    terms = coefs * ms
    lin = float(terms.sum())
    if np.all(coefs > 0):
        nu = lin ** 2 / float(np.sum(terms ** 2 / dfs)) if lin > 0 else np.nan
        lo, hi = _chi2_interval(lin, nu, level) if lin > 0 else (0.0, 0.0)
        return {"estimate": lin - const, "df": nu, "ci": [max(lo - const, 0.0), max(hi - const, 0.0)]}
    if const:
        raise ValueError("const is only supported for positive coefficients")
    if lin > 0:
        nu = lin ** 2 / float(np.sum(terms ** 2 / dfs))
        lo, hi = _chi2_interval(lin, nu, level)
        return {"estimate": lin, "df": nu, "ci": [max(lo, 0.0), hi]}
    pos = coefs > 0
    lp = float(terms[pos].sum())
    hi = _chi2_interval(lp, lp ** 2 / float(np.sum(terms[pos] ** 2 / dfs[pos])), level)[1] if lp > 0 else 0.0
    return {"estimate": lin, "df": np.nan, "ci": [0.0, float(hi)]}


def judge_component_ci(gs, level=0.95):
    """Chi-square / Satterthwaite intervals for the judge components, which the transcript
    bootstrap does not cover. Treats V (the transcript-level noise in the G x J table) as known.
      s_gj        = MS_int - V/G                       df_int = (G-1)(J-1)
      s_j         = (MS_col - MS_int) / G              Satterthwaite
      s_j + s_gj  = MS_col/G + (G-1)/G MS_int - V/G    Satterthwaite (threshold decisions)"""
    if "ms_int" not in gs:
        return {}
    G, J = len(gs["groups"]), gs["J"]
    df_i, df_c = (G - 1) * (J - 1), J - 1
    mi, mc, vg = gs["ms_int"], gs["ms_col"], gs["v_over_G"]
    return {
        "level": level,
        "s_gj": satterthwaite([1.0], [mi], [df_i], const=vg, level=level),
        "s_j": satterthwaite([1 / G, -1 / G], [mc, mi], [df_c, df_i], level=level),
        "s_j_plus_s_gj": satterthwaite([1 / G, (G - 1) / G], [mc, mi], [df_c, df_i], const=vg, level=level),
        "df_int": df_i, "df_col": df_c,
        "note": "normal-theory intervals; with J = 3 they are very wide (df 2 and 4)",
    }


def pair_gj(gs, a, b):
    """Pair-specific target x judge variance from the J per-judge differences d_j = M_aj - M_bj:
    E[var_j(d_j)] = 2 s_gj + v_a + v_b  (J - 1 degrees of freedom; a sensitivity check on the pooled s_gj)."""
    A, B = gs["per_group"][a], gs["per_group"][b]
    J, R = gs["J"], gs["R"]
    if J < 2:
        return np.nan
    d = np.asarray(A["judge_means"]) - np.asarray(B["judge_means"])
    ve = lambda P: P["s_tj"] / P["n"] + (P["s_e"] if R > 1 else 0.0) / (P["n"] * R)  # noqa: E731
    return max((np.var(d, ddof=1) - ve(A) - ve(B)) / 2, 0.0)


def contrast_var(gs, a, b, J=None, R=None, n_a=None, n_b=None, facet="full", s_gj=None):
    J = J or gs["J"]
    R = R or gs["R"]
    A, B = gs["per_group"][a], gs["per_group"][b]
    n_a = n_a or A["n"]
    n_b = n_b or B["n"]
    s_eA = A["s_e"] if np.isfinite(A["s_e"]) else 0.0
    s_eB = B["s_e"] if np.isfinite(B["s_e"]) else 0.0
    t = A["s_t"] / n_a + B["s_t"] / n_b
    gj = 2 * (gs["s_gj"] if s_gj is None else s_gj) / J
    tj = A["s_tj"] / (n_a * J) + B["s_tj"] / (n_b * J)
    e = s_eA / (n_a * J * R) + s_eB / (n_b * J * R)
    return {"full": t + gj + tj + e, "judges": gj + tj + e, "repeats": e, "transcripts": t + tj + e}[facet]


def threshold_var(gs, a, J=None, R=None, n_a=None, facet="full"):
    J = J or gs["J"]
    R = R or gs["R"]
    A = gs["per_group"][a]
    n_a = n_a or A["n"]
    s_e = A["s_e"] if np.isfinite(A["s_e"]) else 0.0
    t = A["s_t"] / n_a
    jj = (gs["s_j"] + gs["s_gj"]) / J
    tj = A["s_tj"] / (n_a * J)
    e = s_e / (n_a * J * R)
    return {"full": t + jj + tj + e, "judges": jj + tj + e, "repeats": e, "transcripts": t + tj + e}[facet]


FACETS = ("full", "judges", "repeats", "transcripts")


def decisions(Y, groups, group_order=None, thresholds=()):
    """phi for every pairwise contrast (and optional thresholds) at the observed design.

    For every facet: the plug-in `phi_<facet>` and the bias-corrected `phi_bc_<facet>` (primary),
    which uses Var(Delta_hat) = the full-facet error variance at the observed design."""
    gs = gstudy(Y, groups, group_order)
    out = {"gstudy": summarize_gstudy(gs), "contrasts": {}, "thresholds": {}}
    gl = gs["groups"]
    for a, b in itertools.combinations(gl, 2):
        delta = gs["group_means"][a] - gs["group_means"][b]
        vhat = contrast_var(gs, a, b, facet="full")
        row = {"delta": float(delta), "delta_debiased": debias_delta(delta, vhat), "var_delta_hat": float(vhat)}
        for f in FACETS:
            sd = float(np.sqrt(contrast_var(gs, a, b, facet=f)))
            row[f"sd_{f}"] = sd
            row[f"phi_{f}"] = phi_from(delta, sd)
            row[f"phi_bc_{f}"] = phi_bc(delta, vhat, sd)
            row[f"phi_ci95_{f}"] = phi_interval(delta, vhat, sd)
        row["z"] = float(abs(delta) / row["sd_full"]) if row["sd_full"] > 0 else np.inf
        sgj = pair_gj(gs, a, b)
        row["s_gj_pair"] = float(sgj)
        row["phi_full_pair_gj"] = phi_from(delta, float(np.sqrt(contrast_var(gs, a, b, s_gj=sgj))))
        row["phi_judges_pair_gj"] = phi_from(delta, float(np.sqrt(contrast_var(gs, a, b, facet="judges", s_gj=sgj))))
        out["contrasts"][f"{a}|{b}"] = row
    for c in thresholds:
        for a in gl:
            delta = gs["group_means"][a] - c
            vhat = threshold_var(gs, a, facet="full")
            row = {"delta": float(delta), "delta_debiased": debias_delta(delta, vhat), "var_delta_hat": float(vhat)}
            for f in FACETS:
                sd = float(np.sqrt(threshold_var(gs, a, facet=f)))
                row[f"phi_{f}"] = phi_from(delta, sd)
                row[f"phi_bc_{f}"] = phi_bc(delta, vhat, sd)
                row[f"phi_ci95_{f}"] = phi_interval(delta, vhat, sd)
                row[f"sd_{f}"] = sd
            out["thresholds"][f"{a}<={c}"] = row
    return out, gs


def summarize_gstudy(gs):
    return {"groups": gs["groups"], "J": gs["J"], "R": gs["R"],
            "s_gj": float(gs["s_gj"]), "s_gj_raw": float(gs["s_gj_raw"]),
            "s_j": float(gs["s_j"]), "s_j_raw": float(gs["s_j_raw"]),
            "df_gj": gs["df_gj"], "df_j": gs["df_j"],
            "judge_component_ci95": judge_component_ci(gs),
            "per_group": {g: {k: (float(v) if k not in ("judge_means",) else [float(x) for x in v])
                              for k, v in p.items()} for g, p in gs["per_group"].items()}}


# ---------------------------------------------------------------- D-study
D_J = (1, 2, 3, 4, 6, 8)
D_R = (1, 2, 3)
D_N = (10, 20, 40, 65, 100, 200, 400, 1000)
EPS = (0.05, 0.10)


def dstudy_contrast(gs, a, b, Js=D_J, Rs=D_R, Ns=D_N, eps=EPS):
    """phi over a grid of (J, R, n per group). Cheapest design (J*R*2n calls) reaching each eps,
    with the plug-in |Delta| (`cheapest`) and with the debiased |Delta| (`cheapest_bc`).
    Model-based extrapolation: J beyond the observed panel assumes judges are a random sample."""
    delta = gs["group_means"][a] - gs["group_means"][b]
    d_bc = debias_delta(delta, contrast_var(gs, a, b))
    grid = []
    for J in Js:
        for R in Rs:
            for n in Ns:
                sd = np.sqrt(contrast_var(gs, a, b, J=J, R=R, n_a=n, n_b=n))
                grid.append({"J": J, "R": R, "n": n, "calls": J * R * 2 * n, "phi": phi_from(delta, sd),
                             "phi_bc": phi_from(d_bc, sd)})
    best, best_bc = {}, {}
    for e in eps:
        for key, store in (("phi", best), ("phi_bc", best_bc)):
            ok = [g for g in grid if g[key] <= e]
            store[str(e)] = min(ok, key=lambda g: (g["calls"], g["J"])) if ok else None
    # limits: infinitely many transcripts (judge floor) and infinitely many judges (transcript floor)
    lim = {str(J): phi_from(delta, np.sqrt(2 * gs["s_gj"] / J)) for J in Js}
    lim_bc = {str(J): phi_from(d_bc, np.sqrt(2 * gs["s_gj"] / J)) for J in Js}
    return {"delta": float(delta), "delta_debiased": d_bc, "grid": grid, "cheapest": best, "cheapest_bc": best_bc,
            "phi_limit_n_infinite_by_J": lim, "phi_bc_limit_n_infinite_by_J": lim_bc}


def floor_bound(gs, Js=(1, 3), thresholds=(), level=0.95):
    """H3': the judge floor (n -> infinity) of phi for every contrast and threshold decision.
      contrast:  sigma_D^2 = 2 s_gj / J        threshold: sigma_D^2 = (s_j + s_gj) / J
    Point: phi at the plug-in |Delta| and the point component (phi_bc reported alongside).
    Bound: phi is increasing in sigma_D and decreasing in |Delta|, so the bound is
    [phi(far end of the Delta interval, lower component), phi(near end, upper component)], with
    each interval at 1 - (1 - level)/2 (Bonferroni), so the joint coverage is at least `level`
    under the normal-theory model. A model-based bound, not a test. Random-judge extrapolation."""
    each = 1 - (1 - level) / 2
    ci = judge_component_ci(gs, each)
    if not ci:
        return {}
    out = {"level": level, "level_each_interval": each, "contrasts": {}, "thresholds": {}}
    gl = gs["groups"]

    def row(delta, vhat, comp, mult):
        h = norm.ppf(0.5 + each / 2) * np.sqrt(vhat)
        lo_d, hi_d = delta - h, delta + h
        near = 0.0 if lo_d <= 0 <= hi_d else min(abs(lo_d), abs(hi_d))
        far = max(abs(lo_d), abs(hi_d))
        r = {}
        for J in Js:
            f = lambda d, s: phi_from(d, np.sqrt(mult * max(s, 0.0) / J))  # noqa: E731
            r[str(J)] = {"point": f(delta, comp["estimate"]), "point_bc": f(debias_delta(delta, vhat), comp["estimate"]),
                         "bound": [f(far, comp["ci"][0]), f(near, comp["ci"][1])]}
        return r
    for a, b in itertools.combinations(gl, 2):
        delta = gs["group_means"][a] - gs["group_means"][b]
        out["contrasts"][f"{a}|{b}"] = {"delta": float(delta), "component": "s_gj",
                                        "by_J": row(delta, contrast_var(gs, a, b), ci["s_gj"], 2.0)}
    for c in thresholds:
        for a in gl:
            delta = gs["group_means"][a] - c
            out["thresholds"][f"{a}<={c}"] = {"delta": float(delta), "component": "s_j + s_gj",
                                              "by_J": row(delta, threshold_var(gs, a), ci["s_j_plus_s_gj"], 1.0)}
    return out


# ---------------------------------------------------------------- empirical check and controls
def empirical_split(Y, groups, a, b, rng, draws=2000):
    """Design-based flip rate: two disjoint transcript halves, two different judges, two repeats.

    Each 'panel' is J=1, R=1 on half of each group's transcripts. Over repeated sampling the two
    halves (and two distinct judges drawn from the judge universe) are independent panels, so the
    split average is an unbiased but noisy estimate of the true phi at (J=1, R=1, n/2), with no
    plug-in bias. Given one dataset it can exceed 0.5 when the sample gap is near 0, because the two
    halves are anti-correlated around the full-sample mean. The model's phi at the same design is
    returned as `phi_model_J1R1_half` for comparison."""
    groups = np.asarray(groups)
    ia, ib = np.where(groups == a)[0], np.where(groups == b)[0]
    n, J, R = Y.shape
    flips = 0
    for _ in range(draws):
        pa, pb = rng.permutation(ia), rng.permutation(ib)
        ha, hb = len(pa) // 2, len(pb) // 2
        j1, j2 = rng.choice(J, 2, replace=False) if J > 1 else (0, 0)
        r1, r2 = (rng.choice(R, 2, replace=False) if R > 1 else (0, 0))
        d1 = Y[pa[:ha], j1, r1].mean() - Y[pb[:hb], j1, r1].mean()
        d2 = Y[pa[ha:2 * ha], j2, r2].mean() - Y[pb[hb:2 * hb], j2, r2].mean()
        flips += np.sign(d1) != np.sign(d2)
    gs = gstudy(Y, groups)
    delta = gs["group_means"][a] - gs["group_means"][b]
    sd = np.sqrt(contrast_var(gs, a, b, J=1, R=1, n_a=len(ia) // 2, n_b=len(ib) // 2))
    sd_p = np.sqrt(contrast_var(gs, a, b, J=1, R=1, n_a=len(ia) // 2, n_b=len(ib) // 2, s_gj=pair_gj(gs, a, b)))
    vhat = contrast_var(gs, a, b)
    return {"phi_empirical": flips / draws, "phi_model_J1R1_half": phi_from(delta, sd),
            "phi_bc_model_J1R1_half": phi_bc(delta, vhat, sd),
            "phi_model_J1R1_half_pair_gj": phi_from(delta, sd_p), "draws": draws}


MODEL_CHECK_TOLERANCE = 0.05


def model_check(splits, tol=MODEL_CHECK_TOLERANCE):
    """Pre-registered pass rule for the variance-component model, at the matched design
    (J=1, R=1, n/2 per target), averaged over the confirmatory contrast decisions:

        mean(plug-in phi) - tol  <=  mean(split-half phi)  <=  mean(phi_bc) + tol

    The split-half estimator is design-based and unbiased for phi at that design. No single-Delta_hat
    estimator of phi is unbiased: the plug-in is biased down near Delta = 0 and up for |Delta|/sigma
    above ~1.2, the bias-corrected phi_bc the other way round, so the two bracket the truth on
    average and the rule tests the model, not the choice of point estimator. Under a true model
    with this study's sizes (simulation in tests/test_phi.py and docs) the rule passes in ~95% of
    datasets; a symmetric +-0.05 rule on either point estimator passes in only ~70-76%.
    Per-decision differences are reported, not tested (a single split-half is noisy)."""
    if not splits:
        return {"tolerance": tol, "n_decisions": 0, "passed": False}
    sp = float(np.mean([v["phi_empirical"] for v in splits.values()]))
    pl = float(np.mean([v["phi_model_J1R1_half"] for v in splits.values()]))
    bc = float(np.mean([v["phi_bc_model_J1R1_half"] for v in splits.values()]))
    return {"tolerance": tol, "n_decisions": len(splits), "mean_split_half": sp,
            "mean_plugin_model": pl, "mean_bc_model": bc,
            "mean_diff_plugin_minus_split": pl - sp, "mean_diff_bc_minus_split": bc - sp,
            "per_decision": {k: {"split": v["phi_empirical"], "plugin": v["phi_model_J1R1_half"],
                                 "bc": v["phi_bc_model_J1R1_half"]} for k, v in splits.items()},
            "passed": bool(pl - tol <= sp <= bc + tol)}


def placebo(Y, groups, rng, perms=500, draws=200):
    """Permute group labels across transcripts (group sizes kept): every true gap is 0, true phi = 0.5.

    Reports the plug-in phi (expected ~1/3 under a true null, because |Delta_hat| > 0), the share of
    permutations with plug-in phi < 0.1 (spurious 'stable' decisions), and the empirical split-half
    flip rate (expected ~0.5)."""
    groups = np.asarray(groups)
    gl = sorted(set(groups.tolist()))
    pairs = list(itertools.combinations(gl, 2))
    plug, bc, emp = [], [], []
    for k in range(perms):
        pg = rng.permutation(groups)
        res, gs = decisions(Y, pg, gl)
        plug.extend(r["phi_full"] for r in res["contrasts"].values())
        bc.extend(r["phi_bc_full"] for r in res["contrasts"].values())
        if k < max(1, perms // 10):
            for a, b in pairs:
                emp.append(empirical_split(Y, pg, a, b, rng, draws)["phi_empirical"])
    plug, bc = np.array(plug), np.array(bc)
    return {"perms": perms, "plugin_phi_mean": float(plug.mean()),
            "bc_phi_mean": float(bc.mean()), "share_bc_phi_below_0.1": float(np.mean(bc < 0.1)),
            "plugin_phi_median": float(np.median(plug)),
            "share_plugin_phi_below_0.1": float(np.mean(plug < 0.1)),
            "empirical_split_phi_mean": float(np.mean(emp)), "empirical_perms": len(emp),
            "expected": {"true_phi": 0.5, "plugin_mean_under_normal_null": 1 / 3,
                         "share_below_0.1_under_normal_null": 0.105}}


def bootstrap(Y, groups, rng, B=1000, group_order=None, thresholds=()):
    """Transcript bootstrap stratified by group: CIs for variance components and every phi."""
    groups = np.asarray(groups)
    gl = group_order or sorted(set(groups.tolist()))
    idx = {g: np.where(groups == g)[0] for g in gl}
    keys, vals = None, []
    for _ in range(B):
        ix = np.concatenate([rng.choice(idx[g], len(idx[g]), replace=True) for g in gl])
        res, gs = decisions(Y[ix], groups[ix], gl, thresholds)
        flat = {"s_gj": gs["s_gj"], "s_j": gs["s_j"]}
        for g in gl:
            for c in ("s_t", "s_tj", "s_e"):
                flat[f"{c}[{g}]"] = gs["per_group"][g][c]
        for k, r in res["contrasts"].items():
            for f in FACETS:
                flat[f"phi_{f}[{k}]"] = r[f"phi_{f}"]
                flat[f"phi_bc_{f}[{k}]"] = r[f"phi_bc_{f}"]
            flat[f"phi_full_pair_gj[{k}]"] = r["phi_full_pair_gj"]
            flat[f"delta[{k}]"] = r["delta"]
        for k, r in res["thresholds"].items():
            flat[f"phi_full[{k}]"] = r["phi_full"]
            flat[f"phi_bc_full[{k}]"] = r["phi_bc_full"]
            flat[f"phi_bc_judges[{k}]"] = r["phi_bc_judges"]
        keys = keys or list(flat)
        vals.append([flat[k] for k in keys])
    V = np.array(vals, float)
    return {k: [float(np.nanpercentile(V[:, i], 2.5)), float(np.nanpercentile(V[:, i], 97.5))]
            for i, k in enumerate(keys)}
