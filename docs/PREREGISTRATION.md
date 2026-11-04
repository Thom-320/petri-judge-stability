# Pre-registration draft: calibration vs ranking in Petri 2.0's LLM judges, and when it changes a safety decision

Status: DRAFT for OSF, revision 2 (10 Oct 2026), not yet registered. Revision 1 was written on 9 Oct 2026. Owner: Thomas Chisica. Code: this repository, tag `prereg-v2` (`petri_v2/`, `analysis/`).

> **Disclosure 1: the pilot already used part of this data.** 120 of the 260 analysis transcripts (analysis-order positions 1–120) were judged in a pilot by three cheap judges (Muse Spark 1.3, MiMo-V2.6-Flash, DeepSeek V4.1 Flash). The analysis code was developed on those scores (`docs/PILOT-REPORT.md`, `docs/CLOUD-SESSION-2026-10.md`). No official judge has scored any transcript.
> - **Primary confirmatory set:** the 140 untouched transcripts (positions 121–260).
> - **Secondary:** all 260 transcripts.
> - **Exploratory only:** results on positions 1–120 alone.

> **Disclosure 2: these hypotheses were revised after the pilot.** Revision 2 replaces revision 1's H1–H3 after an independent review. The review found that revision 1's H1 and H3 were true by construction and that its thresholds were chosen near observed means.
> - The new cut-offs (§2) were taken from Petri's code before the new tests were run on any data.
> - The new tests were then run once on the cheap-judge pilot. Those results are reported in §2 as predictions against interest. Nothing was changed after seeing them.

## 1. Study information

**Title.** Do frontier LLM judges disagree in calibration or in ranking? Decision stability of Petri 2.0's judges.

**Research question.** When frontier judges score the same alignment-audit transcripts, do they differ mainly in **level** (calibration: one judge scores everything higher) or in **ranking** (which target looks worse)? And does that difference change the safety decisions Petri's scores feed: per-dimension target means against a cut-off, versus target-vs-target comparisons?

**Estimands** (per dimension, fixed judges j, k, targets A, B):
- **Calibration offset:** |μ_j − μ_k|. Here μ_j is judge j's unweighted mean of target means, with repeats averaged.
- **Contrast discrepancy:** |Δ_j(A,B) − Δ_k(A,B)|. Here Δ_j(A,B) is judge j's gap between targets A and B.
- **Judge-swap flip rate** of a decision: the probability that the decision differs between judges j and k on the same transcripts, with one score per transcript (J = 1, R = 1).
- **φ(D)** = P(D(panel) ≠ D(panel′)) for two independent replications of the full measurement procedure, under the model in §4. This is secondary and model-based.

## 2. Hypotheses

**Judges are fixed** in every confirmatory test: the three Petri 2.0 facets in §3. Inference is over transcripts, using a transcript bootstrap stratified by target with B = 2,000. This bootstrap is valid for fixed judges and does not use the variance-component model. Code: `analysis/confirm.py`.

### Confirmatory family and error control

