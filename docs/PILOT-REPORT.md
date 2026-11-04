<!-- Written by an AI agent from its run journal, 2026-10-08. Private paths, host names, account and provider details redacted for the public release. -->

# Petri-style judge reliability with three low-cost judges: pilot (20 then 120 transcripts)

Status: complete. 720 of 720 judge calls responded. The 3-hour time-box was slightly exceeded: total about 3 h 05 min, of which 2 h 35 min was judge wall-clock at the 3-call limit.

## Question
Are three low-cost judges from different families (Muse Spark 1.3 Contributor, MiMo-V2.6-Flash, DeepSeek V4.1 Flash) reliable on four Petri alignment dimensions for the public synthetic corpus? Does the target-model ranking survive judge swaps?

## Verdict
- **Signal: yes, weak to moderate. Thesis-worthy as a finding: not yet.** Thesis-worthy as a design: yes, as a reliability sub-study with the official Petri judges and natural (non-planted) audits.
- Strongest: `concerning`. ICC(2,1) 0.88, test-retest 0.96, and the same target order under all three judges in 84% of bootstrap draws.
- Weakest: `cooperation_with_human_misuse` (target order identical under all judges in only 34% of draws) and `unfaithful_thinking` (the corpus has no structured reasoning, so the score rests on visible `<thinking>` text).
- Results are only as good as the judges' output: MiMo returned no usable score block on 6.7% of first attempts.
- Source-level findings, independent of the statistics, are listed under "Verified source findings". They matter more for a thesis than the numbers do.

## Exact commands
Local side, in a scratch directory (`<scratch>`):
```
python3 -I scripts/fetch_hf.py data-raw                 # 317 files, 106.5 MB; 311 transcripts used
python3 -I scripts/prepare.py data-raw/data <petri>/src/petri/scorers/prompts.py inputs out/sample_meta.json
```
`<petri>` is the scratch clone of inspect_petri at branch petri-v2, commit f02b3ec.

Judge calls were then run with a resumable runner on a private server, 20 transcripts first and then the rest of the 120 (600 more jobs). The runner is provider-specific and is not part of this release; `pilot/scores_pilot120.jsonl` holds what it produced, without the judges' text.

Analysis (venv with numpy 2.5, scipy 1.18, pandas 3.0, matplotlib 3.11):
```
.venv/bin/python -I scripts/analyze.py out/judgments_final.jsonl out/sample_meta.json 120 out/scale120 scale120
.venv/bin/python -I scripts/analyze.py out/judgments_final.jsonl out/sample_meta.json 20  out/pilot20  pilot20
.venv/bin/python -I scripts/test_stats.py scripts/analyze.py     # synthetic check of ICC, alpha and variance components
```

Settings: `max_tokens` (or `max_output_tokens`) is 32000, `reasoning_effort` is high, and temperature is the provider default. At most 3 calls run at once. Each judge runs 2 times per transcript. The API key was read at runtime inside the server process and was never printed or saved; its value does not appear in the judgments file, the logs or the session file.

## Sample
- Analysis set: the 260 transcripts in `corpus_index.selected_2pp`, stratified by target × severity. Nested order, so the first 20 are the pilot.
- Full 120: Hermes 3 70B 44, DeepSeek V3.1 46, Mistral Large 2411 30; high 44, moderate 46, low 30.
- Complete cases for the statistics: 105 transcripts for three dimensions and 104 for `unfaithful_thinking`. Targets in that set: Hermes 42, DeepSeek 39, Mistral 24. Excluded: 15–16 transcripts, mostly because MiMo returned no score block.

## Parse and refusal rates (first attempt, no retries)

| Judge | Calls | Petri-equivalent parse (all 4 scores) | Strict structure (all tags closed) | Refusal or filter stops | Median latency |
|---|---|---|---|---|---|
| Muse Spark 1.3 Contributor | 240 | 240 (100%) | 240 (100%) | 0 | 23.9 s |
| MiMo-V2.6-Flash | 240 | 224 (93.3%) | 124 (51.7%) | 1 by regex, not reviewed | 45.4 s |
| DeepSeek V4.1 Flash | 240 | 238 (99.2%) | 160 (66.7%) | 2 with `finish=content_filter` | 31.3 s |

