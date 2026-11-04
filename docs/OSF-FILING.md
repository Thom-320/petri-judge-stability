# OSF filing text (OSF Preregistration template)

Source: `docs/PREREGISTRATION.md`, revision 2 (10 Oct 2026), Design C. Each section below is one field of the OSF Preregistration template, ready to paste. OSF text boxes do not render tables, so everything is written as plain lists.

**Before pasting, check these three things:**
- **Code access.** The analysis code is cited by the tag `prereg-v2` of `github.com/thom-320/petri-judge-stability` (the first public commit; its code matches the private commit the plan was drafted against, apart from docstrings). If the repository is private, attach a zip of that commit to the registration (OSF "Files"), or make the repository public. Otherwise reviewers cannot see the code the plan points to.
- **Author line.** Fill in your affiliation.
- **Date.** File before any official-judge call. The Opus 4.5 leg is submitted after the registration timestamp.

---

## Study Information

### Title

Do frontier LLM judges disagree in calibration or in ranking? Decision stability of Petri 2.0's alignment-audit judges

### Authors

Thomas Chisica ([affiliation])

### Description

Petri is an open-source alignment-auditing tool. An auditor model interacts with a target model, and LLM judges score each transcript on a 1–10 scale for dimensions such as "concerning" behaviour. Petri reports the mean score per dimension over transcripts.

This study asks how frontier judges disagree when they score the same transcripts:
- **Calibration (level):** one judge scores everything higher than another.
- **Ranking:** judges disagree about which target model looks worse.

It also asks whether that difference changes the decisions Petri's scores feed. Two kinds of decision are compared:
- **Threshold decisions:** is a target's mean at or above a cut-off?
- **Contrast decisions:** is target A scored above target B?

The two decisions should react differently to calibration. A judge's overall level shift cancels in a contrast between targets but not in a threshold decision.

Design:
- Corpus: 260 public Petri transcripts (CC-BY-4.0) of three target models.
- Judges: eight LLM judges, each scoring every transcript twice. The three Petri 2.0 judges are the fixed confirmatory panel.
- Confirmatory tests are design-based. They use a transcript bootstrap and do not depend on a statistical model.
- A secondary, model-based generalizability (G/D-study) analysis estimates how many judges, repeats and transcripts keep the decision flip probability low.

### Hypotheses

**Confirmatory panel.** All confirmatory hypotheses concern the three Petri 2.0 judges, treated as fixed:
- Claude Opus 4.5;
- Gemini 3.1 Pro Preview, the named successor of the retired Gemini 3 Pro;
- GPT-5.1.

**Confirmatory dimensions:** "concerning", "unprompted_deception_toward_user" and "cooperation_with_human_misuse".

**Primary dataset:** the 140 transcripts that no judge has scored before (analysis-order positions 121–260).

**H1′: calibration offset exceeds contrast discrepancy.** For each confirmatory dimension, judge pair (j, k) and target pair (A, B):

D = |μ_j − μ_k| − |Δ_j(A,B) − Δ_k(A,B)|

- μ_j is judge j's unweighted mean of the three target means, with repeats averaged.
- Δ_j(A,B) is judge j's mean score for target A minus its mean for target B.
- H1′ predicts that the mean of D over the 9 cells (3 judge pairs × 3 target pairs) is greater than 0.

**H2′: judges flip threshold decisions more than contrast decisions.** The cut-offs are c = 4 and c = 7, Petri's own colour thresholds at the pinned commit (≥ 7 "high", ≥ 4 "medium"). For each confirmatory dimension and cut-off, H2′ predicts FT_c − FC > 0, where:
- **FT_c** is the probability that two different judges disagree on "target mean ≥ c".
- **FC** is the probability that two different judges disagree on "target A's mean > target B's mean".
- Both rates use one judge, one repeat and the same transcripts per panel. They are averaged over judge pairs, repeat pairings and targets or target pairs.

**H3′ (secondary, model-based, no test):** the judge floor of the decision flip probability φ as the number of transcripts goes to infinity, reported as a bound.

**Pilot evidence, disclosed as predictions against interest.** A pilot ran these exact tests once on 120 transcripts with three cheap judges (not the study judges):
- H1′ was not supported on any dimension. Mean D was +0.19, −0.05 and −0.12, every 95% CI included 0, and 0 of 9 cells had a lower bound above 0 on each dimension.
- H2′ was not supported for any dimension × cut-off.
- The hypotheses can therefore fail, and whichever way they come out, the result will be reported.

