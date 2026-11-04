"""Reliability analysis for the Petri-style judge pilot (Mac side, numpy/scipy/pandas/matplotlib).

Usage: python3 -I analyze.py <judgments.jsonl> <sample_meta.json> <n_transcripts> <out_dir> <tag>

Design: transcripts (n) x judges (J=3) x repeats (R=2), one score per cell per dimension.
Metrics per dimension (complete cases only):
  - ICC(2,1) inter-judge (judges as raters), repeat 1 and repeat-averaged; transcript-bootstrap 95% CI
  - Krippendorff alpha (interval) across the 3 judges (repeat 1) and across all 6 judge-repeat raters
  - Test-retest ICC(2,1) per judge (repeats as raters) and mean across judges
  - Variance components (method of moments, balanced crossed design, one obs per cell):
      transcript, judge, repeat, and 2-way interactions; 3-way interaction = residual (unreplicated design)
  - Rank stability of the three target models under judge swaps, stratified transcript bootstrap (B=2000)
  - Extra validity check: AUC of judge scores vs the planted expected-dimension labels (not a reliability metric)
"""
import collections
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

JUDG_PATH, META_PATH, N_USE, OUT_DIR, TAG = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
os.makedirs(OUT_DIR, exist_ok=True)
DIMS = ["concerning", "unprompted_deception_toward_user", "cooperation_with_human_misuse", "unfaithful_thinking"]
JUDGES = ["muse", "mimo", "deepseek"]
REPS = [1, 2]
TARGETS = ["hermes3", "deepseek_v31", "mistral_large"]
B = 2000
BOOT_CI = 1000
rng = np.random.default_rng(20261008)

meta = json.load(open(META_PATH, encoding="utf-8"))
meta_rows = sorted([r for r in meta["rows"] if r["pos"] <= N_USE], key=lambda r: r["pos"])
tids = [r["transcript_id"] for r in meta_rows]
tid_index = {t: i for i, t in enumerate(tids)}
info = {r["transcript_id"]: r for r in meta_rows}

recs = [json.loads(l) for l in open(JUDG_PATH, encoding="utf-8") if l.strip()]
recs = [r for r in recs if r.get("transcript_id") in tid_index]

# ---------------------------------------------------------------- call-level parse / refusal summary
import re  # noqa: E402

REFUSAL_RE = re.compile(r"(I (can(?:'|’)?t|cannot|won(?:'|’)?t|am unable to|'m unable to|must decline)|I'm sorry|I apologi[sz]e)", re.I)
call_summary = {}
for judge in JUDGES:
    rs = [r for r in recs if r["judge"] == judge]
    n = len(rs)
    responded = [r for r in rs if r.get("status") == "responded"]
    petri_ok = [r for r in responded if not (r["parse"]["missing"])]
    strict_ok = [r for r in responded if r["parse"]["ok"]]
    empty = [r for r in responded if not (r.get("content") or "").strip()]
    trunc = [r for r in responded if r.get("finish_reason") == "length"]
    refusal = [r for r in responded if (not r["parse"]["scores"]) and REFUSAL_RE.search(r.get("content") or "")]
    lat = [r.get("latency_s", np.nan) for r in responded]
    in_tok = [((r.get("usage") or {}).get("input_tokens") or (r.get("usage") or {}).get("prompt_tokens") or 0) for r in responded]
    out_tok = [((r.get("usage") or {}).get("output_tokens") or (r.get("usage") or {}).get("completion_tokens") or 0) for r in responded]
    call_summary[judge] = {
        "calls_logged": n, "responded": len(responded),
        "petri_equivalent_parse_ok": len(petri_ok), "strict_structure_ok": len(strict_ok),
        "scores_missing_any_dim": len(responded) - len(petri_ok),
        "empty": len(empty), "truncated_length": len(trunc), "refusal_suspect_no_scores": len(refusal),
        "http_or_transport_errors": n - len(responded),
        "latency_s_median": float(np.nanmedian(lat)) if lat else None,
        "latency_s_p90": float(np.nanpercentile(lat, 90)) if lat else None,
        "input_tokens_total": int(sum(in_tok)), "output_tokens_total": int(sum(out_tok)),
        "attempts_gt1": sum(1 for r in rs if (r.get("attempts") or 1) > 1),
        "finish_reasons": dict(collections.Counter(r.get("finish_reason") for r in responded)),
    }
    # struct failure modes
    modes = collections.Counter()
    for r in responded:
        if not r["parse"]["struct_ok"]:
            c = r.get("content") or ""
            which = [t for t in ["highlights", "summary", "scores"] if f"<{t}>" not in c or f"</{t}>" not in c]
            modes["unclosed_or_missing:" + ",".join(which)] += 1
    call_summary[judge]["structure_failure_modes"] = dict(modes)

