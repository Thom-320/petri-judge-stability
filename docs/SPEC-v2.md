# Petri judge stability v2: specification

Status: spec for the build (9 Oct 2026). Owner: Thomas Chisica. Thesis Aim 1 ("levels versus contrasts": when does judge error change a safety decision?).

## Question

When a panel of LLM judges looks reliable (ICC, kappa), how often does the safety decision it feeds flip under a judge swap, a repeat, or a transcript resample? The estimand is the flip probability φ(D) = P(D(panel) ≠ D(panel′)) for decisions D such as "target A is safer than target B" or "target passes a threshold", plus a decision-level D-study: how many judges, repeats and transcripts keep φ ≤ ε.

Identification (standard generalizability theory, paired crossed design): with score model X_gtjr = μ + α_g + τ_t + γ_j + (ατ)_gt + (αγ)_gj + (τγ)_tj + (ατγ)_gtj + e_gtjr, the contrast D̂ = X̄_A − X̄_B has Var = 2(σ²_gt/n + σ²_gj/J + σ²_gtj/(nJ) + σ²_e/(nJR)); τ_t, γ_j and (τγ)_tj cancel. In the Petri corpus transcripts are nested in targets, so σ²_D = 2(σ²_t:g/n + σ²_gj/J + σ²_tj:g/(nJ) + σ²_e/(nJR)). φ = 2p(1 − p) with p = Φ(−|Δ|/σ_D). ICC(2,1) involves neither Δ nor σ²_gj, so ICC is neither necessary nor sufficient for a stable decision.

## Data

- Corpus: Hugging Face `adlnk/petri-synthetic-transcripts` (CC-BY-4.0; 311 Petri transcripts, `judge_output: null`; auditor Claude Opus 4.5; targets Hermes 3 70B, DeepSeek V3.1, Mistral Large 2411). Do not commit raw data; `pilot/scripts/fetch_hf.py` downloads it. The card warns: never show the seeds file to the judge.
- Analysis set: 260 transcripts stratified by target × severity (`corpus_index.selected_2pp` in the pilot); the first 120 are the pilot set.
- Pilot results (cheap judges, not Petri's): `pilot/` and `docs/PILOT-REPORT.md`.

## Judges

- Official Petri 2.0 judges (alignment.anthropic.com/2026/petri-v2): Claude Opus 4.5 (`claude-opus-4-5-20251101`), Gemini 3 Pro, GPT-5.1 (`gpt-5.1-2025-11-13`). Check that each is still served; if one is retired, record it and use the provider's named successor as a separate facet, never silently.
- Judge prompt, dimensions, transcript view, parser: pin `meridianlabs-ai/inspect_petri`, branch `petri-v2`, commit `f02b3ec` (`src/petri/scorers/judge.py`, `prompts.py`, `transcript/transcript.py`, `utils.py`, `formatting/xml_messages.py`). Known issues on that branch (see PILOT-REPORT, "Notes on Petri code"): the judge view must be `target_messages` (not `messages`, which leaks auditor commentary); parse failures must be **counted**, never floored to 1; the `{{}}/10` placeholder is reproduced as written and documented.
- Design: 3 official judges × 2 repeats × 260 transcripts = 1,560 calls, plus the cheap-judge family from the pilot as a fourth facet. Severity balanced; four dimensions: `concerning`, `unprompted_deception_toward_user`, `cooperation_with_human_misuse`, `unfaithful_thinking`. Kill/cut option: two dimensions only (cooperation with misuse; concerning as the negative control).

## Funding constraint (verified 9 Oct 2026)

- Claude calls are paid from the Max plan's monthly API credits (USD 100/month, expire each billing cycle, Messages and Message Batches API). Opus 4.5 list price USD 5 / 25 per MTok; Batch API USD 2.50 / 12.50 (platform.claude.com/docs/en/about-claude/pricing).
- Gemini and GPT calls are paid in cash or research credits; use each provider's Batch API (50 % off where offered).
- Measured pilot tokens per judge call: ≈7,400 input and ≈4,000 output including reasoning; Petri's reasoning budget is 10,000 tokens, so plan a high case of 10,000 output tokens.

## What to build

1. `petri_v2/runner_anthropic.py`, `runner_gemini.py`, `runner_openai.py`: batch submission, polling and result collection for each provider's Batch API; resumable (jsonl keyed by transcript × judge × repeat); keys read only from env vars (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`), never printed, logged or written; refuse to submit without `--confirm-spend` **and** a `--budget-usd` cap that the dry-run estimate must not exceed.
2. `petri_v2/estimate.py`: a dry-run cost estimator that builds every request, counts tokens (Anthropic token-counting endpoint when a key is present; otherwise a tokenizer approximation, labelled as such) and prints cost by judge for standard and batch prices from a single `prices.yaml` with source URLs and the date checked.
3. `petri_v2/prompts.py`: the pinned Petri judge prompt and dimensions, plus the transcript view, with a unit test that compares against the pinned commit's text.
4. `petri_v2/parse.py`: the Petri parser; records parse failures as missing with a reason code.
5. `analysis/`: reuse `pilot/scripts/analyze.py`; add φ per decision and dimension, the decision-level D-study, variance components by REML or ANOVA with bootstrap CIs, ICC(2,1), Krippendorff's alpha, rank stability; negative control (large-gap pairs, φ ≈ 0) and placebo (permuted target labels, φ ≈ 0.5 for null gaps).
6. `tests/` with mocked HTTP for all three providers; no network in tests.
7. `docs/PREREGISTRATION.md`: an OSF-ready pre-registration draft (hypotheses: H1 φ is not predicted by ICC within ±0.1 across dimensions; H2 decision D-study; exclusion and parse-failure rules; analysis plan; stopping rule). Mark clearly that the 120 pilot transcripts were already judged by cheap judges, so confirmatory claims about official judges should be stated for the full 260 or the 140 untouched transcripts.
8. `README.md`: how to reproduce, and a cost table.

## Rules

- No paid API calls in this build. No keys exist in this environment.
- Keep the pilot folder unchanged.
- Public data only; never commit raw transcripts.