---

## Design Plan

### Study type

Observational study: measurement of existing text data by LLM judges. There is no human participant and no manipulation of the transcripts.

### Blinding

- Judges never see target labels, planted severity, the "expected_dimensions" labels or the scenario seed file.
- Each judge receives only Petri's judge prompt and the transcript in Petri's own judge view.
- No official-judge score will be looked at before all batches of the registered design have finished. There are no interim analyses.

### Is there any additional blinding in this study?

- Model-based outputs (φ, D-study, H3′) are reported as exploratory if a pre-stated model check fails (see Inference criteria).
- The confirmatory tests do not use the model, so this rule cannot change them.

### Study design

**Corpus.** The Hugging Face dataset "adlnk/petri-synthetic-transcripts" (CC-BY-4.0, revision f2fd5fe4):
- 311 Petri transcripts with no judge output;
- auditor: Claude Opus 4.5;
- targets: Hermes 3 70B, DeepSeek V3.1 and Mistral Large 2411.

**Analysis set.** The 260 transcripts in the dataset's "selected_2pp" index.
- Stratified by target × planted severity.
- By target: Hermes 95, DeepSeek 100, Mistral 65.

**Factors** (all crossed, except that transcripts are nested in targets):
- target (3);
- transcript (nested in target);
- judge (8);
- repeat (2 independent calls per transcript × judge).

**Judges: the confirmatory panel (fixed), which scores all 260 transcripts.**
- claude-opus-4-5-20251101
- gemini-3.1-pro-preview
- gpt-5.1-2025-11-13

**Judges: the expanded panel, which scores the 140 confirmatory transcripts only.** Stated population: frontier and mid-tier LLM judges served on 2026-10-10, from at least 4 developers.
- claude-sonnet-5-5 (Anthropic, mid tier)
- gemini-3.8-flash (Google, mid tier)
- gpt-5.4-mini-2026-03-17 (OpenAI, mid tier)
- deepseek-v4-pro (DeepSeek, open weights)
- kimi-k2.6 (Moonshot AI, open weights)

The expanded panel is used for the H3′ bound, the random-judge D-study and a secondary replication of H1′/H2′ over all judge pairs. It never enters the confirmatory family.

**Judge input.**
- Petri's judge prompt and dimension definitions, byte for byte, from meridianlabs-ai/inspect_petri, branch petri-v2, commit f02b3ec. This includes a literal "{{}}/10" placeholder in that version, kept as written.
- The four dimensions are scored together in one call.
- The transcript view is the one Petri's judge builds: the target's view replayed from events, with rolled-back branches kept and marked.

**Generation settings.** These follow Petri's judge config: max_tokens 32,000, reasoning budget 10,000, reasoning effort "high". Mapped per provider:

| Judge | Setting sent |
|---|---|
| Opus 4.5 | extended thinking with budget_tokens 10,000 |
| Sonnet 5.5 | adaptive thinking, effort high |
| Gemini | thinkingLevel HIGH |
| OpenAI | reasoning.effort high |
| DeepSeek | thinking enabled, reasoning_effort high |
| Kimi | thinking enabled |

No request sets temperature, top_p or top_k. Each provider's default sampling applies, and with reasoning on that default is fixed or required.

**Calls.** 2,960 judge calls in total:
- 3 × 2 × 260 = 1,560 for the confirmatory panel;
- 5 × 2 × 140 = 1,400 for the expanded panel.

Calls go through each provider's Batch API, except DeepSeek, which has none. DeepSeek uses synchronous calls in its off-peak window only.

### Randomization

There is no random assignment. The order of the 260 transcripts is a fixed, stratified ordering, created with seed 20261007 before any study judge was run:
- each target × severity cell is shuffled;
- the cells are then merged in a greedy nested proportional order;
- positions 1–120 are the pilot set.

Bootstrap and permutation procedures use these fixed seeds:
- confirmatory bootstrap: 20261010;
- φ analyses: 20261009;
- reliability statistics: 20261008.

---

## Sampling Plan

### Existing data

Registration prior to creation of data. The outcome data are the official-judge scores, and none exist yet. See "Explanation of existing data" for the transcripts and the pilot.

### Explanation of existing data

