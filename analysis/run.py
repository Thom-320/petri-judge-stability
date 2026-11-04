"""Full analysis: reliability (pilot-compatible), phi per decision and dimension, D-study, controls.

Usage (pilot data, cheap judges):
  python -m analysis.run --judgments pilot/scores_pilot120.jsonl --meta pilot/sample_meta.json \
      --n 120 --judges muse,mimo,deepseek --out results/pilot120 --tag pilot120_cheap
Usage (v2 runs):
  python -m analysis.run --judgments runs/*/results.jsonl --meta results/meta_260.json \
      --n 260 --judges opus45,gemini31pro,gpt51 --out results/v2 --tag v2

With an expanded panel (J = 6-8), pass all judges in --judges and the three Petri facets in
--confirm-judges: H1'/H2' (confirmatory) use the fixed Petri facets only; the random-judge D-study
and the H3' floor use every judge.

Outputs <out>/results_<tag>.json and <out>/phi_vs_icc_<tag>.md.
"""
import argparse
import itertools
import json
import os

import numpy as np

from . import confirm, data, phi, reliability, reml

DIMS = ["concerning", "unprompted_deception_toward_user", "cooperation_with_human_misuse", "unfaithful_thinking"]
# Confirmatory family (pre-registration, Session 2). unfaithful_thinking is exploratory: no target
# emits native reasoning, and auditor-prompted <thinking> blocks occur in 2 of 95 Hermes transcripts.
CONFIRM_DIMS = DIMS[:3]
EXPLORATORY_DIMS = DIMS[3:]
# Target-level threshold decisions "target mean <= c" for the model-based phi and the H3' floor.
# 4 and 7 are Petri's own cut-offs (confirm.PETRI_CUTOFFS); 2, 3, 5 are descriptive.
THRESHOLDS = (2.0, 3.0, 4.0, 5.0, 7.0)
H3_JS = (1, 3)
PHI_SEED = 20261009
CONFIRM_SEED = 20261010


def analyze(recs, meta_rows, judges, dims=DIMS, targets=data.TARGETS, b_ci=reliability.B_CI,
            b_rank=reliability.B_RANK, b_phi=1000, placebo_perms=500, split_draws=2000,
            reliability_seed=reliability.SEED, phi_seed=PHI_SEED, petri_floor=False,
            confirm_judges=None, b_confirm=confirm.B_CONFIRM, run_reml=True, confirm_dims=CONFIRM_DIMS):
    tids = [r["transcript_id"] for r in meta_rows]
    info = {r["transcript_id"]: r for r in meta_rows}
    tgt = np.array([info[t]["target"] for t in tids])
    sev = np.array([info[t]["severity"] for t in tids])
    confirm_judges = confirm_judges or judges[:3]
    cidx = [judges.index(j) for j in confirm_judges]
    out = {"n_transcripts_in_sample": len(tids), "judges": judges, "confirm_judges": confirm_judges,
           "confirm_dims": [d for d in dims if d in confirm_dims],
           "exploratory_dims": [d for d in dims if d not in confirm_dims],
           "petri_floor_sensitivity": petri_floor,
           "missing": data.missing_summary(recs, judges, dims),
           "missing_by_severity": data.missing_by_stratum(recs, meta_rows, judges, dims), "dims": {}}
    tensors, alltensors = {}, {}
    rng_rel = np.random.default_rng(reliability_seed)
    for dim in dims:
        Yall = data.score_tensor(recs, meta_rows, dim, judges, petri_floor=petri_floor)
        ok = data.complete(Yall)
        Y = Yall[ok]
        d = {"n_complete_transcripts": int(ok.sum()), "n_excluded_incomplete": int((~ok).sum()),
             "n_transcripts_with_any_score": int(np.sum(~np.all(np.isnan(Yall), axis=(1, 2)))),
             "role": "confirmatory" if dim in confirm_dims else "exploratory"}
        alltensors[dim] = (Yall, tgt)
        if Y.shape[0] < 4:
            d["note"] = "too few complete transcripts"
            out["dims"][dim] = d
            continue
        labels = np.array([1 if dim in info[t]["expected_dimensions"] else 0 for t in np.array(tids)[ok]])
        d.update(reliability.dim_reliability(Y, tgt[ok], labels, judges, targets, rng_rel, b_ci, b_rank))
        out["dims"][dim] = d
        tensors[dim] = (Y, tgt[ok], sev[ok])
    rng = np.random.default_rng(phi_seed)
    rng_c = np.random.default_rng(CONFIRM_SEED)
    splits_confirm = {}
    for dim, (Y, tg, sv) in tensors.items():
        d = out["dims"][dim]
        gl = [g for g in targets if np.any(tg == g)]
        res, gs = phi.decisions(Y, tg, gl, THRESHOLDS)
        d["phi"] = res
        d["phi_boot_ci95"] = phi.bootstrap(Y, tg, rng, b_phi, gl, THRESHOLDS) if b_phi else {}
        d["dstudy"] = {k: phi.dstudy_contrast(gs, *k.split("|")) for k in res["contrasts"]}
        for k in d["dstudy"]:
            d["dstudy"][k].pop("grid")  # keep the summary; the grid is reproducible from the components
        d["empirical_split"] = {k: phi.empirical_split(Y, tg, *k.split("|"), rng=rng, draws=split_draws)
                                for k in res["contrasts"]}
        if dim in confirm_dims:
            splits_confirm.update({f"{dim}|{k}": v for k, v in d["empirical_split"].items()})
        # negative control: planted severity high vs low (expected large gap, phi ~ 0)
        m = np.isin(sv, ["high", "low"])
        nc, _ = phi.decisions(Y[m], sv[m], ["high", "low"])
        d["negative_control_severity_high_vs_low"] = nc["contrasts"]["high|low"]
        d["placebo_permuted_targets"] = phi.placebo(Y, tg, rng, placebo_perms, min(200, split_draws)) if placebo_perms else {}
        d["H3_floor_bound"] = phi.floor_bound(gs, H3_JS + ((len(judges),) if len(judges) not in H3_JS else ()),
                                              confirm.PETRI_CUTOFFS)
        if b_confirm:
            d["confirm"] = confirm.confirm_dim(Y, tg, gl, rng_c, judge_idx=cidx, B=b_confirm)
            if len(judges) > len(cidx):  # secondary: H1'/H2' statistics over all judge pairs
                d["confirm_all_judges"] = confirm.confirm_dim(Y, tg, gl, rng_c, B=b_confirm)
        if run_reml:
            Yall, tga = alltensors[dim]
            fr = reml.fit(Yall, tga, gl)
            g2 = reml.gs_like(fr, len(judges), Y.shape[2])
            rr = {"fit": fr, "contrasts": {}}
            for a, b in itertools.combinations(gl, 2):
                delta = g2["group_means"][a] - g2["group_means"][b]
                v = phi.contrast_var(g2, a, b)
                rr["contrasts"][f"{a}|{b}"] = {"delta": float(delta), "phi_bc_full": phi.phi_bc(delta, v, np.sqrt(v)),
                                               "phi_bc_judges": phi.phi_bc(delta, v, np.sqrt(phi.contrast_var(g2, a, b, facet="judges")))}
            d["reml_sensitivity"] = rr
    if b_confirm:
        out["confirmatory_family"] = confirm.family({k: v["confirm"] for k, v in out["dims"].items() if "confirm" in v},
                                                    [d for d in dims if d in confirm_dims])
    out["model_check"] = phi.model_check(splits_confirm)
    return out