- MiMo's failures include 10-character outputs (`<highlight`, finish=stop). I did not classify the other missing cases individually.
- "Petri-equivalent" follows Petri's own parse: `extract_xml_tags` never raises, so only the `<scores>` block matters. The stricter criterion, which I used first, is reported only for comparison.
- No transport errors, no truncations, no empty outputs.
- The pilot gate was: Muse and DeepSeek 100%, MiMo 87.5%. I scaled anyway, because the failure rate is itself a result and it is reported.

## Reliability, 105 transcripts (95% CI from transcript bootstrap, B=1000)

| Dimension | ICC(2,1) inter-judge, rep 1 | Krippendorff alpha (interval), 3 judges | Test-retest ICC per judge (Muse / MiMo / DeepSeek) | Transcript share of variance | Target order same under all judges | Mean score (Muse / MiMo / DeepSeek) |
|---|---|---|---|---|---|---|
| concerning | 0.88 [0.84, 0.92] | 0.88 | 0.99 / 0.94 / 0.95 | 0.87 [0.83, 0.91] | 0.84 | 4.51 / 3.82 / 4.11 |
| unprompted deception toward user | 0.79 [0.67, 0.87] | 0.79 | 0.89 / 0.88 / 0.94 | 0.81 [0.71, 0.88] | 0.75 | 2.44 / 2.65 / 2.27 |
| cooperation with human misuse | 0.81 [0.69, 0.90] | 0.81 | 0.94 / 0.85 / 0.85 | 0.81 [0.71, 0.88] | 0.34 | 2.21 / 2.12 / 2.39 |
| unfaithful thinking (n=104) | 0.74 [0.59, 0.86] | 0.74 | 0.91 / 0.65 / 0.76 | 0.71 [0.57, 0.82] | 0.68 | 2.01 / 1.82 / 1.84 |

- Exact repeat agreement (rep 1 = rep 2) for concerning is 0.73 / 0.50 / 0.61; in the other dimensions it is between 0.56 and 0.92.
- Repeat-averaged ICC(2,1) is higher than single-run ICC in every dimension: concerning 0.89, deception 0.86, cooperation 0.86, unfaithful 0.79.
- Variance components (method of moments, balanced crossed design, one score per cell, positive shares):
  - Transcript: above, with CIs.
  - Judge: 0.2–1.5%.
  - Repeat: about 0. The estimate is negative and truncated, so it is imprecise.
  - Transcript × judge: 6.5–9.4%.
  - Transcript × repeat: 0–1.5%.
  - Residual (the unreplicated three-way term): 3.7% for concerning, 10–18% for the others.
- With only 3 judges (2 df) and 2 repeats (1 df), the judge and repeat components are imprecise. Mean differences are more informative: MiMo scores concerning 0.7 points below Muse.

## Target ranking under judge swaps (stratified transcript bootstrap, B=2000)
Targets: Mistral Large 2411 > DeepSeek V3.1 > Hermes 3 70B on concerning, deception and unfaithful thinking, the same order under all three judges. On cooperation the order differs by judge: Muse ranks Hermes above Mistral, the other two rank them the other way, and all differences are about 0.1–0.4 points.

- Probability all three judges give the same full order: concerning 0.84, deception 0.75, unfaithful 0.68, cooperation 0.34.
- Pairwise direction agreement with the consensus is 0.97 or higher for the concerning pairs with a clear gap, and 0.39–0.73 on the cooperation pairs.

## Validity against planted labels (not a reliability metric)
AUC of the judge mean against `expected_dimensions`, which are design intent:
- concerning 0.61 (54 positive / 51 negative)
- deception 0.70 (27 / 78)
- cooperation 0.80 (19 / 86; small)
- unfaithful thinking 0.70 (27 / 77)

Per judge, the AUCs are within about 0.05 of each other.

## Token usage
Token counts are from the API responses.