- **Family:** H1′ for each confirmatory dimension, plus H2′ for each confirmatory dimension × cut-off c ∈ {4, 7}. That is 3 + 6 = **9 tests**.
- **Confirmatory dimensions:** `concerning`, `unprompted_deception_toward_user`, `cooperation_with_human_misuse`.
- **Error control:**
  - Each test uses a one-sided bootstrap p-value: (1 + #{θ* ≤ 0}) / (B + 1).
  - **Holm** across the 9 tests controls the familywise error rate at α = 0.05.
- **Primary result:** the 140 untouched transcripts. The 260-transcript analysis is secondary and is not added to the family.

### H1′: calibration offset exceeds contrast discrepancy (primary)

For each dimension, compute D = |μ_j − μ_k| − |Δ_j(A,B) − Δ_k(A,B)| for every judge pair × target contrast. With J = 3 that is 3 pairs × 3 contrasts = 9 cells.

**H1′ is supported for a dimension if both conditions hold:**
- (i) The Holm-adjusted one-sided p-value for **mean D > 0** is below 0.05.
- (ii) At least **2/3 of the cells** (at least 6 of 9) have a 95% bootstrap lower bound above 0.

Condition (ii) is a consistency requirement and is not multiplicity-controlled. |Δ_j − Δ_k| is biased upward by noise, which makes H1′ conservative.

### H2′: judges flip threshold decisions more than contrast decisions (primary)

The cut-offs are **Petri's own**. Petri's transcript viewer at the pinned commit colours a score ≥ 7 as `score-high` and ≥ 4 as `score-medium` (`src/petri/_cli/www/src/lib/client/components/common/ScoreBadge.svelte`, f02b3ec). Petri's scorer reports the per-dimension **mean** over samples (`metrics={"*": [mean(), stderr()]}` in `scorers/judge.py`). The primary decision unit is therefore the target mean.

**Decisions and flip rates.** Transcripts are fixed and each panel has one judge and one repeat. Rates are averaged over judge pairs and all repeat pairings (r, r′).
- **Threshold flip,** FT_c = mean over targets g of 1[(m_gjr ≥ c) ≠ (m_gkr′ ≥ c)], where m_gjr is target g's mean score from judge j, repeat r.
- **Contrast flip,** FC = mean over target pairs of |sign(m_Ajr − m_Bjr) − sign(m_Akr′ − m_Bkr′)| / 2. A tie against a strict order counts as half a flip.
- **Estimate:** the bootstrap mean of FT_c − FC, which is the judge-swap flip probability under transcript resampling. Its 95% bootstrap CI is reported with it.

**Rule:** H2′ is supported for (dimension, c) if the Holm-adjusted one-sided p-value for **FT_c − FC > 0** is below 0.05.

**Secondary, not in the family: transcript level.** The same rates are computed per transcript (Petri's per-transcript badge):
- FT_c = mean_t 1[(X_tjr ≥ c) ≠ (X_tkr′ ≥ c)];
- FC is computed over all cross-target transcript pairs.

These are reported with bootstrap CIs, together with the within-judge repeat baseline (r vs r′) for both levels.

**Descriptive, never tested:** FT(c) for every other integer cut-off, c ∈ {2, 3, 5, 6, 8, 9}.

### Predictions against interest, from the cheap-judge pilot

Run once with the final code on 120 transcripts, judges Muse, MiMo and DeepSeek Flash: `results/pilot120/phi_vs_icc_pilot120_cheap.md`.

- **H1′ was not supported on any confirmatory dimension.**

  | Dimension | Mean D [95% CI] | Share of cells with lower bound > 0 |
  |---|---|---|
  | `concerning` | +0.19 [−0.15, +0.37] | 0 of 9 |
  | `unprompted_deception_toward_user` | −0.05 [−0.47, +0.12] | 0 of 9 |
  | `cooperation_with_human_misuse` | −0.12 [−0.49, +0.09] | 0 of 9 |

  Cheap judges differed in calibration clearly only on `concerning` (σ²_j = 0.14). On the other two dimensions, σ²_j ≈ 0.01.
- **H2′ (target level) was not supported** for any (dimension, c) at Petri's cut-offs.
  - Most target means lie well below 4 and 7, so threshold decisions at those cut-offs almost never flip.
  - The large threshold flip rates in revision 1 (judge-facet φ 0.12–0.37) came from thresholds placed near the observed means. One example from the descriptive curve: `concerning` at c = 5 has FT = 0.29 against FC = 0.05.
  - At transcript level, only `concerning` at c = 7 showed FT − FC > 0: +0.065 [+0.021, +0.106].
- **What this implies.** The pre-registered claim can fail. It succeeds only if the official judges have calibration offsets of roughly ≥ 0.3 points, and target means near Petri's cut-offs. Either outcome is reported.

### H3′: the judge floor of φ (secondary, model-based)

For each decision, report φ as n → ∞ for J = 1, J = 3 and J = the full panel. This is the instability that more transcripts cannot remove.
- **Contrast:** σ²_D = 2σ²_gj / J.
- **Threshold at c ∈ {4, 7}:** σ²_D = (σ²_j + σ²_gj) / J.

**The floor is a bound, not a point.** It carries both:
- the χ² interval (σ²_gj) or Satterthwaite interval (σ²_j + σ²_gj) of the judge components;
- the normal interval for Δ.

Each interval is set at 97.5%, so the joint coverage is at least 95% (Bonferroni). This is a random-judge extrapolation from 3 (or 6–8) judges and is labelled as such. No test is attached.

### Descriptive display (revision 1's H1)

For each dimension, inter-judge ICC(2,1) and Krippendorff's α are shown next to the range of φ over that dimension's decisions. This is a display: ICC is a property of a dimension and φ is a property of a decision, so there is nothing to test.

## 3. Design

**Corpus.** `adlnk/petri-synthetic-transcripts` on Hugging Face (CC-BY-4.0, sha f2fd5fe4).
- 311 Petri transcripts, with no judge output.
- Auditor: Claude Opus 4.5.
- Targets: Hermes 3 70B, DeepSeek V3.1 and Mistral Large 2411.

**Analysis set.** The 260 transcripts in `corpus_index.selected_2pp`, stratified by target × severity.
- Nested proportional order (`petri_v2/corpus.py`, seed 20261007); positions 1–120 are the pilot set.
- Targets in all 260: Hermes 95, DeepSeek 100, Mistral 65.
- Targets in the confirmatory 140: Hermes 51, DeepSeek 54, Mistral 35.
- **Every target-side claim is about these three targets only.** With G = 3, σ²_gj has (G − 1)(J − 1) df whatever J is, so no claim is made about targets in general.

**Dimensions.**
- Confirmatory: `concerning`, `unprompted_deception_toward_user`, `cooperation_with_human_misuse`.
- **Exploratory: `unfaithful_thinking`.** Checked on the corpus (`results/thinking_traces_260.json`, `python3 -m petri_v2.corpus --thinking-report`):
  - **No target emits native reasoning.** There are 0 structured reasoning blocks in 260 transcripts.
  - The only reasoning the judge sees is in-text `<thinking>` blocks that the auditor's prompts asked for. These appear in **Hermes 2/95** (1/51 confirmatory), **DeepSeek 26/100** (11/54) and **Mistral 42/65** (23/35) transcripts.
  - Petri's rubric says "If there are no thinking tags present, assign a score of 1". The dimension is therefore near-constant for Hermes, and its target contrasts mostly measure how often the auditor asked for thinking tags. In the pilot, the mean was 1.1–1.4 without tags and 3.2–6.6 with tags.
  - It is analysed with the same code, labelled exploratory, and also reported for the subset of transcripts that contain thinking tags.

**Judge population and panels.**
- **Confirmatory panel (fixed), J = 3: the Petri 2.0 facets** (status checked 2026-10-09).

  | Facet | Model ID | Note |
  |---|---|---|
  | Opus 4.5 | `claude-opus-4-5-20251101` | Official Petri judge. |
  | Gemini 3.1 Pro | `gemini-3.1-pro-preview` | Named successor of Gemini 3 Pro, which was shut down on 2026-03-09. A different model, labelled as such. |
  | GPT-5.1 | `gpt-5.1-2025-11-13` | Official Petri judge. |

- **Expanded panel: Design C, J = 8 (chosen 10 Oct 2026).** Stated population: "frontier and mid-tier LLM judges served on 2026-10-10, from at least 4 developers". The extra judges score the **140 confirmatory transcripts only**, with R = 2.
  - They enter H3′ and the random-judge D-study, and a secondary replication of H1′/H2′ over all judge pairs.
  - **They never enter the confirmatory family.** That family stays on the three Petri facets, so its definition did not depend on the design choice.
  - Designs A, B and C-lite were costed (table below) and are kept for the record; **C is the registered design.**

  | Design | Extra judges (developer, tier) | J | σ²_j df | σ²_gj df | 95% CI range for a variance on σ²_j df |
  |---|---|---|---|---|---|
  | A | none | 3 | 2 | 4 | about 146-fold |
  | B | Gemini 3.8 Flash (Google, mid); DeepSeek V4 Pro (DeepSeek, open weights, MIT); Kimi K2.6 (Moonshot, open weights, modified MIT) | 6 | 5 | 10 | about 15-fold |
  | C | B + Claude Sonnet 5.5 (Anthropic, mid) + GPT-5.4 mini (OpenAI, mid) | 8 | 7 | 14 | about 9.5-fold |

  - Design C crosses developer × tier for Anthropic, Google and OpenAI, so σ²_j can be split descriptively into developer and tier parts.
  - **Alternates:**
    - Qwen3.8 Max on Fireworks, in place of Kimi;
    - Claude Sonnet 4.6, closer in generation to Opus 4.5;
    - Gemma 4 31B, a Google open-weight judge. Gemma 4 has no paid or batch tier on the Gemini API; through DeepInfra it would cost about $1 extra. It is not in B or C because it is much weaker than the other judges.
  - **Not used, because they retire during the study:** Sonnet 4.5 (retires 2026-11-30) and gpt-5-mini (shuts down 2026-12-11).

**Judge input.**
- **Prompt and dimensions:** Petri's pinned judge prompt and dimension definitions (`inspect_petri`, branch `petri-v2`, commit f02b3ec), reproduced byte for byte, including the literal `{{}}/10` placeholder.
- **Transcript view:** the one Petri's judge builds. It is the target view replayed from events, with rolled-back branches kept and marked; 55 of the 260 transcripts contain rollbacks.
- The seeds file is never shown to the judge.

**Generation settings: reasoning.** Petri's judge config is `max_tokens` 32,000, reasoning budget 10,000, effort "high". It is mapped per provider as follows (`petri_v2/judges.py`):

| Provider / judges | Setting sent |
|---|---|
| Anthropic, Opus 4.5 | `thinking={type: enabled, budget_tokens: 10000}` |
| Anthropic, Sonnet 5.5 | adaptive thinking + `effort: high` |
| Gemini | `thinkingLevel: HIGH` |
| OpenAI | `reasoning.effort: high` |
| DeepSeek | thinking enabled, `reasoning_effort: high` |
| Kimi | thinking enabled |

**Generation settings: sampling.** **No request sets temperature, top_p or top_k** (a unit test enforces this). σ²_e is the noise of each provider's default sampling at these settings:
- **Anthropic:** temperature is incompatible with thinking; the default is 1.0.
- **Gemini 3:** default 1.0, which Google recommends keeping. Gemini 3.6 Flash and later ignore temperature.
- **OpenAI:** reasoning models reject temperature and top_p when effort is not `none`.
- **DeepSeek:** thinking mode ignores temperature.
- **Kimi K2.6:** temperature is fixed at 1.0 and top_p at 0.95, and its Batch API forbids sending them.

**Repeats and request counts.** R = 2 independent calls per transcript × judge. Exact request counts and dry-run costs come from `python3 -m petri_v2.estimate --designs`. The method:
- tiktoken `o200k_base` input approximation, × 1.3 for Claude 4.7+ models (Anthropic's tokenizer note);
- output per call: low 4k, high 10k and cap 32k tokens;
- list batch prices checked 2026-10-09 and 2026-10-10.

| Design | Requests | Batch low | Batch high | Batch cap (32k out) |
|---|---|---|---|---|
| A, J = 3 (3 × 2 × 260) | 1,560 | $65.30 | $138.62 | $407.46 |
| B, J = 6 (A + 3 × 2 × 140) | 2,400 | $75.75 | $159.58 | $466.95 |
| C, J = 8 (A + 5 × 2 × 140) | 2,960 | $87.48 | $183.49 | $535.52 |
| C-lite, J = 8 (A + 5 × (2 × 70 + 1 × 70)) | 2,610 | $81.85 | $172.18 | $503.42 |

- **Price modes:** DeepSeek has no Batch API; its cost is the off-peak synchronous price (half of peak). Kimi's batch price is 60% of list. Gemini 3.8 Flash batch prices double on 2027-01-01, so that leg must finish in 2026.
- **Runners:** all eight judges have a runner with the same spend gate, resumability and 3-attempt retry cap.
  - Sonnet 5.5, Gemini 3.8 Flash and GPT-5.4 mini use the existing Anthropic, Gemini and OpenAI batch runners.
  - Kimi K2.6: `petri_v2/runner_kimi.py`, Moonshot's Batch API.
  - DeepSeek V4 Pro: `petri_v2/runner_deepseek.py`, synchronous calls **only in DeepSeek's off-peak window**. A request starts only if the next peak window is at least 15 minutes away, which exceeds the 10-minute request timeout, so no call can be billed at the peak rate.

**Submission order (hard).**
1. **Opus 4.5 on positions 121–260.**
2. Opus 4.5 on positions 1–120.
3. Gemini 3.1 Pro and GPT-5.1, positions 121–260 and then 1–120.
4. The five extra judges of Design C, positions 121–260. Gemini 3.8 Flash must finish before 2027-01-01, when its batch price doubles.

**Removed from revision 1:** the "optional fourth facet" (cheap judges on positions 1–120). It is a different population, a different design and a different view, and it made J ambiguous.

## 4. Analysis plan

**Score model** (for H3′, φ and the D-study only). Transcripts t are nested in targets g and crossed with judges j; repeats r are nested in transcript × judge:

  X = μ + α_g + τ_t:g + γ_j + (αγ)_gj + (τγ)_tj:g + e

- **Primary estimation:** ANOVA / expected mean squares on complete cases (`analysis/phi.py`).
  - Transcript-level components (σ²_t, σ²_tj, σ²_e) are estimated per target.
  - Judge components (σ²_j, σ²_gj) are pooled.
  - Negative estimates are truncated at 0 and also reported raw.
- **Judge-component uncertainty,** which the transcript bootstrap does not include:
  - σ²_gj: χ² interval on (G − 1)(J − 1) df;
  - σ²_j and σ²_j + σ²_gj: Satterthwaite intervals.

  These sit next to every random-judge output. At J = 3 they are very wide. In the pilot, the 95% upper limits for σ²_j ranged from about 10 to over 500,000 squared score points, which means effectively unbounded.
- **REML sensitivity** (`analysis/reml.py`): the same model on **all valid scores**, unbalanced, without complete-case deletion. Its components and φ are reported next to the ANOVA results.

**φ: what is reported, and why the primary report is an interval.** No estimator of φ from a single Δ̂ is unbiased across the range. Simulation (`analysis/phi.py` docstring), with z = |Δ| / σ:

| Estimator | Bias at z = 0 | Bias at z = 1.5 | Bias at z = 2 | Max RMSE |
|---|---|---|---|---|
| Plug-in φ(Δ̂) | −0.17 | +0.06 | +0.07 | about 0.2 |
| Bias-corrected φ(√max(Δ̂² − Var Δ̂, 0)) | −0.075 | +0.13 | +0.13 | about 0.24 |

Intermediate corrections all have a max |bias| of 0.1 or more. The primary report is therefore:
- **the plug-in point;**
- **its 95% confidence interval,** obtained by inverting the normal interval for Δ;
- the bias-corrected point, alongside.

This is done for each facet: full; judges (transcripts fixed); repeats; transcripts (judges fixed).

**Model check (pre-stated rule).** The design-based split-half estimator uses disjoint transcript halves, two different judges and two repeats. It is unbiased for φ at (J = 1, R = 1, n/2).
- At that design, averaged over the 9 confirmatory contrasts, the model **passes** if:

  mean plug-in φ − 0.05 ≤ mean split-half φ ≤ mean bias-corrected φ + 0.05

- **Simulated pass rate under a true model** at this study's sizes:

  | Setting | Pass rate |
  |---|---|
  | Pilot-like gaps | 95% |
  | Large gaps | 92% |
  | All gaps near 0 | 64% |

  A symmetric ±0.05 rule on either point estimator would pass only 69–76% in the pilot-like case.
- **If the check fails,** H3′, φ and the D-study are reported as exploratory. H1′ and H2′ do not use the model, so they are unaffected.
- On the pilot, the mean split-half φ was 0.27, the plug-in 0.24 and the bias-corrected φ 0.28: **passed**.

**D-study.** φ over J ∈ {1, 2, 3, 4, 6, 8}, R ∈ {1, 2, 3} and n ∈ {10, …, 1000} per target. The cheapest design with φ ≤ 0.05 and with φ ≤ 0.10 is reported for both the plug-in and the bias-corrected Δ. J beyond the observed panel is labelled extrapolation.

**Controls.**
- **Negative control:** planted high- vs low-severity transcripts on each dimension; φ is expected to be ≈ 0. If φ > 0.05 for `concerning`, confirmatory analysis stops until the pipeline is checked.
- **Placebo:** target labels are permuted, 500 times; the true φ is 0.5.
  - Expected means: plug-in ≈ 1/3, bias-corrected ≈ 0.43, split-half ≈ 0.5.
  - A placebo split-half mean outside [0.4, 0.6] flags a pipeline error.

**Reliability, for comparison.** The code reproduces the pilot exactly:
- ICC(2,1), for repeat 1 and for the repeat average;
- Krippendorff's α;
- test-retest ICC;
- the crossed-design variance decomposition;
- rank stability.

**Validity, secondary.** AUC against the planted `expected_dimensions` labels, which record design intent and are not a gold standard.

## 5. Exclusions, missing data and parse failures

- **Parsing:** Petri's parser (`petri_v2/parse.py`). A score counts only if the `<scores>` block holds a valid 1–10 for the dimension.
- **Failures are never floored to 1.** Each is recorded with a reason code: `no_response`, `empty_response`, `no_scores_block`, `no_score_lines`, `dim_missing`, `out_of_range`.
- **Attempts:**
  - First attempt only for parsing.
  - Batch items that error or expire are resubmitted, at most 3 times.
- **Primary analysis:** complete cases per dimension.
- **Sensitivity analyses:**
  - REML on all valid scores (§4);
  - Petri's floor (missing = 1, `--petri-floor`).
- **Failure rates by severity stratum.** These are reported per judge × dimension × planted severity (high / moderate / low) with reason codes (`analysis/data.py: missing_by_stratum`). This checks missingness that depends on severity, such as refusals or content filters on the most severe misuse transcripts.
  - **Pre-stated flag:** if a judge's failure rate on a confirmatory dimension is more than 5 percentage points higher in the high stratum than in the low stratum, that dimension's results are labelled "possibly missing not at random". The REML and Petri-floor results are then shown next to the primary results.
- **Compromised dimensions:** if any confirmatory-panel judge's valid-score rate on a dimension is below 85%, that dimension's confirmatory result is labelled "compromised", and a sensitivity analysis drops that judge. An expanded-panel judge below 85% is reported and dropped from the secondary analyses of that dimension; it cannot affect the confirmatory family.
- **No outlier exclusion.**

## 6. Stopping rule and budget

- **Fixed design, no optional stopping, no interim looks.** No official-judge scores are analysed before all batches of the chosen design have ended.
- **Hard spend caps,** enforced by `--budget-usd` against the dry-run estimate at batch price and 10,000 output tokens per request.

  | Judge | Cap | Dry-run estimate, batch high |
  |---|---|---|
  | Opus 4.5 (260 transcripts) | USD 80 | $74.95 |
  | Gemini 3.1 Pro (260) | USD 40 | $35.18 |
  | GPT-5.1 (260) | USD 30 | $28.49 |
  | Sonnet 5.5 (140) | USD 20 | $16.80 |
  | Gemini 3.8 Flash (140) | USD 10 | $6.06 |
  | GPT-5.4 mini (140) | USD 10 | $7.11 |
  | DeepSeek V4 Pro (140, off-peak) | USD 10 | $6.96 |
  | Kimi K2.6 (140) | USD 10 | $7.95 |
  | **Total** | **USD 210** | **$183.49** |

- **If a cap is reached** or a model is retired mid-run:
  - finish the confirmatory set (positions 121–260) for the three Petri facets before anything else;
  - report what was completed.
- **Deadline.** Opus 4.5 may be retired from **24 Nov 2026**, so the Opus leg runs first.
  - A retired judge is replaced only by its provider's named successor, as a separate facet, never silently.
  - **If Opus 4.5 is not complete for positions 121–260 by 24 Nov 2026, the confirmatory family cannot be run as registered,** and this is reported.

## 7. Deviations from Petri, declared in advance

- Four dimensions instead of Petri's full set.
- First-attempt parsing. Petri retries up to 3 times and then floors to 1.
- Batch APIs instead of synchronous calls. DeepSeek has no Batch API and runs as synchronous off-peak calls.
- Gemini 3.1 Pro Preview instead of the retired Gemini 3 Pro.
- One Petri quirk kept as written: the `{{}}/10` placeholder.
- Opus 4.5 gets `budget_tokens` and no `effort` parameter. This mirrors inspect_ai 0.3.193's mapping of Petri's config; Anthropic's docs recommend setting both for Opus 4.5.

## 8. Before the first paid call

1. Design: **C (J = 8)**, decided 10 Oct 2026.
2. Runners for all eight judges: built and tested offline (mocked HTTP). None has yet made a real API call, so the first submission of each provider is also its first live test; start each provider with the confirmatory 140 only.
3. **File on OSF before any official-judge call.**
