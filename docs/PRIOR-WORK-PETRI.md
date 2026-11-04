# Pilot: reliability of LLM judges in Petri 2.0 / Bloom audits

Date: 2026-10-07. Status labels: [V] verified (I opened the source or ran the check), [P] partial (secondary text, summary tool, or part of a source), [U] unknown, [I] my inference.

## Verdict

- **Zero-cost preliminary result: no.** Per-judge scores from Petri 2.0's three-judge run are not published anywhere I could find [V]. Without them, no ICC, Krippendorff alpha, variance components or ranking-stability analysis can be computed on the 2026 judges.
- **Zero-cost alternative in the data: partly.** The 2025 launch post has an inter-judge Spearman matrix for five judges, on the "Concerning" metric only, read from a figure [V]. That is prior work, so any thesis must cite and extend it.
- **Verdict: worth it, but only as a paid pilot that Thomas must approve.** Cheapest version: 120 transcripts, 3 cheap judges from 3 families, 2 repeats, about $2 to $4.5 in API calls. Full unscored public corpus (311 transcripts): about $5.6 to $11.6 [I, list prices, assumed token counts]. Estimated work: 10 to 14 h [I]. I made no paid calls.
- Overlap: Phase 2 §7 lists TutorBench judge reliability as the first 12-month artifact. The same crossed-judge design serves both, so Thomas should choose which one gets the hours.

## What is public