# ---------------------------------------------------------------- score tensor per dimension
def score_tensor(dim):
    Y = np.full((len(tids), len(JUDGES), len(REPS)), np.nan)
    for r in recs:
        if r.get("status") != "responded":
            continue
        s = r["parse"]["scores"].get(dim)
        if s is None:
            continue
        i = tid_index[r["transcript_id"]]
        j = JUDGES.index(r["judge"])
        k = REPS.index(r["repeat"])
        Y[i, j, k] = s
    return Y


# ---------------------------------------------------------------- statistics
def icc21(X):
    X = np.asarray(X, float)
    n, k = X.shape
    if n < 3 or np.all(X == X.flat[0]):  # constant data: reliability undefined, not zero
        return np.nan
    g = X.mean()
    rm, cm = X.mean(axis=1), X.mean(axis=0)
    SSR = k * np.sum((rm - g) ** 2)
    SSC = n * np.sum((cm - g) ** 2)
    SST = np.sum((X - g) ** 2)
    SSE = SST - SSR - SSC
    MSR, MSC, MSE = SSR / (n - 1), SSC / (k - 1), SSE / ((n - 1) * (k - 1))
    den = MSR + (k - 1) * MSE + k * (MSC - MSE) / n
    return (MSR - MSE) / den if den > 0 else np.nan


def kalpha_interval(X):
    X = np.asarray(X, float)
    n, k = X.shape
    if np.all(X == X.flat[0]):  # constant data: undefined
        return np.nan
    N = n * k
    per_unit = 2 * k * np.sum(X ** 2, axis=1) - 2 * np.sum(X, axis=1) ** 2
    Do = np.sum(per_unit / (k - 1)) / N
    allv = X.ravel()
    De = (2 * N * np.sum(allv ** 2) - 2 * np.sum(allv) ** 2) / (N * (N - 1))
    return 1 - Do / De if De > 0 else np.nan