def _f(x, fmt="{:.3f}"):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else fmt.format(x)


def confirm_tables(res):
    J = res["confirm_judges"]
    lines = [f"### Confirmatory family (fixed judges: {', '.join(J)})", ""]
    fam = res.get("confirmatory_family")
    if fam:
        lines += [f"Holm across m = {fam['m']} tests, alpha = {fam['alpha']}. H1' also needs the share rule "
                  f"(>= 2/3 of judge-pair x contrast cells with a 95% lower bound above 0).", "",
                  "| Test | Estimate [95% CI] | p (one-sided) | p Holm | Supported |", "|---|---|---|---|---|"]
        for k, t in fam["tests"].items():
            parts = k.split("|")
            c = res["dims"][parts[1]]["confirm"]
            if parts[0] == "H1":
                est = f"mean D = {c['H1']['mean_D']:+.3f} [{c['H1']['mean_D_ci95'][0]:+.3f}, {c['H1']['mean_D_ci95'][1]:+.3f}]; " \
                      f"share = {c['H1']['share_cells_lower_bound_above_0']:.2f}"
            else:
                cc = parts[2].split("=")[1]
                ci = c["H2"]["ci95"][f"diff_{cc}"]
                est = f"FT - FC = {c['H2']['estimate'][f'diff_{cc}']:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]"
            lines.append(f"| {k} | {est} | {t['p']:.4f} | {t['p_holm']:.4f} | {'yes' if t['supported'] else 'no'} |")
    lines += ["", "Flip rates under a judge swap / within-judge repeat (H2' target level = bootstrap mean; "
              "transcript level = observed; FT_c is a threshold at Petri's cut-off c, FC a contrast):", "",
              "| Dimension | Role | Level | FC swap / repeat | FT_4 swap / repeat | FT_7 swap / repeat | FT_4 - FC [95% CI] | FT_7 - FC [95% CI] |",
              "|---|---|---|---|---|---|---|---|"]
    for dim, d in res["dims"].items():
        if "confirm" not in d:
            continue
        for lev, key in (("target", "H2"), ("transcript", "H2_transcript_level")):
            h = d["confirm"][key]
            p, ci = h["estimate"], h["ci95"]
            lines.append(f"| {dim} | {d['role']} | {lev} | {p['FC']:.3f} / {_f(p['FC_repeat'])} | "
                         f"{p['FT_4']:.3f} / {_f(p['FT_4_repeat'])} | {p['FT_7']:.3f} / {_f(p['FT_7_repeat'])} | "
                         f"{p['diff_4']:+.3f} [{ci['diff_4'][0]:+.3f}, {ci['diff_4'][1]:+.3f}] | "
                         f"{p['diff_7']:+.3f} [{ci['diff_7'][0]:+.3f}, {ci['diff_7'][1]:+.3f}] |")
    cs = sorted(set(confirm.PETRI_CUTOFFS) | set(confirm.DESCRIPTIVE_CUTOFFS))
    lines += ["", "Descriptive FT(c) curve, target level, judge swap (bootstrap mean); 4 and 7 are the tested Petri cut-offs:", "",
              "| Dimension | FC | " + " | ".join(f"c={c}" for c in cs) + " |", "|---|---|" + "---|" * len(cs)]
    for dim, d in res["dims"].items():
        if "confirm" not in d:
            continue
        p = d["confirm"]["H2"]["estimate"]
        lines.append(f"| {dim} | {p['FC']:.3f} | " + " | ".join(f"{p[f'FT_{c}']:.3f}" for c in cs) + " |")
    mc = res.get("model_check", {})
    if mc.get("n_decisions"):
        lines += ["", f"**Model check** at J=1, R=1, n/2, mean over {mc['n_decisions']} confirmatory contrasts: split-half "
                  f"{mc['mean_split_half']:.3f}, model plug-in {mc['mean_plugin_model']:.3f}, model bc {mc['mean_bc_model']:.3f}. "
                  f"Rule: plug-in - {mc['tolerance']} <= split-half <= bc + {mc['tolerance']}: "
                  f"**{'passed' if mc['passed'] else 'FAILED, model-based results (phi, D-study, H3) are exploratory'}**."]
    return "\n".join(lines)