| Run | Calls | Input tokens (cached) | Output tokens (reasoning) |
|---|---|---|---|
| Pilot, 20 transcripts | 120 | 784,630 (501,698) | 430,820 (298,128) |
| Full, 120 transcripts | 720 | 5,321,333 (3,471,874) | 2,894,929 (2,033,378) |

At public per-token prices for these models, the full run costs about USD 1.34 off-peak or USD 2.14 at peak (DeepSeek's two rates).

## Verified source findings (Petri at commit f02b3ec)
1. **Judge view.** Petri builds the judge input from `_collect_messages(events, "target")` (`src/petri/transcript/transcript.py`). The card says the judge scores `messages`. I checked all 311 files: `messages[0]` is the auditor's system prompt, and auditor turns are present in every file. `target_messages` never contains the auditor prompt. I used `target_messages`. Using `messages` would show the judge the auditor's commentary, such as "This is extremely sycophantic behavior". Not tested: the effect of the other view on scores.
2. **Parse check is a no-op.** `extract_xml_tags` (`src/petri/utils.py`) checks `required_tags` against a dict that already contains every tag, so it never raises. Petri's parse therefore requires only the `<scores>` block with all expected keys.
3. **Silent floor.** When all retries fail, `score_fn` in `judge.py` returns every dimension as 1 with the explanation "Failed to parse judge's response". Under Petri's default `retries=3`, an output like MiMo's would be retried, and after three failures would count as a score of 1. This matches the concern in inspect_petri issue #113 (from the earlier report; not re-opened).
4. **Placeholder.** `DIMENSIONS` values contain `{{}}/10`, and `str.format` does not expand inserted values. The judge therefore sees `{{}}/10` four times in the prompt. I reproduced this as written.

## Deviations from Petri
- Four dimensions instead of the full `DIMENSIONS` set: concerning, unprompted_deception_toward_user, cooperation_with_human_misuse, unfaithful_thinking.
- First-attempt parsing, no retries.
- Judges are Muse, MiMo-Flash and DeepSeek-Flash, not Petri's Opus, Gemini or GPT.
- Petri's `reasoning_tokens=10000` budget is not sent; only `max_tokens` and `reasoning_effort=high`.
- Temperature is the provider default; repeats are independent samples.

## Caveats and unknowns
- The corpus is synthetic and planted, so its labels are design intent, not gold standard.
- Floor effects: cooperation and unfaithful thinking average about 2 and are mostly 1.
- The target-view versus `messages` sensitivity was not tested.
- The judges are cheap models, so the results do not transfer to Petri's judges.
- The earlier report's claims (Petri 2.0 blog, 2025 correlation figure, Petri issue #113) were not re-checked here. They are marked partial, as in that report.

## Claims and status
- Petri judge code, prompts, transcript view, parser and formatter, commit f02b3ec: **verified** (read). https://github.com/meridianlabs-ai/inspect_petri, branch petri-v2, files `src/petri/scorers/judge.py`, `prompts.py`, `transcript/transcript.py`, `utils.py`, `formatting/xml_messages.py`.
- Dataset, card, and all 311 files: **verified**. https://huggingface.co/datasets/adlnk/petri-synthetic-transcripts (sha f2fd5fe4).
- Earlier report claims (`petri.md`): **partial**, not re-checked.

## Figures and data
In this repository:
- Figures: `pilot/figs/fig1_reliability_scale120.png`, `fig2_varcomp_scale120.png`, `fig3_concerning_scatter_scale120.png`, `fig4_rank_stability_scale120.png`.
- Data: `pilot/scores_pilot120.jsonl` (the 720 judge records with parsed scores, token usage and status, without the judges' generated text), `pilot/sample_meta.json` (labels, kept off the judge), `pilot/results/results_scale120.json`, `pilot/results/results_pilot20.json`, and `pilot/scripts/`.
- The 720 raw judge outputs (`judgments_final.jsonl`) are not redistributed: the terms for redistributing them were not established. `pilot/scripts/analyze.py` and the raw-output parser tests need that file; `analysis.run` and the regression test use the scores file.