def varcomp(Y):
    """Method-of-moments variance components for a balanced n x J x R design (one obs per cell)."""
    n, J, R = Y.shape
    m = Y.mean()
    yt = Y.mean(axis=(1, 2)); yj = Y.mean(axis=(0, 2)); yr = Y.mean(axis=(0, 1))
    ytj = Y.mean(axis=2); ytr = Y.mean(axis=1); yjr = Y.mean(axis=0)
    SS_A = J * R * np.sum((yt - m) ** 2)
    SS_B = n * R * np.sum((yj - m) ** 2)
    SS_C = n * J * np.sum((yr - m) ** 2)
    SS_AB = R * np.sum((ytj - yt[:, None] - yj[None, :] + m) ** 2)
    SS_AC = J * np.sum((ytr - yt[:, None] - yr[None, :] + m) ** 2)
    SS_BC = n * np.sum((yjr - yj[:, None] - yr[None, :] + m) ** 2)
    SS_T = np.sum((Y - m) ** 2)
    SS_ABC = SS_T - SS_A - SS_B - SS_C - SS_AB - SS_AC - SS_BC
    df = {"A": n - 1, "B": J - 1, "C": R - 1, "AB": (n - 1) * (J - 1), "AC": (n - 1) * (R - 1),
          "BC": (J - 1) * (R - 1), "ABC": (n - 1) * (J - 1) * (R - 1)}
    MS = {"A": SS_A / df["A"], "B": SS_B / df["B"], "C": SS_C / df["C"], "AB": SS_AB / df["AB"],
          "AC": SS_AC / df["AC"], "BC": SS_BC / df["BC"], "ABC": SS_ABC / df["ABC"]}
    s_abc = MS["ABC"]
    s_ab = (MS["AB"] - s_abc) / R
    s_ac = (MS["AC"] - s_abc) / J
    s_bc = (MS["BC"] - s_abc) / n
    s_a = (MS["A"] - MS["AB"] - MS["AC"] + s_abc) / (J * R)
    s_b = (MS["B"] - MS["AB"] - MS["BC"] + s_abc) / (n * R)
    s_c = (MS["C"] - MS["AC"] - MS["BC"] + s_abc) / (n * J)
    raw = {"transcript": s_a, "judge": s_b, "repeat": s_c, "transcript_x_judge": s_ab,
           "transcript_x_repeat": s_ac, "judge_x_repeat": s_bc, "residual_3way": s_abc}
    pos = {k: max(v, 0.0) for k, v in raw.items()}
    tot = sum(pos.values())
    shares = {k: (v / tot if tot > 0 else np.nan) for k, v in pos.items()}
    return raw, shares


def auc(scores, labels):
    scores, labels = np.asarray(scores, float), np.asarray(labels, int)
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    u = stats.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return u / (len(pos) * len(neg))


def stratified_idx(rs_groups):
    out = []
    for idx in rs_groups:
        out.append(rng.choice(idx, size=len(idx), replace=True))
    return np.concatenate(out)


results = {"tag": TAG, "n_transcripts_in_sample": len(tids), "call_summary": call_summary, "dims": {}}

# transcript groups by target for stratified bootstrap
tgt_of = np.array([info[t]["target"] for t in tids])
group_idx = {g: np.where(tgt_of == g)[0] for g in TARGETS if np.any(tgt_of == g)}
present_targets = list(group_idx.keys())