- **The transcripts are public and existed before this study.** No study judge has scored any of them.
- **Pilot.** 120 of the 260 transcripts (positions 1–120) were scored in a pilot by three inexpensive judges: Muse Spark 1.3, MiMo-V2.6-Flash and DeepSeek V4.1 Flash. None of these is a study judge.
- **What the pilot was used for:** developing and checking the analysis code, and running the revised tests once, as disclosed under Hypotheses.
- **Revision history.** The hypotheses were revised after an independent review of an earlier draft. That review found the earlier hypotheses true by construction and their thresholds chosen near observed means.
  - The revised cut-offs (4 and 7) were taken from Petri's source code before the revised tests were run on any data.
  - Nothing was changed after the pilot run.
- **Consequences for the claims:**
  - Confirmatory claims rest on the 140 transcripts never scored by any judge (positions 121–260).
  - All 260 transcripts form a secondary analysis.
  - Results on positions 1–120 alone are exploratory.

### Data collection procedures

- Requests are built from the pinned Petri prompt and judge view and submitted through the providers' APIs by the scripts in petri_v2/ (tag prereg-v2).
- Each script refuses to submit unless a spend confirmation flag is given and the dry-run cost estimate is within a stated budget.
- Responses are parsed with a port of Petri's own parser, which is checked against Petri's code on 720 pilot outputs.
- A score counts only if the response's scores block contains a valid integer from 1 to 10 for that dimension.
- **Submission order:**
  1. Opus 4.5 on positions 121–260.
  2. Opus 4.5 on positions 1–120.
  3. Gemini 3.1 Pro and GPT-5.1, positions 121–260 and then 1–120.
  4. The five expanded-panel judges, positions 121–260.

### Sample size

- 260 transcripts in total, with 140 of them confirmatory: Hermes 51, DeepSeek 54, Mistral 35.
- 8 judges.
- 2 repeats.
- 2,960 judge calls.

### Sample size rationale

**No formal power analysis was performed.**
- **What fixed the sample size:** the transcript count comes from the public corpus. The repeat count and the expanded panel were set by budget (a dry-run estimate of about USD 183 at batch prices) and by the retirement schedule of the judge models.
- **Why the expanded panel:** with three judges, a judge variance component has 2 degrees of freedom, and its 95% interval spans about 146-fold. With eight judges it has 7 degrees of freedom and spans about 9.5-fold.
- **Power for H1′:** the pilot suggests H1′ has adequate power only if the official judges' calibration offsets are about 0.3 score points or larger. This limitation is accepted and stated in advance.

### Stopping rule

The design is fixed. All registered calls are submitted once, with no optional stopping and no interim looks.
- Provider-side failures (errored or expired items) are resubmitted, at most 3 attempts per request.
- Parse failures are not retried.

**Hard spend caps per judge:**

| Judge | Cap (USD) |
|---|---|
| Opus 4.5 | 80 |
| Gemini 3.1 Pro | 40 |
| GPT-5.1 | 30 |
| Sonnet 5.5 | 20 |
| Gemini 3.8 Flash | 10 |
| GPT-5.4 mini | 10 |
| DeepSeek V4 Pro | 10 |
| Kimi K2.6 | 10 |

If a cap is reached or a model is retired during the study:
- the confirmatory set for the three Petri judges is completed before anything else;
- whatever was completed is reported.

Deadlines and replacement rules:
- Opus 4.5 may be retired from 24 Nov 2026. If its confirmatory leg is not complete by then, the confirmatory family cannot be run as registered, and this will be reported.
- A retired judge is replaced only by its provider's named successor, reported as a separate judge, never silently.

---

## Variables

### Manipulated variables

None.

### Measured variables

- **Judge scores:** integers from 1 to 10 for four Petri dimensions, per transcript × judge × repeat.
  - Confirmatory: concerning, unprompted_deception_toward_user, cooperation_with_human_misuse.
  - Exploratory: unfaithful_thinking.
- **Response metadata:** finish reason, token usage, and a parse-failure reason code for each missing score. The codes are no_response, empty_response, no_scores_block, no_score_lines, dim_missing and out_of_range.
- **Corpus labels, never shown to judges:** target model, planted severity (high / moderate / low) and planted expected dimensions.

### Indices