| Source | What it contains | Status |
|---|---|---|
| Petri 2.0 post, alignment.anthropic.com/2026/petri-v2 (dated 22 Jan 2026) | 10 target models, 2 auditors (Claude Sonnet 4.5, GPT-5.1), 181 seeds, so 362 transcripts per target. Each transcript judged by Claude Opus 4.5, Gemini 3 Pro and GPT-5.1, giving 1,086 scores per target. Raw text searched for agreement, correlation, kappa, reliability: no hits. Only uncertainty statement: "Error bars are 95% confidence intervals." No data release. | [V] (raw HTML, curl) |
| github.com/safety-research/petri | Now a redirect: API 301 to repositories/1041001082 = meridianlabs-ai/inspect_petri (MIT; main HEAD 766d384, 2026-10-01; 1,364 stars; 42 open issues). The petri-v2 branch holds the 2.0 code (101 commits, HEAD f02b3ec, 2026-06-08). | [V] |
| Repo file trees (main and petri-v2) | No data, results, transcript or per-judge score files. Only source code, docs and tests. | [V] (git clone, grep) |
| evals/target_model_comparison.py (petri-v2) | Runs `alignment_judge` with four judges: claude-opus-4-5-20251101, claude-sonnet-4-5-20250929, gemini-3-pro-preview, gpt-5.1-2025-11-13 (o4-mini commented out). The blog names three judges; the code has four. Per-judge scores go into Inspect logs, which are not in the repo. | [V] |
| github.com/safety-research/bloom | Frozen at its last standalone release; development moved to Meridian Labs. No judge agreement data. | [V] (raw README) |
| Hugging Face (40 datasets matched "petri"; targeted searches for Petri judges with Gemini or GPT names: 0 hits) | adlnk/petri-synthetic-transcripts: 311 Petri transcripts, cc-by-4.0, `judge_output: null` (unscored). Auditor Claude Opus 4.5; targets Hermes 3 Llama 3.1 70B (106), DeepSeek V3.1 (116), Mistral Large 2411 (89). Hidden target behaviours are planted via a modified Petri, so this is synthetic data. The card warns not to show the seeds file to the judge under test. | [V] card |
| | dougalldeepmind dose-sweep and MSM datasets: one judge only (Sonnet 4.5, or claude-opus-5). Not inter-judge. | [V] cards |
| | auditing-agents/petri-transcripts-*, petri-judge-summaries-*: judge model not stated in the card I read. rangell/*petri-judged-*: card not accessible. | [P]/[U] |
| | barissozudogru/petri-bench: unrelated benchmark that happens to use the word "petri" (p-hacking audits). | [V] card |

## Prior reports of Petri judge agreement

- **2025 launch post** (alignment.anthropic.com/2025/petri/) [V, raw HTML]. Five judges (Claude Opus 4.1, Claude Sonnet 4, Gemini 2.5 Pro, GPT-5, o4-mini) act as judge on the same transcripts. Figure "Inter-Judge Correlation Matrix (Spearman), Concerning Metric Only" [V, figure read visually; labels printed to 3 decimals]:

  | Pair | Spearman |
  |---|---|
  | Opus 4.1 – Sonnet 4 | 0.733 |
  | Opus 4.1 – Gemini 2.5 Pro | 0.703 |
  | Sonnet 4 – Gemini 2.5 Pro | 0.747 |
  | Opus 4.1 – GPT-5 | 0.651 |
  | Sonnet 4 – GPT-5 | 0.683 |
  | Gemini 2.5 Pro – GPT-5 | 0.707 |
  | Opus 4.1 – o4-mini | 0.553 |
  | Sonnet 4 – o4-mini | 0.602 |
  | Gemini 2.5 Pro – o4-mini | 0.644 |
  | GPT-5 – o4-mini | 0.646 |

  Mean of the 10 pairs 0.667; range 0.553 to 0.747. The post also says intra-judge correlation (judge sampled twice per transcript) "was typically between 0.75 and 0.85" in "preliminary experiments" [V text]. No n, no data, no CI. It also admits the judge "will sometimes exhibit inconsistencies in edge cases" [V].
- **Petri 2.0 post (2026):** no agreement statistic [V]. The 2026 judges (Opus 4.5, Gemini 3 Pro, GPT-5.1) have not been reported on agreement by their authors.
- **GitHub issues, inspect_petri** [V, GitHub API bodies and comments]:
  - #9 "Multi judge ensemble scoring" (2025-10-14, closed 2025-10-21). A maintainer replied that multi-judge scoring is already in target_model_comparison.py and was used for the 2025 release.
  - #113 (open, 2026-06-18): judge refusals and failed audits silently lower reported concern. A judge-reliability failure mode, not an agreement statistic.
  - #174 (open, 2026-10-06): clean-model false-confession study. Two judges (Gemma 4 12B and gpt-oss-20b) agree on 77% of runs, kappa 0.38. Not Petri's judges.
- **Papers since Jan 2026:** I found none that analyse Petri's judges. Nearby work:
  - arXiv 2607.01245 [V, full HTML]: three judges (GPT-5.4 Thinking low, Gemini 3.1 Pro, Claude Opus 4.6); Cohen's kappa 0.58 to 0.77 across leave-one-out pairs; not Petri.
  - arXiv 2608.02442, 2608.13840, 2607.24339: search snippets only, [U]. The snippet's kappa values were not in the page text I could read.

## What I ran

All work was in a local scratch directory (raw/, clone-petri-v2/, clone-main/, scripts/, out/; path redacted).

```
curl -sL -m 60 https://alignment.anthropic.com/2026/petri-v2 -o raw/petri-v2.html
curl -sL -m 60 https://alignment.anthropic.com/2025/petri/ -o raw/petri-2025.html
curl -s  https://api.github.com/repos/safety-research/petri        # 301 to repositories/1041001082
curl -sL https://api.github.com/repositories/1041001082             # = meridianlabs-ai/inspect_petri
curl -s  "https://api.github.com/repos/meridianlabs-ai/inspect_petri/git/trees/petri-v2?recursive=1"
git clone --branch petri-v2 https://github.com/meridianlabs-ai/inspect_petri.git clone-petri-v2   # read only, nothing executed
git clone https://github.com/meridianlabs-ai/inspect_petri.git clone-main                        # read only
grep -rn -i -E "opus-4|gemini-3|gpt-5\.1|three judges|krippendorff|kappa|ensemble" clone-petri-v2  # quoted pattern
curl -s "https://api.github.com/search/issues?q=repo:meridianlabs-ai/inspect_petri+judge+agreement"  # and other judge queries
curl -s https://api.github.com/repos/meridianlabs-ai/inspect_petri/issues/{9,113,174}  (+ /comments)
curl -s "https://huggingface.co/api/datasets?search=petri&limit=50"; /api/datasets/<id>; raw README at huggingface.co/datasets/<id>/raw/main/README.md
curl -s -m 60 https://openrouter.ai/api/v1/models -o raw/openrouter-models.json   # 467 models, prices
curl -sL https://www.anthropic.com/pricing -o raw/anthropic-pricing.html           # Haiku 5.5 price text
# 2025 Spearman figure: WebFetch on figures/corellation_matrix.png (returned text failed; the tool saved the PNG), then read visually
python3 -I scripts/icc_sim.py            > out/icc_sim.txt
python3 -I scripts/cost_table.py raw/openrouter-models.json > out/cost_table.txt
```

Notes on the tools: the WebFetch summary of the OpenRouter list returned 10 models with no prices, which contradicted the live JSON. I discarded it and used the curl output. WebFetch summaries of GitHub pages were checked against raw text and API output; claims that rest only on a summary are marked [P].

## Cost and power (estimates, not spent)

- Token assumption: about 12.3k input and 0.7k output tokens per judge call. This is a proxy from the dougalldeepmind dose-sweep card (Sonnet 4.5 judge, Petri transcripts) [V card, [I] for this corpus]. The corpus length was not measured, so treat costs as roughly ±2x.
- Prices: OpenRouter list prices, live via curl 2026-10-07. Haiku 5.5 matches Anthropic's pricing page ($0.10 input, $0.50 output per MTok up to 100K tokens) [V]. The other prices are OpenRouter-only [P].

| Design | Calls | Cost (no reasoning to +3k reasoning per call) |
|---|---|---|
| Pilot A: 120 transcripts x 2 reps x 3 cheap judges (claude-haiku-5.5, gpt-5.6-luna, gemini-3.1-flash-lite) | 720 | about $2.2 to $4.5 |
| Full corpus: 311 x 2 reps x same 3 judges | 1,866 | about $5.6 to $11.6 |
| Full corpus: 311 x 1 rep x same 3 judges | 933 | about $2.8 to $5.8 |
| Reference judge Opus 5 (list $5/$25): 311 x 1 rep | 311 | about $24.6 to $47.9 |
| Blog-scale judging only: 3,620 transcripts x 3 cheap judges x 1 rep | 10,860 | about $33 to $67 (excludes generating audits) |

- Generating new audits is the expensive part and I did not price it. The repo README gives token totals for one 111-seed, 30-turn batch: about 18.5M tokens across three roles [V README]. The pilot avoids this by using the unscored public corpus.
- Power: simulation of ICC(2,1) with k=3 judges, true ICC 0.5, 400 replicates, seed 1 [I, idealised: no judge bias, independent noise]. Approximate 95% CI half-width: 0.21 (30 items), 0.15 (60), 0.10 (120), 0.07 (311). A 120-item pilot cannot separate ICC 0.5 from 0.7 reliably. The full corpus can.
- Consistency check: 181 x 2 x 3 = 1,086 scores per target, which matches the blog's own number [V].

## Estimated work

About 10 to 14 h [I]: format conversion and Inspect setup 3 to 4 h; judging about 1 h wall clock; analysis (ICC, alpha, variance components, ranking stability under judge subsets with item bootstrap) 3 to 4 h; write-up 2 to 3 h.

## What would change the verdict

1. Per-judge logs for the 2026 run are released (or Meridian publishes them). Then the question is answered at near-zero cost, with 3 to 4 h of analysis. Strong reason to switch to that route.
2. A 2026 paper or report already gives per-judge agreement for Petri 2.0's judges. Then the pilot becomes a replication, or is dropped.
3. The cheap judges fail the Petri judge prompt (refusals, parse errors). Issue #113 shows refusals silently remove scores. Then a stronger judge is needed, and costs rise 5 to 10x (Opus 5 is about $25 to $48 per 311 calls).
4. Real transcripts are about 2x longer than the 12.3k-token assumption: costs double.
5. The synthetic planted-behaviour corpus is judged unrepresentative of Petri 2.0's default seeds: the design must include audits, which I did not price.
6. Thomas gives the hours to TutorBench (Phase 2 §7): the Petri pilot becomes "not now".

## Context from the phase files (read only)

- Phase 1 lists measurement, evaluation design and judge reliability as a skill that gains value in all three scenarios.
- Phase 2 names evaluation and measurement science as the first bet, with TutorBench judge reliability as the first artifact.

## Limits and compliance

- No paid API calls; no issues, PRs or posts; nothing modified or committed in Thomas's repos. Repo clones are scratch copies, and no repo code was executed.
- Downloads: no Hugging Face dataset files were downloaded, only API metadata and READMEs. The 2025 figure PNG was saved by WebFetch to a local tool-results directory (path redacted) and read visually; I did not copy it elsewhere.
- The 2025 Spearman values are read visually; a misreading of about 0.001 is possible.
- Several arXiv results rest on search snippets [U].
- No figure was produced (matplotlib is not installed). Scripts and outputs are in scratch: `scripts/icc_sim.py`, `scripts/cost_table.py`, `out/icc_sim.txt`, `out/cost_table.txt`.