fig_rows = {}
for dim in DIMS:
    Y_all = score_tensor(dim)
    complete = ~np.any(np.isnan(Y_all), axis=(1, 2))
    Y = Y_all[complete]
    tg = tgt_of[complete]
    d = {"n_complete_transcripts": int(complete.sum()),
         "n_excluded_incomplete": int((~complete).sum()),
         "n_transcripts_with_any_score": int(np.sum(~np.all(np.isnan(Y_all), axis=(1, 2))))}
    n = Y.shape[0]
    if n < 4:
        d["note"] = "too few complete transcripts"
        results["dims"][dim] = d
        continue
    # score distribution
    d["score_mean_by_judge_rep1"] = {JUDGES[j]: float(np.mean(Y[:, j, 0])) for j in range(3)}
    d["score_sd_by_judge_rep1"] = {JUDGES[j]: float(np.std(Y[:, j, 0], ddof=1)) for j in range(3)}
    d["n_distinct_values_all"] = int(len(np.unique(Y)))
    # 1) inter-judge agreement
    X1 = Y[:, :, 0]
    XA = Y.mean(axis=2)
    d["icc21_interjudge_rep1"] = float(icc21(X1))
    d["icc21_interjudge_repavg"] = float(icc21(XA))
    d["kalpha_interjudge_rep1"] = float(kalpha_interval(X1))
    d["kalpha_all6_raters"] = float(kalpha_interval(Y.reshape(n, -1)))
    # 2) test-retest per judge
    tr = {}
    for j in range(3):
        tr[JUDGES[j]] = {"icc21": float(icc21(Y[:, j, :])),
                         "pearson_r": float(np.corrcoef(Y[:, j, 0], Y[:, j, 1])[0, 1]) if np.std(Y[:, j, :]) > 0 else np.nan,
                         "exact_agreement": float(np.mean(Y[:, j, 0] == Y[:, j, 1]))}
    d["test_retest"] = tr
    d["test_retest_icc21_mean_over_judges"] = float(np.nanmean([tr[j]["icc21"] for j in JUDGES]))
    # 3) variance components
    raw, shares = varcomp(Y)
    d["varcomp_raw"] = {k: float(v) for k, v in raw.items()}
    d["varcomp_share"] = {k: float(v) for k, v in shares.items()}
    # bootstrap CIs (transcript resampling, unstratified) for ICC and alpha and transcript share
    bi, ba, bs = [], [], []
    for _ in range(BOOT_CI):
        ix = rng.integers(0, n, n)
        bi.append(icc21(X1[ix]))
        ba.append(kalpha_interval(X1[ix]))
        rr, sh = varcomp(Y[ix])
        bs.append(sh["transcript"] if not np.isnan(sh["transcript"]) else np.nan)
    ci = lambda v: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]  # noqa: E731
    d["boot_ci95"] = {"icc21_interjudge_rep1": ci(bi), "kalpha_interjudge_rep1": ci(ba),
                      "transcript_variance_share": ci(bs)}
    # 4) rank stability of targets under judge swaps (stratified transcript bootstrap)
    M = Y.mean(axis=2)  # n x 3 judges, repeat-averaged
    mu = {g: M[tg == g].mean(axis=0) for g in present_targets}
    gl = present_targets
    point_order = {}
    for j in range(3):
        point_order[JUDGES[j]] = [gl[i] for i in np.argsort([-mu[g][j] for g in gl], kind="stable")]
    consensus_vals = {g: mu[g].mean() for g in gl}
    cons_order = [gl[i] for i in np.argsort([-consensus_vals[g] for g in gl], kind="stable")]
    same_all = 0
    match_cons = np.zeros(3)
    pair_agree = {}
    pairs = [(a, b) for ia, a in enumerate(gl) for b in gl[ia + 1:]]
    for a, b in pairs:
        pair_agree[f"{a}>{b}"] = 0
    grp_ix = [np.where(tg == g)[0] for g in gl]
    for _ in range(B):
        bm = {}
        for g, ix in zip(gl, grp_ix):
            samp = rng.choice(ix, size=len(ix), replace=True)
            bm[g] = M[samp].mean(axis=0)
        orders = []
        for j in range(3):
            o = [gl[i] for i in np.argsort([-bm[g][j] for g in gl], kind="stable")]
            orders.append(o)
        if all(o == orders[0] for o in orders):
            same_all += 1
        for j in range(3):
            match_cons[j] += orders[j] == cons_order
        for a, b in pairs:
            signs = {np.sign(bm[a][j] - bm[b][j]) for j in range(3)}
            if len(signs) == 1 and list(signs)[0] == np.sign(consensus_vals[a] - consensus_vals[b]):
                pair_agree[f"{a}>{b}"] += 1
    d["rank_stability"] = {
        "point_order_by_judge": point_order,
        "consensus_order_mean_over_judges": cons_order,
        "target_means_rep_avg_by_judge": {g: {JUDGES[j]: float(mu[g][j]) for j in range(3)} for g in gl},
        "n_per_target": {g: int(np.sum(tg == g)) for g in gl},
        "P_all_three_judges_same_order": same_all / B,
        "P_judge_order_equals_consensus": {JUDGES[j]: float(match_cons[j] / B) for j in range(3)},
        "P_pairwise_sign_agrees_across_all_judges": {k: v / B for k, v in pair_agree.items()},
        "B": B,
    }
    # 5) extra validity: AUC vs planted expected dimension (rep-averaged judge score)
    labels = np.array([1 if dim in info[t]["expected_dimensions"] else 0 for t in np.array(tids)[complete]])
    val = {"n_positive": int(labels.sum()), "n_negative": int(len(labels) - labels.sum())}
    if 0 < labels.sum() < len(labels):
        val["auc_by_judge"] = {JUDGES[j]: float(auc(M[:, j], labels)) for j in range(3)}
        val["auc_by_judge_mean_of_judges"] = float(auc(M.mean(axis=1), labels))
    d["validity_vs_planted_label"] = val
    results["dims"][dim] = d
    fig_rows[dim] = {"Y": Y, "M": M, "tg": tg, "labels": labels}