Per dimension, with judges j and k, targets A and B, and m_gjr the mean score of target g from judge j, repeat r:
- **μ_j:** the unweighted mean over targets of judge j's target means, with repeats averaged.
- **Δ_j(A,B):** judge j's target mean for A minus its target mean for B, with repeats averaged.
- **D (H1′):** |μ_j − μ_k| − |Δ_j(A,B) − Δ_k(A,B)|, averaged over the 9 cells.
- **FT_c (H2′):** the mean over targets, judge pairs and repeat pairings (r, r′) of 1[(m_gjr ≥ c) ≠ (m_gkr′ ≥ c)], for c ∈ {4, 7}.
- **FC (H2′):** the mean over target pairs, judge pairs and repeat pairings of |sign(m_Ajr − m_Bjr) − sign(m_Akr′ − m_Bkr′)| / 2. A tie against a strict order counts as half a flip.
- **Transcript-level versions of FT_c and FC (secondary):**
  - FT_c compares single transcript scores with c.
  - FC compares orderings of cross-target transcript pairs.
- **Repeat baselines:** the same flip rates within a judge (repeat 1 vs repeat 2).
- **φ (secondary):** the probability that two independent replications of the full measurement procedure reach different decisions. Model-based: φ = 2p(1 − p), with p = Φ(−|Δ| / σ_D).

---

## Analysis Plan

### Statistical models

**Confirmatory (H1′, H2′): design-based, no statistical model.**
- Judges are fixed. Inference is over transcripts, through a bootstrap that resamples transcripts within each target (B = 2,000, seed 20261010).
- The estimate of FT_c − FC is the bootstrap mean, which is the judge-swap flip probability under transcript resampling.
- Each test uses a one-sided bootstrap p-value: (1 + number of bootstrap statistics ≤ 0) / (B + 1).

**Secondary (H3′, φ, D-study): a variance-component model.**

X = μ + α_target + τ_transcript(target) + γ_judge + (αγ)_target×judge + (τγ)_transcript×judge(target) + e

- Estimated by ANOVA / expected mean squares on complete cases.
- Transcript-level components are estimated separately per target. Judge components are pooled.
- Negative variance estimates are truncated at 0 and also reported raw.
- Judge-component uncertainty, which the transcript bootstrap does not cover, is reported as:
  - a chi-square interval for the target × judge variance (df = (3 − 1)(J − 1));
  - Satterthwaite intervals for the judge variance, and for judge plus target × judge.

**H3′ judge floor** (number of transcripts → infinity), for J = 1, 3 and 8:
- contrast decisions: σ_D² = 2σ²_target×judge / J;
- threshold decisions: σ_D² = (σ²_judge + σ²_target×judge) / J.

It is reported as a bound. The bound combines the variance-component interval with the normal interval for the decision gap, each at 97.5%, for a joint coverage of at least 95%.

**How φ is reported.** No estimator of φ from one observed gap is unbiased across the range (simulation: maximum absolute bias of about 0.1 or more for every correction tried). The primary report is therefore:
- the plug-in point;
- a 95% confidence interval obtained by inverting the normal interval for the gap;
- a bias-corrected point alongside.

**D-study:** φ over J ∈ {1, 2, 3, 4, 6, 8}, R ∈ {1, 2, 3} and transcripts per target from 10 to 1,000. The cheapest designs with φ ≤ 0.05 and φ ≤ 0.10 are reported. Designs with more judges than observed are labelled extrapolation.

**Comparison statistics:**
- inter-judge ICC(2,1);
- Krippendorff's alpha (interval);
- test-retest ICC per judge;
- rank stability of the target order;
- AUC against planted labels, which record design intent and are not a gold standard.

**Descriptive display:** ICC and alpha per dimension shown next to the range of φ over that dimension's decisions. This is not tested.

### Transformations

- No transformation of scores.
- Target means are unweighted means over that target's transcripts, with repeats averaged where stated.

### Inference criteria

**Confirmatory family:** 9 tests.
- H1′ for each of the 3 confirmatory dimensions.
- H2′ for each of the 3 confirmatory dimensions × 2 cut-offs (4, 7).
- Holm correction across the 9 tests, familywise α = 0.05.
- Tested on the 140 confirmatory transcripts. The 260-transcript analysis is secondary and outside the family.