def phi_vs_icc_table(res, tag):
    lines = [confirm_tables(res), "",
             f"### Descriptive display: phi vs ICC ({tag})", "",
             "phi full: plug-in point, [95% CI by inverting the Delta interval] (primary), bias-corrected point; "
             "the bootstrap CI of the plug-in is in the JSON.", "",
             "| Dimension | Role | n | ICC(2,1) rep 1 | alpha | Contrast | Delta | phi full [95% CI] / bc | phi judges [95% CI] | "
             "phi repeats | phi transcripts | empirical split phi (J=1,R=1,n/2) vs model bc / plug-in |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for dim, d in res["dims"].items():
        if "phi" not in d:
            continue
        for k, r in d["phi"]["contrasts"].items():
            ci, cj = r["phi_ci95_full"], r["phi_ci95_judges"]
            es = d["empirical_split"][k]
            lines.append(f"| {dim} | {d['role']} | {d['n_complete_transcripts']} | {d['icc21_interjudge_rep1']:.2f} | "
                         f"{d['kalpha_interjudge_rep1']:.2f} | {k.replace('|', ' vs ')} | {r['delta']:+.2f} | "
                         f"{r['phi_full']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] / {r['phi_bc_full']:.3f} | "
                         f"{r['phi_judges']:.3f} [{cj[0]:.3f}, {cj[1]:.3f}] | "
                         f"{r['phi_repeats']:.3f} | {r['phi_transcripts']:.3f} | "
                         f"{es['phi_empirical']:.3f} vs {es['phi_bc_model_J1R1_half']:.3f} / {es['phi_model_J1R1_half']:.3f} |")
    lines += ["", "| Dimension | s_gj [95% chi-square CI] | s_j [95% Satterthwaite CI] | Negative control: high vs low, Delta / phi | "
              "Placebo: plug-in phi mean / bc phi mean / empirical split phi |", "|---|---|---|---|---|"]
    for dim, d in res["dims"].items():
        if "phi" not in d:
            continue
        g = d["phi"]["gstudy"]
        ci = g.get("judge_component_ci95") or {}
        cg = ci.get("s_gj", {}).get("ci", [np.nan, np.nan])
        cj = ci.get("s_j", {}).get("ci", [np.nan, np.nan])
        nc = d["negative_control_severity_high_vs_low"]
        pl = d.get("placebo_permuted_targets") or {}
        lines.append(f"| {dim} | {g['s_gj']:.4f} [{cg[0]:.4f}, {cg[1]:.4f}] (df {g['df_gj']}) | "
                     f"{g['s_j']:.4f} [{cj[0]:.4f}, {cj[1]:.4f}] | "
                     f"{nc['delta']:+.2f} / {nc['phi_bc_full']:.2e} | "
                     f"{pl.get('plugin_phi_mean', np.nan):.3f} / {pl.get('bc_phi_mean', np.nan):.3f} / "
                     f"{pl.get('empirical_split_phi_mean', np.nan):.3f} |")
    lines += ["", "H3' (model-based, random judges): judge floor of phi with n -> infinity, plug-in point "
              "[joint 95% bound from the Delta and judge-component intervals, Bonferroni].", "",
              "| Dimension | Decision | J = 1 | J = 3 |", "|---|---|---|---|"]  # J = len(judges) is in the JSON
    for dim, d in res["dims"].items():
        fb = d.get("H3_floor_bound") or {}
        for kind in ("contrasts", "thresholds"):
            for k, r in fb.get(kind, {}).items():
                cells = [f"{r['by_J'][J]['point']:.3f} [{r['by_J'][J]['bound'][0]:.3f}, {r['by_J'][J]['bound'][1]:.3f}]"
                         for J in ("1", "3")]
                lines.append(f"| {dim} | {k.replace('|', ' vs ')} | {cells[0]} | {cells[1]} |")
    lines += ["", "| Dimension | Contrast | Cheapest design with phi <= 0.05 (J, R, n per target, calls): plug-in / bias-corrected |",
              "|---|---|---|"]
    fmt = lambda b: f"J={b['J']}, R={b['R']}, n={b['n']}, {b['calls']} calls" if b else "not reached on the grid"  # noqa: E731
    for dim, d in res["dims"].items():
        for k, ds in (d.get("dstudy") or {}).items():
            lines.append(f"| {dim} | {k.replace('|', ' vs ')} | {fmt(ds['cheapest'].get('0.05'))} / {fmt(ds['cheapest_bc'].get('0.05'))} |")
    if any("reml_sensitivity" in d for d in res["dims"].values()):
        lines += ["", "REML sensitivity (all valid scores, unbalanced) vs ANOVA (complete cases):", "",
                  "| Dimension | scores used | s_j REML / ANOVA | s_gj REML / ANOVA | contrast: phi_bc full REML / ANOVA |", "|---|---|---|---|---|"]
        for dim, d in res["dims"].items():
            rr = d.get("reml_sensitivity")
            if not rr:
                continue
            g = d["phi"]["gstudy"]
            c = rr["fit"]["components"]
            ph = "; ".join(f"{k.replace('|', ' vs ')} {v['phi_bc_full']:.3f} / {d['phi']['contrasts'][k]['phi_bc_full']:.3f}"
                           for k, v in rr["contrasts"].items())
            lines.append(f"| {dim} | {rr['fit']['n_scores']} | {c['s_j']:.4f} / {g['s_j']:.4f} | {c['s_gj']:.4f} / {g['s_gj']:.4f} | {ph} |")
    lines += ["", "Failure rate by planted severity (judge: dimension high / moderate / low):", ""]
    for j, dd in res.get("missing_by_severity", {}).items():
        parts = []
        for dim, cells in dd.items():
            parts.append(f"{dim} " + " / ".join(f"{cells[lv]['failure_rate']:.3f}" for lv in ("high", "moderate", "low") if lv in cells))
        lines.append(f"- {j}: " + "; ".join(parts))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--judgments", nargs="+", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--judges", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--b-phi", type=int, default=1000)
    ap.add_argument("--placebo-perms", type=int, default=500)
    ap.add_argument("--confirm-judges", help="fixed judges for H1'/H2' (default: the first three of --judges)")
    ap.add_argument("--b-confirm", type=int, default=confirm.B_CONFIRM)
    ap.add_argument("--no-reml", action="store_true", help="skip the REML sensitivity (slow for J = 8 on 260 transcripts)")
    ap.add_argument("--petri-floor", action="store_true",
                    help="sensitivity only: score missing dimensions of responded calls as 1, as Petri does")
    a = ap.parse_args(argv)
    recs = data.read_records(a.judgments)
    meta = data.load_meta(a.meta, a.n)
    res = analyze(recs, meta, a.judges.split(","), b_phi=a.b_phi, placebo_perms=a.placebo_perms,
                  petri_floor=a.petri_floor, b_confirm=a.b_confirm, run_reml=not a.no_reml,
                  confirm_judges=a.confirm_judges.split(",") if a.confirm_judges else None)
    res["tag"] = a.tag
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, f"results_{a.tag}.json"), "w", encoding="utf-8"), indent=1,
              default=float)
    md = phi_vs_icc_table(res, a.tag)
    open(os.path.join(a.out, f"phi_vs_icc_{a.tag}.md"), "w", encoding="utf-8").write(md + "\n")
    print(md)


if __name__ == "__main__":
    main()