json.dump(results, open(os.path.join(OUT_DIR, f"results_{TAG}.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# ---------------------------------------------------------------- figures
plt.rcParams.update({"font.size": 9})
dims_plot = [d for d in DIMS if d in fig_rows]
short = {"concerning": "concerning", "unprompted_deception_toward_user": "unprompted\ndeception",
         "cooperation_with_human_misuse": "cooperation w/\nmisuse", "unfaithful_thinking": "unfaithful\nthinking"}

# fig1: reliability bars with transcript-bootstrap CIs
fig, ax = plt.subplots(figsize=(8, 4))
x = np.arange(len(dims_plot))
w = 0.27
for k, (lab, key, color) in enumerate([("ICC(2,1) inter-judge, rep 1", "icc21_interjudge_rep1", "#3b6ea5"),
                                       ("Krippendorff alpha, 3 judges, rep 1", "kalpha_interjudge_rep1", "#8c8c8c"),
                                       ("Test-retest ICC(2,1), mean of judges", "test_retest_icc21_mean_over_judges", "#c56a2d")]):
    vals = [results["dims"][dm].get(key, np.nan) for dm in dims_plot]
    err = None
    if key in ("icc21_interjudge_rep1", "kalpha_interjudge_rep1"):
        ck = "icc21_interjudge_rep1" if key.startswith("icc") else "kalpha_interjudge_rep1"
        lo = [results["dims"][dm]["boot_ci95"][ck][0] for dm in dims_plot]
        hi = [results["dims"][dm]["boot_ci95"][ck][1] for dm in dims_plot]
        err = [np.array(vals) - np.array(lo), np.array(hi) - np.array(vals)]
    ax.bar(x + (k - 1) * w, vals, w, label=lab, color=color, yerr=err, capsize=2)
ax.axhline(0, color="black", lw=0.6)
ax.set_xticks(x)
ax.set_xticklabels([short[d] for d in dims_plot])
ax.set_ylabel("coefficient")
ax.set_ylim(-0.6, 1.05)
ax.set_title(f"Judge reliability, {len(tids)} transcripts (95% transcript-bootstrap CI for first two)")
ax.legend(fontsize=7, loc="lower right")
fig.tight_layout()
f1 = os.path.join(OUT_DIR, f"fig1_reliability_{TAG}.png")
fig.savefig(f1, dpi=150)
plt.close(fig)

# fig2: variance shares
fig, ax = plt.subplots(figsize=(8, 4))
comp = ["transcript", "judge", "repeat", "transcript_x_judge", "transcript_x_repeat", "judge_x_repeat", "residual_3way"]
colors = ["#2b8c4b", "#3b6ea5", "#c56a2d", "#9ec7a6", "#e0a46e", "#c9b3dd", "#bdbdbd"]
bottom = np.zeros(len(dims_plot))
for c, colr in zip(comp, colors):
    vals = np.array([results["dims"][dm]["varcomp_share"][c] for dm in dims_plot])
    vals = np.nan_to_num(vals)
    ax.bar(np.arange(len(dims_plot)), vals, 0.6, bottom=bottom, label=c.replace("_x_", " x ").replace("_", " "), color=colr)
    bottom += vals
ax.set_xticks(np.arange(len(dims_plot)))
ax.set_xticklabels([short[d] for d in dims_plot])
ax.set_ylabel("share of positive variance")
ax.set_title("Variance components (method of moments; residual includes the unreplicated 3-way term)")
ax.legend(fontsize=6.5, bbox_to_anchor=(1.01, 1), loc="upper left")
fig.tight_layout()
f2 = os.path.join(OUT_DIR, f"fig2_varcomp_{TAG}.png")
fig.savefig(f2, dpi=150)
plt.close(fig)

# fig3: judge-vs-judge scatter for 'concerning' (repeat-averaged), jitter for ties
if "concerning" in fig_rows:
    M = fig_rows["concerning"]["M"]
    fig, axes = plt.subplots(1, 3, figsize=(9, 3.2))
    pairs = [(0, 1), (0, 2), (1, 2)]
    for ax, (a, b) in zip(axes, pairs):
        xs = M[:, a] + rng.uniform(-0.12, 0.12, M.shape[0])
        ys = M[:, b] + rng.uniform(-0.12, 0.12, M.shape[0])
        ax.scatter(xs, ys, s=18, alpha=0.7)
        ax.plot([1, 10], [1, 10], color="grey", lw=0.6, ls="--")
        rho = stats.spearmanr(M[:, a], M[:, b]).statistic
        ax.set_title(f"{JUDGES[a]} vs {JUDGES[b]}  rho={rho:.2f}", fontsize=8)
        ax.set_xlabel(f"{JUDGES[a]} (mean of 2 runs)")
        ax.set_ylabel(f"{JUDGES[b]} (mean of 2 runs)")
        ax.set_xlim(0.5, 10.5)
        ax.set_ylim(0.5, 10.5)
    fig.tight_layout()
    f3 = os.path.join(OUT_DIR, f"fig3_concerning_scatter_{TAG}.png")
    fig.savefig(f3, dpi=150)
    plt.close(fig)
else:
    f3 = None

# fig4: rank stability
fig, ax = plt.subplots(figsize=(8, 3.6))
pa = [results["dims"][dm]["rank_stability"]["P_all_three_judges_same_order"] for dm in dims_plot]
pc = [np.mean(list(results["dims"][dm]["rank_stability"]["P_judge_order_equals_consensus"].values())) for dm in dims_plot]
ax.bar(np.arange(len(dims_plot)) - 0.18, pa, 0.36, label="P(all 3 judges give the same target order)", color="#3b6ea5")
ax.bar(np.arange(len(dims_plot)) + 0.18, pc, 0.36, label="P(a judge's order = consensus order), mean over judges", color="#c56a2d")
ax.axhline(1 / 6, color="grey", ls="--", lw=0.7)
ax.text(len(dims_plot) - 0.5, 1 / 6 + 0.02, "chance (1/6 for orders of 3)", fontsize=6.5, ha="right")
ax.set_ylim(0, 1.05)
ax.set_xticks(np.arange(len(dims_plot)))
ax.set_xticklabels([short[d] for d in dims_plot])
ax.set_title("Rank stability of the three target models under judge swaps (transcript bootstrap)")
ax.legend(fontsize=7, loc="lower left")
fig.tight_layout()
f4 = os.path.join(OUT_DIR, f"fig4_rank_stability_{TAG}.png")
fig.savefig(f4, dpi=150)
plt.close(fig)

print(json.dumps({"figures": [f1, f2, f3, f4], "results": os.path.join(OUT_DIR, f"results_{TAG}.json")}))
print(json.dumps(call_summary, indent=1))
for dm in DIMS:
    if dm in results["dims"]:
        dd = results["dims"][dm]
        print(dm, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in dd.items()
                   if k in ("n_complete_transcripts", "icc21_interjudge_rep1", "icc21_interjudge_repavg",
                            "kalpha_interjudge_rep1", "kalpha_all6_raters", "test_retest_icc21_mean_over_judges")})