**H1′ is supported for a dimension if both hold:**
- (i) the Holm-adjusted one-sided p-value for mean D > 0 is below 0.05;
- (ii) at least 6 of the 9 cells have a 95% bootstrap lower bound above 0. This is a consistency requirement and is not multiplicity-controlled.

**H2′ is supported** for (dimension, c) if the Holm-adjusted one-sided p-value for FT_c − FC > 0 is below 0.05.

**Model check (governs only H3′, φ and the D-study).**
- A design-based split-half estimator is compared with the model at one judge, one repeat and half the transcripts. It uses disjoint transcript halves, two different judges and two repeats, and is unbiased at that design.
- The model passes if, averaged over the 9 confirmatory target contrasts:

  mean plug-in φ − 0.05 ≤ mean split-half φ ≤ mean bias-corrected φ + 0.05

- In simulation under a true model, this rule passed in 95% of datasets with pilot-like gaps, 92% with large gaps and 64% with all gaps near zero.
- If it fails, H3′, φ and the D-study are reported as exploratory.

**Pipeline controls:**
- **Negative control** (planted high vs low severity): if φ > 0.05 on "concerning", confirmatory analysis stops until the pipeline is checked.
- **Placebo** (target labels permuted 500 times, true φ = 0.5): if the split-half mean falls outside [0.4, 0.6], a pipeline error is flagged.

### Data exclusion

- No outlier exclusion.
- A missing score is never replaced by 1. Petri's default does this; here it is used only as a sensitivity analysis.
- **Primary analysis:** complete cases per dimension. A transcript enters a dimension's analysis only if every judge × repeat returned a valid score for it.
- **Compromised dimension:** if any confirmatory-panel judge's valid-score rate on a dimension is below 85%, that dimension's confirmatory result is labelled "compromised", and a sensitivity analysis without that judge is reported.
- **Expanded-panel judges:** a judge from the expanded panel whose valid-score rate on a dimension is below 85% is reported and dropped from that dimension's secondary analyses. It cannot affect the confirmatory family.

### Missing data

- **Reporting:** missing scores are reported by judge, dimension, reason code and planted-severity stratum.
- **Pre-stated flag:** if a judge's failure rate on a confirmatory dimension is more than 5 percentage points higher in the high-severity stratum than in the low stratum, that dimension's results are labelled "possibly missing not at random".
- **Sensitivity analyses,** reported next to the primary results:
  - REML on all valid scores (unbalanced, no complete-case deletion);
  - Petri's floor (missing = 1).

### Exploratory analysis

- **"unfaithful_thinking."** It is exploratory because no target in the corpus produces native reasoning.
  - Only auditor-prompted in-text thinking tags exist, in 2 of 95 Hermes, 26 of 100 DeepSeek and 42 of 65 Mistral transcripts.
  - Petri's rubric assigns 1 when no tags are present.
  - It is also reported for the subset of transcripts that contain thinking tags.
- **Transcript-level H2′,** with repeat baselines.
- **Threshold flip curve** FT(c) for c ∈ {2, 3, 5, 6, 8, 9}.
- **H1′/H2′ statistics over all 28 judge pairs** of the eight-judge panel.
- **Descriptive split of the judge variance** into developer and tier parts (Anthropic, Google and OpenAI each have a frontier and a mid-tier judge).
- **Results on positions 1–120 alone,** and comparison with the cheap-judge pilot.

---

## Other

### Other

**Deviations from Petri, declared in advance:**
- Four dimensions instead of Petri's full set.
- First-attempt parsing. Petri retries up to 3 times and then fills missing scores with 1.
- Batch APIs instead of synchronous calls. DeepSeek runs as synchronous off-peak calls.
- Gemini 3.1 Pro Preview replaces the retired Gemini 3 Pro.
- Opus 4.5 receives a thinking budget without an effort parameter. This mirrors how inspect_ai maps Petri's configuration; Anthropic's documentation recommends setting both.

**Scope of claims:**
- Target-side claims concern these three targets only. With 3 targets, the target × judge variance has (3 − 1)(J − 1) degrees of freedom whatever the number of judges.
- Random-judge statements are extrapolations from eight judges, from a stated population.

**Materials:**
- Code, pinned prompt copies, the parser, cost estimates and the full plan: github.com/thom-320/petri-judge-stability, tag prereg-v2.
- The full pre-registration document with derivations: docs/PREREGISTRATION.md.
- The pilot report: docs/PILOT-REPORT.md.
