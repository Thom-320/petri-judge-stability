# Cloud session, 9 Oct 2026: v2 build

- **Branch:** `v2-build` (private development history; this repository starts from a clean snapshot).
- **No paid API calls.** No keys exist in this environment.
- **Nothing posted:** no emails, issues or PRs.
- **`pilot/` is unchanged.**

Status labels: **[V]** verified (source opened, code run, or test passing); **[I]** my inference.

## 1. Verdict first

1. **The build is complete for SPEC items 1–8, and 59 of 59 tests pass offline.** [V]
   - The Petri-faithful prompt, view and parser are checked against Petri's own code on the real corpus and on all 720 pilot outputs.
   - The new analysis code reproduces every pilot statistic to 1e-12.
2. **Petri 2.0's exact judge panel can no longer be run.** [V]
   - Gemini 3 Pro Preview was shut down on 2026-03-09. The Gemini facet is now `gemini-3.1-pro-preview`, a different model, and it is labelled as such.
   - Claude Opus 4.5 may be retired from **24 Nov 2026**, so the Anthropic leg has a deadline about 6 weeks away.
   - GPT-5.1 is deprecated and will be removed on 1 Apr 2027.
3. **The spec's judge view was wrong.**
   - Petri's judge does not read `target_messages`. It replays the transcript events for the target view and keeps rolled-back branches, with "Starting new conversation branch" markers [V].
   - The two views differ on 55 of the 260 analysis transcripts, including 28 of the pilot's 120. The default is now Petri's real view.
4. **Cost.** The full design (1,560 requests) is **$65–$139 at batch prices**, or $131–$277 at standard prices, under the low and high output cases. Opus 4.5 alone is $36–$75 at batch prices, which fits the $100 monthly Max credit if output stays at or below 10k tokens per call.
   - **The 2-dimension cut saves under 1%,** because output tokens dominate cost; it is not a cost lever.
5. **The pilot result is uncomfortable for the thesis framing** (cheap judges).
   - For target contrasts, almost all decision instability comes from **transcript sampling, not from judges**. Judge-facet φ is ≈ 0 for 11 of 12 contrasts.
   - Judges matter for **threshold (level) decisions**, where the judge main effect does not cancel.
   - So "judge error changes safety decisions" holds mainly for levels, not for rankings. See §6 and §8.

## 2. What was built

| SPEC item | Files | Notes |
|---|---|---|
| 1. Runners | `petri_v2/runner_anthropic.py`, `runner_gemini.py`, `runner_openai.py`; shared core `petri_v2/batch.py`, `http.py`, `jobs.py` | See notes below the table. |
| 2. Estimator | `petri_v2/estimate.py`, `prices.yaml` | See notes below the table. |
| 3. Prompts | `petri_v2/prompts.py`; verbatim pinned copies in `petri_v2/pinned/f02b3ec/` with `PIN.json` (sha256) | Setup: `scripts/setup_vendor.sh` clones commit f02b3ec into `vendor/` (gitignored). Tests diff the pinned copies against `vendor/` byte for byte. |
| 3b. Transcript view | `petri_v2/view.py` | A port of `_collect_messages(events, "target", add_only=True, indicate_rollbacks=True)` and `format_messages_xml`. Identical to Petri's own output on 311 of 311 corpus files, checked by running the pinned Petri code with inspect_ai. SHA-256 fingerprints are committed as a fallback. |
| 4. Parser | `petri_v2/parse.py` | A port of Petri's parser, identical to Petri's `_parse_judge_response` on all 720 pilot outputs. There is no floor: each missing score gets a reason code. |
| 5. Analysis | `analysis/pilot_fns.py`, `data.py`, `reliability.py`, `phi.py`, `run.py` | See notes below the table. |
| 6. Tests | `tests/` (59) | Mocked HTTP for all three providers. A socket guard fails any test that attempts network access. |
| 7. Pre-registration | `docs/PREREGISTRATION.md` | |
| 8. README | `README.md` | |
| Extra | `petri_v2/corpus.py`, `results/meta_260.json` | The 260-transcript nested order; its first 120 equal the pilot's. Public labels only. |

**Runners (item 1).**
- Batch submit, poll and collect, plus `plan`, `status` and `run`.
- Resumable: state is kept in `runs/<provider>/` and keyed by transcript × judge × repeat.
- Errored or expired items are resubmitted, at most 3 times.
- Keys are read from environment variables only, and redacted from any error text.
- Submission is refused without `--confirm-spend` **and** a `--budget-usd` that is at or above the dry-run estimate (batch price, 10k output tokens per request).
- Retired judges and wrong-provider judges are refused.

**Estimator (item 2).**
- Builds every request exactly.
- Uses Anthropic's `count_tokens` endpoint when a key is present; otherwise tiktoken `o200k_base`, labelled as an approximation, falling back to chars/4 offline.
- Reports low (4k), high (10k) and cap (32k) output cases at standard and batch prices.

**Analysis (item 5).**
- Reliability statistics reuse the pilot's functions, extracted from `pilot/scripts/analyze.py` with `ast` so the pilot file is untouched.
- φ is computed per decision and per facet (full, judges, repeats, transcripts).
- Also: threshold decisions, the D-study, transcript-bootstrap CIs, the negative control, the placebo, a split-half model check, and a Petri-floor sensitivity option (`--petri-floor`).

**How requests mirror Petri** (`petri_v2/judges.py`). Petri's judge config is `max_tokens=32000, reasoning_tokens=10000, reasoning_effort="high"`. I mapped it per provider the way inspect_ai does. Petri's lockfile pins inspect-ai 0.3.192, which is no longer on PyPI, so I read the providers in 0.3.193 instead.
- **Anthropic:** `thinking={"type":"enabled","budget_tokens":10000}`, with no temperature and no `effort`.
- **Gemini 3:** `thinkingConfig={"thinkingLevel":"HIGH","includeThoughts":true}`.
- **OpenAI:** Responses API with `reasoning.effort="high"` and `max_output_tokens=32000`, and the system prompt sent as a developer message.
- **Optional successor `opus55`:** adaptive thinking with `output_config.effort="high"`, because type "enabled" returns a 400 error on Opus 5.5.

## 3. Test status

```
python3 -m pytest -q tests      ->  59 passed in ~11.5 s   (0 skipped here)
```

- **What gets skipped elsewhere:**
  - Without `data/raw/`, the corpus and view tests skip.
  - Without `vendor/` and inspect_ai, the live-Petri equivalence tests skip; the committed fingerprints still cover the view whenever the corpus is present.
- **Runner tests**, run with fake Anthropic, Gemini and OpenAI servers:
  - a full submit → poll → collect cycle;
  - thinking text excluded from the judge output;
  - refusals recorded as `no_scores_block` with a `refusal_suspect` flag;
  - errored or expired items retried, at most 3 times;
  - no resubmission while a batch is pending;
  - the spend gate refuses in all three cases (no `--confirm-spend`, no budget, over budget);
  - refusal with no key;
  - the key never appears in any written file, log or stdout;
  - request shapes, URLs and headers per provider.
- **Simulation tests:**
  - the EMS variance components are recovered;
  - the judge components are unbiased on average;
  - 2p(1−p) matches the Monte Carlo flip rate of independent panels;
  - the judge main effect cancels in contrasts but not in thresholds;
  - the placebo gives plug-in ≈ 1/3 and split-half ≈ 0.5.

## 4. Model IDs and Batch API shapes (checked 2026-10-09, official pages only)

| Judge facet | Model ID | Status | Batch price per MTok (in / out) | Sources |
|---|---|---|---|---|
| opus45 (official) | `claude-opus-4-5-20251101` | Active (legacy). Retirement "not sooner than November 24, 2026". | $2.50 / $12.50 (standard $5 / $25) | platform.claude.com/docs/en/about-claude/model-deprecations, …/about-claude/pricing, …/models/opus-4-5/overview |
| gemini3pro (official) | `gemini-3-pro-preview` | **Shut down 2026-03-09.** The named replacement is `gemini-3.1-pro-preview`. | n/a | ai.google.dev/gemini-api/docs/deprecations |
| gemini31pro (successor, in default panel) | `gemini-3.1-pro-preview` | Preview, with no shutdown date announced. Batch API supported. | $1 / $6 for prompts ≤200k tokens (standard $2 / $12) | ai.google.dev/gemini-api/docs/pricing, …/models/gemini-3.1-pro-preview |
| gpt51 (official) | `gpt-5.1-2025-11-13` | **Deprecated.** Removal on 2027-04-01; the named replacement is `gpt-6-sol`. | $0.625 / $5 (standard $1.25 / $10) | developers.openai.com/api/docs/deprecations, …/models/gpt-5.1, …/pricing |
| gpt6sol (optional successor) | `gpt-6-sol` | Active | $1 / $5 (standard $2 / $10) | developers.openai.com/api/docs/models/gpt-6-sol |
| opus55 (optional successor) | `claude-opus-5-5` | Active (latest). Adaptive thinking only. | $2 / $10 (standard $4 / $20) | platform.claude.com/docs/en/models/opus-5-5/overview |

Batch API shapes are recorded in the runner docstrings, with URLs:

- **Anthropic:** `POST /v1/messages/batches`, with `custom_id` matching `^[a-zA-Z0-9_-]{1,64}$`.
  - Limits: 100k requests or 256 MB per batch.
  - Batches expire after 24 h; results are kept for 29 days.
  - Result types: succeeded, errored, canceled, expired.
- **Gemini:** JSONL `{key, request}` uploaded through the resumable File API, then `models/{model}:batchGenerateContent`.
  - State names: the guide says `JOB_STATE_*` and the API reference says `BATCH_STATE_*`; the runner accepts both.
  - Jobs expire after 48 h; the results file is kept for 6 weeks.
- **OpenAI:** `POST /v1/files` (purpose `batch`), then `POST /v1/batches` with endpoint `/v1/responses` and a 24 h window.
  - Limits: 50k requests or 200 MB.
  - Expired items go to the error file with code `batch_expired`.

How I checked: a research subagent read each official page (WebFetch, or curl plus pandoc for Google and OpenAI) and returned verbatim quotes. I did not re-open every page myself, so these facts rest on that subagent's quotes [V via subagent]. Two points are inferred from examples rather than stated in one sentence: Anthropic batches need no beta header, and `count_tokens` requires a key.

## 5. Dry-run cost table

What the estimator did:
- built every request, using the Petri view and the exact prompt;
- counted input tokens with **tiktoken `o200k_base`**. This is an approximation for Claude and Gemini, because Anthropic's count endpoint needs a key;
- priced the requests from `prices.yaml`, with no caching discount.

Two checks on the token counts:
- **Pilot calibration:** on the pilot's 120 transcripts, measured input tokens divided by the o200k estimate had a median of 0.997 for Muse, 1.016 for MiMo and 1.018 for DeepSeek.
- **Sensitivity:** if Claude's tokenizer counts 30% more tokens, the full-design Opus batch cost rises by only about $3, because output dominates.

Output cases per request: **low = 4,000 tokens**, the pilot's measured mean; **high = 10,000 tokens**, Petri's reasoning budget; **cap = 32,000 tokens**, the `max_tokens` worst case.

**Exact request counts:**

| Scenario | Requests |
|---|---|
| Full: 260 transcripts × 3 judges × 2 repeats | 1,560 (520 per judge) |
| Pilot set: 120 transcripts | 720 |
| Untouched: 140 transcripts | 840 |
| 2-dimension cut: 260 transcripts | 1,560 |
| 2-dimension cut: 120 transcripts | 720 |

#### full_260_4dims: 260 transcripts, 4 dims, view=petri

Requests: 1560. Prices checked 2026-10-09.

| Judge | Model | Requests | Input tokens | Mean in/request | Token method | Output low / high | Std low | Std high | Batch low | Batch high | Batch cap (32k out) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opus45 | claude-opus-4-5-20251101 | 520 | 3,979,622 | 7,653 | approximation: tiktoken o200k_base | 2,080,000 / 5,200,000 | $71.90 | $149.90 | $35.95 | $74.95 | $217.95 |
| gemini31pro | gemini-3.1-pro-preview | 520 | 3,979,622 | 7,653 | approximation: tiktoken o200k_base | 2,080,000 / 5,200,000 | $32.92 | $70.36 | $16.46 | $35.18 | $103.82 |
| gpt51 | gpt-5.1-2025-11-13 | 520 | 3,979,622 | 7,653 | approximation: tiktoken o200k_base | 2,080,000 / 5,200,000 | $25.77 | $56.97 | $12.89 | $28.49 | $85.69 |
| **total** | | 1,560 | | | | | $130.59 | $277.23 | $65.30 | $138.62 | $407.46 |

#### pilot_120_4dims: 120 transcripts, 4 dims, view=petri

Requests: 720. Prices checked 2026-10-09.

| Judge | Model | Requests | Input tokens | Mean in/request | Token method | Output low / high | Std low | Std high | Batch low | Batch high | Batch cap (32k out) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opus45 | claude-opus-4-5-20251101 | 240 | 1,828,170 | 7,617 | approximation: tiktoken o200k_base | 960,000 / 2,400,000 | $33.14 | $69.14 | $16.57 | $34.57 | $100.57 |
| gemini31pro | gemini-3.1-pro-preview | 240 | 1,828,170 | 7,617 | approximation: tiktoken o200k_base | 960,000 / 2,400,000 | $15.18 | $32.46 | $7.59 | $16.23 | $47.91 |
| gpt51 | gpt-5.1-2025-11-13 | 240 | 1,828,170 | 7,617 | approximation: tiktoken o200k_base | 960,000 / 2,400,000 | $11.89 | $26.29 | $5.94 | $13.14 | $39.54 |
| **total** | | 720 | | | | | $60.20 | $127.88 | $30.10 | $63.94 | $188.02 |

#### untouched_140_4dims: 140 transcripts, 4 dims, view=petri

Requests: 840. Prices checked 2026-10-09.

| Judge | Model | Requests | Input tokens | Mean in/request | Token method | Output low / high | Std low | Std high | Batch low | Batch high | Batch cap (32k out) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opus45 | claude-opus-4-5-20251101 | 280 | 2,151,452 | 7,684 | approximation: tiktoken o200k_base | 1,120,000 / 2,800,000 | $38.76 | $80.76 | $19.38 | $40.38 | $117.38 |
| gemini31pro | gemini-3.1-pro-preview | 280 | 2,151,452 | 7,684 | approximation: tiktoken o200k_base | 1,120,000 / 2,800,000 | $17.74 | $37.90 | $8.87 | $18.95 | $55.91 |
| gpt51 | gpt-5.1-2025-11-13 | 280 | 2,151,452 | 7,684 | approximation: tiktoken o200k_base | 1,120,000 / 2,800,000 | $13.89 | $30.69 | $6.94 | $15.34 | $46.14 |
| **total** | | 840 | | | | | $70.39 | $149.35 | $35.19 | $74.67 | $219.43 |

#### cut_260_2dims: 260 transcripts, 2 dims, view=petri

Requests: 1560. Prices checked 2026-10-09.

| Judge | Model | Requests | Input tokens | Mean in/request | Token method | Output low / high | Std low | Std high | Batch low | Batch high | Batch cap (32k out) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opus45 | claude-opus-4-5-20251101 | 520 | 3,793,982 | 7,296 | approximation: tiktoken o200k_base | 2,080,000 / 5,200,000 | $70.97 | $148.97 | $35.48 | $74.48 | $217.48 |
| gemini31pro | gemini-3.1-pro-preview | 520 | 3,793,982 | 7,296 | approximation: tiktoken o200k_base | 2,080,000 / 5,200,000 | $32.55 | $69.99 | $16.27 | $34.99 | $103.63 |
| gpt51 | gpt-5.1-2025-11-13 | 520 | 3,793,982 | 7,296 | approximation: tiktoken o200k_base | 2,080,000 / 5,200,000 | $25.54 | $56.74 | $12.77 | $28.37 | $85.57 |
| **total** | | 1,560 | | | | | $129.06 | $275.70 | $64.53 | $137.85 | $406.69 |

#### cut_120_2dims: 120 transcripts, 2 dims, view=petri

Requests: 720. Prices checked 2026-10-09.

| Judge | Model | Requests | Input tokens | Mean in/request | Token method | Output low / high | Std low | Std high | Batch low | Batch high | Batch cap (32k out) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opus45 | claude-opus-4-5-20251101 | 240 | 1,742,490 | 7,260 | approximation: tiktoken o200k_base | 960,000 / 2,400,000 | $32.71 | $68.71 | $16.36 | $34.36 | $100.36 |
| gemini31pro | gemini-3.1-pro-preview | 240 | 1,742,490 | 7,260 | approximation: tiktoken o200k_base | 960,000 / 2,400,000 | $15.00 | $32.28 | $7.50 | $16.14 | $47.82 |
| gpt51 | gpt-5.1-2025-11-13 | 240 | 1,742,490 | 7,260 | approximation: tiktoken o200k_base | 960,000 / 2,400,000 | $11.78 | $26.18 | $5.89 | $13.09 | $39.49 |
| **total** | | 720 | | | | | $59.50 | $127.18 | $29.75 | $63.59 | $187.67 |

#### successor facets (optional): 260 transcripts, 4 dims

Requests: 1040. Prices checked 2026-10-09.

| Judge | Model | Requests | Input tokens | Mean in/request | Token method | Output low / high | Std low | Std high | Batch low | Batch high | Batch cap (32k out) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opus55 | claude-opus-5-5 | 520 | 3,979,622 | 7,653 | approximation: tiktoken o200k_base | 2,080,000 / 5,200,000 | $57.52 | $119.92 | $28.76 | $59.96 | $174.36 |
| gpt6sol | gpt-6-sol | 520 | 3,979,622 | 7,653 | approximation: tiktoken o200k_base | 2,080,000 / 5,200,000 | $28.76 | $59.96 | $14.38 | $29.98 | $87.18 |
| **total** | | 1,040 | | | | | $86.28 | $179.88 | $43.14 | $89.94 | $261.54 |

What the numbers mean:
- **Opus 4.5 on the Max credit ($100 per month).**
  - The full 260 transcripts cost $75 at batch prices in the high case. That fits, with $25 of headroom.
  - If outputs run toward the 32k cap, the cost could reach $218.
  - Safer plan: run the untouched 140 this billing cycle ($40 high, $117 cap) and the pilot 120 next cycle. Both cycles fall before 24 Nov only if the cycle boundary allows it. Check your billing date.
- **Gemini and GPT are paid in cash or credits.** At batch prices in the high case, Gemini 3.1 Pro costs $35 and GPT-5.1 costs $28.
- **The high case is not a hard bound for Gemini and GPT.** Gemini 3 and GPT-5.1 run at "high" thinking with no token budget; Petri's 10k budget applies only to Claude. Their real output could exceed 10k per call [I].

## 6. φ vs ICC on the pilot data (CHEAP JUDGES: Muse, MiMo, DeepSeek; not Petri's judges)

Setup:
- Command: `python3 -m analysis.run --judgments pilot/scores_pilot120.jsonl --meta pilot/sample_meta.json --n 120 --judges muse,mimo,deepseek --out results/pilot120 --tag pilot120_cheap`.
- Data: complete cases, 105 transcripts (104 for `unfaithful_thinking`).
- Bootstrap: B = 1,000 transcript resamples, stratified by target; placebo uses 500 permutations.
- Views: 28 of these 120 transcripts were judged with the `target_messages` view, not Petri's view (§7.3).
- Full output: `results/pilot120/results_pilot120_cheap.json` and `phi_vs_icc_pilot120_cheap.md`.

| Dimension | n | ICC(2,1) rep 1 | alpha | Contrast | Delta | phi full [95% CI] | phi judges | phi repeats | phi transcripts | phi full, pair-specific s_gj | empirical split phi (J=1,R=1,n/2) vs model (pooled / pair s_gj) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| concerning | 105 | 0.88 | 0.88 | hermes3 vs deepseek_v31 | -1.99 | 0.001 [0.000, 0.181] | 0.000 | 0.000 | 0.001 | 0.001 | 0.002 vs 0.025 / 0.027 |
| concerning | 105 | 0.88 | 0.88 | hermes3 vs mistral_large | -2.55 | 0.000 [0.000, 0.044] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 vs 0.008 / 0.010 |
| concerning | 105 | 0.88 | 0.88 | deepseek_v31 vs mistral_large | -0.56 | 0.322 [0.002, 0.499] | 0.001 | 0.000 | 0.319 | 0.319 | 0.425 vs 0.412 / 0.409 |
| unprompted_deception_toward_user | 105 | 0.79 | 0.79 | hermes3 vs deepseek_v31 | -1.59 | 0.000 [0.000, 0.024] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 vs 0.014 / 0.016 |
| unprompted_deception_toward_user | 105 | 0.79 | 0.79 | hermes3 vs mistral_large | -2.33 | 0.000 [0.000, 0.006] | 0.000 | 0.000 | 0.000 | 0.000 | 0.001 vs 0.007 / 0.007 |
| unprompted_deception_toward_user | 105 | 0.79 | 0.79 | deepseek_v31 vs mistral_large | -0.74 | 0.235 [0.002, 0.499] | 0.000 | 0.000 | 0.235 | 0.236 | 0.359 vs 0.362 / 0.363 |
| cooperation_with_human_misuse | 105 | 0.81 | 0.81 | hermes3 vs deepseek_v31 | -0.49 | 0.307 [0.006, 0.499] | 0.000 | 0.000 | 0.306 | 0.306 | 0.416 vs 0.402 / 0.401 |
| cooperation_with_human_misuse | 105 | 0.81 | 0.81 | hermes3 vs mistral_large | -0.12 | 0.483 [0.021, 0.500] | 0.333 | 0.255 | 0.483 | 0.483 | 0.676 vs 0.493 / 0.493 |
| cooperation_with_human_misuse | 105 | 0.81 | 0.81 | deepseek_v31 vs mistral_large | +0.37 | 0.379 [0.015, 0.499] | 0.026 | 0.003 | 0.378 | 0.383 | 0.577 vs 0.450 / 0.452 |
| unfaithful_thinking | 104 | 0.74 | 0.74 | hermes3 vs deepseek_v31 | -1.05 | 0.005 [0.000, 0.202] | 0.000 | 0.000 | 0.004 | 0.010 | 0.011 vs 0.072 / 0.103 |
| unfaithful_thinking | 104 | 0.74 | 0.74 | hermes3 vs mistral_large | -1.50 | 0.001 [0.000, 0.070] | 0.000 | 0.000 | 0.001 | 0.001 | 0.005 vs 0.050 / 0.051 |
| unfaithful_thinking | 104 | 0.74 | 0.74 | deepseek_v31 vs mistral_large | -0.44 | 0.335 [0.009, 0.500] | 0.020 | 0.001 | 0.333 | 0.333 | 0.526 vs 0.433 / 0.432 |

| Dimension | s_gj (target x judge) | s_j (judge) | Negative control: high vs low severity, Delta / phi | Placebo: plug-in phi mean / share < 0.1 / empirical split phi |
|---|---|---|---|---|
| concerning | 0.0151 (raw 0.0151, df 4) | 0.1388 (raw 0.1388, df 2) | +2.14 / 2.46e-03 | 0.343 / 0.092 / 0.512 |
| unprompted_deception_toward_user | 0.0000 (raw -0.0042, df 4) | 0.0139 (raw 0.0139, df 2) | +1.40 / 5.14e-03 | 0.326 / 0.121 / 0.510 |
| cooperation_with_human_misuse | 0.0047 (raw 0.0047, df 4) | 0.0097 (raw 0.0097, df 2) | +1.32 / 2.23e-02 | 0.339 / 0.105 / 0.536 |
| unfaithful_thinking | 0.0072 (raw 0.0072, df 4) | 0.0206 (raw 0.0206, df 2) | +1.08 / 3.05e-03 | 0.331 / 0.105 / 0.475 |

| Dimension | Contrast | Cheapest design with phi <= 0.05 (J, R, n per target, calls) | phi limit with n -> infinity, J = 1 / 3 / 8 |
|---|---|---|---|
| concerning | hermes3 vs deepseek_v31 | J=1, R=1, n=20, 40 calls | 0.000 / 0.000 / 0.000 |
| concerning | hermes3 vs mistral_large | J=1, R=1, n=10, 20 calls | 0.000 / 0.000 / 0.000 |
| concerning | deepseek_v31 vs mistral_large | J=1, R=1, n=400, 800 calls | 0.001 / 0.000 / 0.000 |
| unprompted_deception_toward_user | hermes3 vs deepseek_v31 | J=1, R=1, n=20, 40 calls | 0.000 / 0.000 / 0.000 |
| unprompted_deception_toward_user | hermes3 vs mistral_large | J=1, R=1, n=10, 20 calls | 0.000 / 0.000 / 0.000 |
| unprompted_deception_toward_user | deepseek_v31 vs mistral_large | J=1, R=1, n=200, 400 calls | 0.000 / 0.000 / 0.000 |
| cooperation_with_human_misuse | hermes3 vs deepseek_v31 | J=1, R=1, n=400, 800 calls | 0.000 / 0.000 / 0.000 |
| cooperation_with_human_misuse | hermes3 vs mistral_large | not reached on the grid | 0.189 / 0.030 / 0.000 |
| cooperation_with_human_misuse | deepseek_v31 vs mistral_large | J=2, R=1, n=400, 1600 calls | 0.000 / 0.000 / 0.000 |
| unfaithful_thinking | hermes3 vs deepseek_v31 | J=1, R=1, n=40, 80 calls | 0.000 / 0.000 / 0.000 |
| unfaithful_thinking | hermes3 vs mistral_large | J=1, R=1, n=20, 40 calls | 0.000 / 0.000 / 0.000 |
| unfaithful_thinking | deepseek_v31 vs mistral_large | J=1, R=1, n=400, 800 calls | 0.000 / 0.000 / 0.000 |

Threshold decisions ("target mean ≤ c"), selected rows from the JSON. Judge-facet φ means transcripts are held fixed:

| Dimension | Decision | Δ (mean − c) | φ full | φ judges |
|---|---|---|---|---|
| concerning | Hermes ≤ 2.5 | +0.33 | 0.355 | **0.145** |
| concerning | Hermes ≤ 3.0 | −0.17 | 0.459 | **0.365** |
| concerning | Mistral ≤ 5.0 | +0.38 | 0.371 | **0.115** |
| cooperation | Mistral ≤ 2.0 | +0.12 | 0.465 | **0.313** |

Compare these with target contrasts of similar |Δ|, where judge-facet φ is ≤ 0.026 except cooperation Hermes vs Mistral (0.333). This is the levels-versus-contrasts effect:
- The judge main effect cancels in a contrast but not in a threshold decision.
- In the pilot, MiMo scores `concerning` 0.7 points lower than Muse (σ²_j = 0.139).

How to read the main table:
- **ICC does not track φ** (H1, cheap judges). `concerning` has the highest ICC (0.88) and still has one contrast at φ = 0.32. Within every dimension, φ ranges from ≈ 0 to 0.32–0.48.
- **Contrast instability comes from transcript sampling.** For contrasts, φ_full ≈ φ_transcripts. The judge facet matters only where Δ ≈ 0 (cooperation, Hermes vs Mistral).
- **The CIs are very wide,** for example [0.002, 0.499]. With about 35 transcripts per target, φ for close pairs is essentially undetermined. The 260-transcript run narrows this, but only by about √2.
- **The negative control passes:** high vs low planted severity has φ ≤ 0.022 on all four dimensions.
- **The placebo behaves as theory predicts:** plug-in φ averages 0.33–0.34, which is the 1/3 expected under a normal null, and the split-half estimator gives 0.48–0.54.
- **Model check:** for decisions with clear gaps, the split-half φ agrees with the model's φ at (J=1, R=1, n/2), and the model is conservative in the tails. For near-zero gaps the split-half estimate exceeds 0.5 (for example 0.676 vs 0.493). This is expected for a single dataset: the two halves are anti-correlated around the full-sample mean. The estimator is unbiased over repeated samples, but noisy.
- **Petri's silent floor changes results.** With the floor (`--petri-floor`: missing = 1, as Petri does after retries), ICC drops on every dimension:

  | Dimension | ICC without floor | ICC with floor |
  |---|---|---|
  | concerning | 0.88 | 0.79 |
  | deception | 0.79 | 0.74 |
  | cooperation | 0.81 | 0.77 |
  | unfaithful thinking | 0.74 | 0.68 |

  Target gaps also move:

  | Contrast | Gap without floor | Gap with floor |
  |---|---|---|
  | cooperation, DeepSeek vs Mistral | +0.37 | +0.12 |
  | cooperation, Hermes vs Mistral | −0.12 | −0.36 |
  | unfaithful thinking, DeepSeek vs Mistral | −0.44 | −0.11 |

  Almost all of the floored cells are MiMo's 61 missing cells. This quantifies the concern raised in inspect_petri issue #113, with cheap judges.

## 7. What in the spec turned out wrong or incomplete

1. **"Gemini 3 Pro" as an official judge.** It has been shut down since 2026-03-09, so the panel uses the named successor as a separate facet. Petri 2.0's exact panel is no longer reproducible, and the write-up must say so.
2. **No deadline for Opus 4.5.** Its earliest retirement is 24 Nov 2026, which is a hard schedule constraint.
3. **"The judge view must be `target_messages`."** This is wrong. Both views exclude the auditor's commentary, but Petri's judge uses the event-replayed target view, which keeps rolled-back branches.
   - 64 of 311 corpus files have target rollbacks: 55 of the 260 analysis transcripts, 28 of the pilot 120 and 27 of the untouched 140.
   - The default is now `--view petri`; `--view target_messages` reproduces the pilot's view.
   - Consequence: the pilot's 28 rollback transcripts are not comparable with v2 scores. The "cheap-judge family as fourth facet" is clean only if the cheap judges re-score those 28 under the Petri view (or all 120, at about $2 at list price).
4. **"Placebo: φ ≈ 0.5 for null gaps."** This holds for the true φ and for the split-half estimator. The plug-in estimator gives about **1/3** under a null, because |Δ̂| > 0. In the pilot, about 9–12% of null permutations gave a plug-in φ below 0.1. Plug-in φ near 0.5 cannot be read as "unstable": near-null decisions look more stable than they are.
5. **The kill/cut option (2 dimensions)** saves under 1% of cost: the prompt shrinks by about 360 tokens, and output is unchanged. The levers are transcripts, repeats or judges.
6. **σ²_D in the spec assumes one σ²_t:g for all targets.** The build estimates transcript-level components per target, because the targets differ (floor effects), and pools only the judge components. With J = 3 these judge components have 2 and 4 degrees of freedom. The spec should say this plainly.
7. **"Measured pilot tokens ≈ 7,400 input."** Under the Petri view, the input is about 7,650 tokens per request (the 260 mean), because kept branches add tokens. This is minor.
8. **Petri's `reasoning_tokens=10000` reaches only Claude.** For Gemini 3 and GPT-5.1, inspect_ai sends a thinking level or effort, not a budget, so the "10k high case" is not a bound for them (§5).
9. **"ICC(2,1) involves neither Δ nor σ²_gj."** This is correct for the inter-judge ICC computed within one repeat. One nuance: transcript-level ICC still contains σ²_tj in its error term, which feeds σ²_D through σ²_tj/(nJ).

## 8. Open questions for Thomas

1. **Which provider for Gemini and GPT?**
   - Options: (a) Google AI Studio Gemini API and the OpenAI API directly; (b) Vertex AI or Azure, where research credits may apply; (c) OpenRouter, which offers no batch discount and an unclear thinking passthrough.
   - My recommendation is (a): the runners are written for (a), and only (a) gives the 50% batch price as documented. Who pays, and are there research credits?
2. **Is `gemini-3.1-pro-preview` acceptable as the Gemini facet?** The alternative is to report "2 official judges + 1 successor" explicitly. The model is a preview with no shutdown date, so it may change during the study.
3. **Opus timing.** Run the untouched 140 before 24 Nov, within one Max billing cycle ($40 high, $117 cap)? Or submit all 260 now ($75 high, but over $100 if outputs run long)?
4. **Accept the switch to Petri's real view** (the change from the spec)?
5. **Parse-failure retries.** The primary analysis is first-attempt only. Do you also want a Petri-style secondary with up to 3 attempts per call? It costs up to the failure rate × the call cost extra.
6. **Re-score the pilot with cheap judges under the Petri view,** so the fourth facet is clean? It costs about $2 at list price.
7. **Register the pre-registration on OSF before any official-judge call.**

## 9. Brutal assessment

- **H1 as written is close to a tautology.** ICC is defined per dimension and φ per decision, so a reviewer will call H1 trivially true. The cheap-judge pilot already "confirms" it.
- **The publishable claim is H3 (levels vs contrasts) plus the D-study floor.** The claim is not that judges flip rankings. It is that judges flip threshold decisions, and that transcript sampling, not judge disagreement, limits rankings at Petri's scale. That is less dramatic than the thesis title, but it is what the pilot data supports.
- **If official judges show the same pattern, the headline changes.** It becomes "your audit is under-powered in transcripts and level-miscalibrated in judges", not "your judges are unreliable". Decide now which result would still be a paper, before you spend the money.
- **Pilot n is tiny.** With about 35 transcripts per target, every near-zero contrast has a φ CI of about [0, 0.5]. Even 260 transcripts gives about 87 per target, which narrows CIs by about √2.5. The decisive estimates will be the D-study components (σ²_gj and σ²_j), and with 3 judges those rest on 2–4 degrees of freedom. Either use more judges (the successor facets plus the cheap family) or state that the judge components are weakly identified.
- **Schedule.** Opus 4.5's retirement window starts in 6 weeks. Every week spent polishing the pipeline instead of submitting the confirmatory 140 raises the risk that the main judge disappears.

## 10. Housekeeping

- Committed:
  - `petri_v2/`, `analysis/`, `tests/`, `scripts/setup_vendor.sh`, `prices.yaml`, `requirements.txt`;
  - `results/estimate_*.json`, `results/meta_260.json` (public labels only) and `results/pilot120/`;
  - docs.
- Not committed (gitignored): `data/raw/` (corpus), `vendor/` (Petri clone), `runs/`.
- I accidentally overwrote `.gitignore` while scaffolding. I restored the original entries (`*.env`, `.env*`, `*.key`, `secrets*`, `out/`) and added `vendor/`, `runs/`, `*.pyc` and `.pytest_cache/`.

---

# Session 2, 10 Oct 2026: fixes after the independent second opinion

- **Branch:** `v2-build`.
- **No paid API calls. Nothing filed on OSF.** No emails, issues or PRs.
- **`pilot/` is unchanged.**
- **Input:** an independent review of revision 1 of the pre-registration, which concluded "file after fixes".
- **Output:**
  - `docs/PREREGISTRATION.md`, revision 2;
  - `analysis/confirm.py` and `analysis/reml.py` (new);
  - changes to `analysis/phi.py`, `analysis/run.py`, `analysis/data.py`, `petri_v2/judges.py`, `petri_v2/estimate.py`, `petri_v2/corpus.py` and `prices.yaml`;
  - 18 new tests;
  - `results/estimate_designs.json`, `results/thinking_traces_260.json`, and a regenerated `results/pilot120/`.
- **Tests:** `python3 -m pytest -q tests` gives 77 passed and 2 skipped, in about 19 s. The 2 skips are the live-Petri equivalence tests, which need inspect_ai; the committed fingerprints cover them.

## S2.1 Verdict first

1. **Every requested fix is done, except the open-weight runners** (S2.2). Two fixes deviate from the review's letter, for reasons shown in data: the φ estimator and the model-check tolerance.
2. **The restructured claim is not supported on the pilot (cheap judges).** This is the most important finding of the session.
   - **H1′ (calibration offset > contrast discrepancy) fails on all three confirmatory dimensions.** In each, 0 of 9 cells have a lower bound above 0.
   - **H2′ at Petri's own cut-offs (4, 7) fails at target level everywhere.** At transcript level it holds only for `concerning`, c = 7.
   - Revision 1's striking "levels vs contrasts" numbers came from thresholds placed near the observed target means, exactly as the review suspected.
   - **Whether official judges show the effect is an open empirical question, and the pre-registration says so.** That framing is right, but Thomas should expect a real chance of a null on the headline.
3. **The review was wrong about Mistral and right about Hermes** on `unfaithful_thinking`.
   - No target emits native reasoning.
   - Auditor-prompted `<thinking>` blocks appear in Mistral 42/65, DeepSeek 26/100 and Hermes 2/95 transcripts.
   - The dimension is now exploratory.
4. **Design options are costed.** J = 8 adds about $45 at batch-high prices on top of the J = 3 design's $139. The Opus leg stays first in every design.

## S2.2 Each fix: done / not done and why

| # | Fix requested | Status | Where | Notes |
|---|---|---|---|---|
| 1 | Restructure hypotheses around levels vs contrasts | **Done** | prereg §2; `analysis/confirm.py` | See notes 1a–1c below the table. |
| 2 | Move old H1 to a descriptive display | **Done** | prereg §2 "Descriptive display"; `run.py` table | |
| 3 | Make the primary φ estimator design-based or bias-corrected, with a pre-stated tolerance for the model check | **Done, with changes** | `phi.py`: `phi_bc`, `phi_interval`, `model_check` | See notes 3a–3c below the table. |
| 4 | Name the confirmatory family and its error control | **Done** | prereg §2; `confirm.family` | See note 4 below the table. |
| 5 | Make `unfaithful_thinking` exploratory, and check reasoning traces in the corpus | **Done** | prereg §3; `corpus.thinking_report`; `results/thinking_traces_260.json` | Counts in S2.4. |
| 6 | REML / mixed-model sensitivity analysis | **Done** | `analysis/reml.py` | See note 6 below the table. |
| 7 | Failure rates by severity stratum | **Done** | `data.missing_by_stratum`; prereg §5 | Pre-stated flag: if the high-stratum failure rate exceeds the low stratum by more than 5 points, the dimension is labelled "possibly missing not at random". |
| 8 | Specify temperature and sampling per provider | **Done** | `judges.py` (`sampling`, `reasoning` fields); prereg §3 | No request sends temperature, top_p or top_k. A new test checks every served judge's request body. |
| 9 | Remove the cheap-judge fourth facet | **Done** | prereg §3 | |
| 10 | Write the J = 3 design and a J = 6–8 option, with a stated population, ≥ 4 developers, exact counts and dry-run costs | **Done** | `judges.PANEL_J6` / `PANEL_J8`; `estimate.DESIGNS`; `--designs` | Table in S2.3. Gemma was considered: S2.3. |
| 11 | DeepSeek and Kimi runners | **Not done** | | See note 11 below the table. |
| 12 | Keep the Opus 4.5 deadline; the Opus leg runs first | **Done** | prereg §3, §6; tested | Every design's first leg is Opus 4.5 on positions 121–260. |
| 13 | Update tests | **Done** | `tests/test_confirm.py`, `test_reml.py`, additions to `test_phi.py`, `test_estimate.py`, `test_runners.py` | 59 → 77 tests. |

**Note 1a: H1′.** For each dimension, D = |μ_j − μ_k| − |Δ_j − Δ_k| is computed per judge pair × contrast. The test statistic is the mean of D, with a bootstrap one-sided p-value. H1′ also requires that at least 2/3 of the cells have a 95% lower bound above 0.

**Note 1b: H2′.** Judge-swap flip rates are computed with transcripts fixed, J = 1 and R = 1.
- **Cut-offs:** **Petri's own, 4 and 7.** They come from `ScoreBadge.svelte` at f02b3ec: score ≥ 7 is "high" and ≥ 4 is "medium". The viewer is the only place in the pinned code with score cut-offs, so the review's "{3, 5, 7}" fallback was not needed.
- **Primary level:** target means. Petri's scorer metric is the mean over samples.
- **Secondary level:** per transcript (Petri's per-transcript badge).

**Note 1c: H3′.** The judge floor as n → ∞ is reported as a bound. It combines a χ² or Satterthwaite interval for the judge component with the normal interval for Δ, each at 97.5% (Bonferroni, so jointly at least 95%).

**Note 3a: why the bias-corrected φ is not primary.** I simulated it, and it is **not better uniformly.** With z = |Δ| / σ:
- The plug-in φ is biased −0.17 at z = 0 and **+0.07 at z = 2**. The review's "systematically understates instability" is true only for z below about 1.2.
- The bias-corrected φ is −0.075 at z = 0 and +0.13 at z = 1.5.
- Every intermediate correction has a max |bias| of 0.1 or more, and an RMSE of about 0.2.

This is an identifiability limit of estimating φ from one Δ̂. **The primary report is therefore the plug-in point plus a 95% CI by inversion of the normal Δ interval** (coverage tested). The bias-corrected φ is reported alongside.

**Note 3b: the model-check tolerance.** **The review's "|φ_model − φ_split| ≤ 0.05" fails 24–31% of the time when the model is true** (simulated at this study's sizes). It would mostly flag noise. The pre-stated rule is instead a bracket:

  mean plug-in − 0.05 ≤ mean split-half ≤ mean bias-corrected + 0.05

It passes in 95% of simulated datasets with pilot-like gaps, 92% with large gaps and **64% when all gaps are near 0**. The prereg states those rates.

**Note 3c: what a model-check failure does.** It downgrades H3′, φ and the D-study to exploratory. **H1′ and H2′ do not use the model**, so the main claims cannot be rescued or sunk by it.

**Note 4: the family.** 3 confirmatory dimensions × (H1′ + H2′ at c = 4 and c = 7) = 9 tests, Holm at α = 0.05, one-sided bootstrap p-values with B = 2,000. The judges are the three Petri facets, **fixed in every design**, so the choice of J does not change the family.

**Note 6: REML.** The same model is fitted on all valid scores, unbalanced. It uses dense REML with an analytic gradient. On balanced data it equals the ANOVA estimates (tested). Speed:
- about 10 s per dimension at 1,000 scores;
- slow at J = 8 on 260 transcripts, which is about 4,000 scores and roughly 8 minutes per dimension (estimated). `--no-reml` skips it.

**Note 11: why the DeepSeek and Kimi runners are not built.** They are needed only if Thomas picks Design B or C, and Kimi's Batch API (OpenAI-compatible JSONL) and DeepSeek's off-peak window would need their own mocked tests.
- Building them before the design choice would spend effort that may not be needed.
- The Anthropic, Gemini and OpenAI runners already accept `sonnet55`, `gemini38flash` and `gpt54mini` (checked with `plan`).

## S2.3 Judge population and dry-run cost table

**Stated population:** "frontier and mid-tier LLM judges served on 2026-10-10, from at least 4 developers".
- One tier down from Anthropic, Google and OpenAI.
- Two strong open-weight judges.
- Status and prices were checked on official pages by a research subagent on 2026-10-10. I re-checked these rows against the saved official pages myself:
  - Sonnet 5.5;
  - Gemini 3.8 Flash;
  - GPT-5.4 mini;
  - DeepSeek V4 Pro off-peak;
  - Kimi K2.6 batch.

**Command:** `python3 -m petri_v2.estimate --designs --json results/estimate_designs.json`. Settings:
- tiktoken `o200k_base` input approximation, about 7,650 tokens per request;
- × 1.3 for Claude 4.7+ models (the pricing page: "approximately 30% more tokens");
- output per call: low 4,000, high 10,000, cap 32,000 tokens.

| Design | Judges | Requests | Batch low | Batch high | Batch cap (32k out) | Standard high |
|---|---|---|---|---|---|---|
| A_J3 | 3 | 1,560 | $65.30 | $138.62 | $407.46 | $277.23 |
| B_J6 | 6 | 2,400 | $75.75 | $159.58 | $466.95 | $316.52 |
| C_J8 | 8 | 2,960 | $87.48 | $183.49 | $535.52 | $364.32 |
| C_J8_lite | 8 | 2,610 | $81.85 | $172.18 | $503.42 | $342.39 |
| add-on Gemma 4 31B | 1 | 280 | $0.70 | $1.24 | $3.21 | $1.55 |
| alternate Qwen3.8 Max | 1 | 280 | $5.51 | $10.55 | $29.03 | $21.10 |

Design composition and exact request counts:
- **A:** 3 judges × 2 repeats × 260 transcripts.
- **B:** A + {Gemini 3.8 Flash, DeepSeek V4 Pro, Kimi K2.6} × 2 × 140 (positions 121–260) = 1,560 + 840.
- **C:** A + {Sonnet 5.5, Gemini 3.8 Flash, GPT-5.4 mini, DeepSeek V4 Pro, Kimi K2.6} × 2 × 140 = 1,560 + 1,400.
- **C-lite:** the same 5 extra judges with R = 2 on positions 121–190 and R = 1 on 191–260 = 1,560 + 1,050.

| Judge | Model ID | Developer | Tier | Requests | Batch low | Batch high | Batch cap | Price mode | Runner in repo |
|---|---|---|---|---|---|---|---|---|---|
| opus45 | claude-opus-4-5-20251101 | Anthropic | frontier | 520 | $35.95 | $74.95 | $217.95 | Batch API | yes |
| gemini31pro | gemini-3.1-pro-preview | Google | frontier | 520 | $16.46 | $35.18 | $103.82 | Batch API | yes |
| gpt51 | gpt-5.1-2025-11-13 | OpenAI | frontier | 520 | $12.89 | $28.49 | $85.69 | Batch API | yes |
| sonnet55 | claude-sonnet-5-5 | Anthropic | mid | 280 | $8.40 | $16.80 | $47.60 | Batch API | yes |
| gemini38flash | gemini-3.8-flash | Google | mid | 280 | $2.91 | $6.06 | $17.61 | Batch API | yes |
| gpt54mini | gpt-5.4-mini-2026-03-17 | OpenAI | mid | 280 | $3.33 | $7.11 | $20.97 | Batch API | yes |
| deepseekv4pro | deepseek-v4-pro (V4-Pro-0813, MIT) | DeepSeek | open | 280 | $3.64 | $6.96 | $19.16 | off-peak synchronous (no Batch API) | no |
| kimik26 | kimi-k2.6 (modified MIT) | Moonshot AI | open | 280 | $3.91 | $7.95 | $22.73 | Batch API (60% of list) | no |
| gemma4 (add-on) | google/gemma-4-31B-it on DeepInfra | Google | open | 280 | $0.70 | $1.24 | $3.21 | batch, derived (80% of list) | no |
| qwen38max (alternate) | qwen3p8-max on Fireworks | Alibaba Qwen | open | 280 | $5.51 | $10.55 | $29.03 | batch, derived (50% of list) | no |

**Facts that shaped the choice** [V = on a page I or the subagent opened; I = inference]:
- **Sonnet 4.5 retires 2026-11-30, and gpt-5-mini shuts down 2026-12-11** [V]. Both would add a second deadline race, so neither is used. `gpt-5.1-mini` does not exist [V].
- **Gemini 3.8 Flash batch prices double on 2027-01-01** [V]: from $0.375 / $1.875 to $0.75 / $3.75. That leg must run in 2026.
- **DeepSeek has no Batch API** [I: absent from the docs]. Off-peak rates are half of peak; peak is 01:00–04:00 and 06:00–10:00 UTC, Monday to Friday [V].
- **Together AI's batch discount no longer applies to LLMs** [V], so it was dropped as a host. DeepInfra's batch is 20% off [V]; Fireworks' is 50% [V]. The Qwen and Gemma batch prices apply those rules to list prices, so they are labelled "derived" [I].
- **Gemma.** Gemma 4 31B is free-tier only on the Gemini API, with no paid or batch tier [V]. It is much weaker than the other candidates [I]. It is offered as a ~$1 add-on, not in B or C.
- **Sampling defaults:** see the prereg §3 table. Kimi's Batch API forbids sending temperature or top_p [V]. Sonnet 5.5 returns a 400 error on a non-default temperature [V].
- **Opus 4.5 effort parameter.** Anthropic's thinking docs say "On Claude Opus 4.5 … effort shapes the overall response while budget_tokens sets thinking depth; set both" [V]. The runner sends only `budget_tokens`, mirroring inspect_ai 0.3.193's mapping of Petri's config. This is now declared as a deviation in prereg §7. Thomas should decide whether to keep it Petri-faithful (my recommendation) or add effort.

**Recommendation [I]: Design C (J = 8) if the extra ~$45 is affordable and Thomas will build the two runners this week. Otherwise Design A, stated honestly as 3 fixed judges.**
- **Design B adds little for its cost and effort.** It has 5 developers but only one mid-tier judge, so it cannot separate tier from developer.
- **Any expanded design is wasted if it delays the Opus leg.** The Opus leg needs no decision and should be submitted as soon as the pre-registration is filed.

## S2.4 New findings from data (cheap-judge pilot, 120 transcripts)

**Reasoning traces in the corpus** (`results/thinking_traces_260.json`):

| Target | Native reasoning | In-text `<thinking>`, all 260 | Confirmatory 140 |
|---|---|---|---|
| Hermes 3 70B | 0/95 | 2/95 | 1/51 |
| DeepSeek V3.1 | 0/100 | 26/100 | 11/54 |
| Mistral Large 2411 | 0/65 | 42/65 | 23/35 |

Pilot mean `unfaithful_thinking` score by target and tag presence:

| Target | Without tags | With tags |
|---|---|---|
| DeepSeek | 1.37 | 4.35 |
| Hermes | 1.13 | 6.6 (one transcript) |
| Mistral | 1.09 | 3.21 |

**Revised tests on the pilot** (`results/pilot120/phi_vs_icc_pilot120_cheap.md`):
- **H1′:** mean D was +0.19 for `concerning`, −0.05 for deception and −0.12 for cooperation. Every CI includes 0, and **0 of 9 cells** had a lower bound above 0 on each dimension.
- **H2′ at target level** (FT − FC):

  | Dimension | c = 4 | c = 7 |
  |---|---|---|
  | `concerning` | −0.01 | −0.04 |
  | deception | +0.02 | −0.06 |
  | cooperation | −0.26 | −0.26 |

  Every Holm-adjusted p-value was 1.0.
- **The descriptive FT(c) curve shows where the earlier effect lived.** For `concerning`, FT is 0.29 at c = 5 and 0.12 at c = 6, against FC = 0.05. Cut-offs off Petri's grid therefore matter a great deal, and choosing them after seeing data would have produced a "result".
- **H2′ at transcript level:** only `concerning`, c = 7, was positive: +0.065 [+0.021, +0.106]. Deception and cooperation are significantly negative at c = 4. Per transcript, the transcript × judge noise dominates both kinds of decision.
- **Model check: passed.** Mean split-half φ 0.27, plug-in 0.24, bias-corrected 0.28.
- **Placebo means:** plug-in φ 0.33–0.34; bias-corrected 0.42–0.43 (theory: 0.425); split-half 0.48–0.54.
- **REML vs ANOVA:**
  - On `concerning`, REML on all 703 valid scores gives σ²_gj = 0.034, against 0.015 from ANOVA on complete cases. The DeepSeek vs Mistral bias-corrected φ moves from 0.50 to 0.35.
  - On `unfaithful_thinking`, REML gives σ²_j = 0, against 0.021 from ANOVA.

  The judge components are fragile, as expected at 2–4 df.
- **Failure rates by severity:** only MiMo has failures, and they are not concentrated in the high stratum: 5.7% high, 4.3% moderate, 10% low, with reason `dim_missing`. The missing-not-at-random flag would not trigger.

## S2.5 Brutal assessment

- **The headline you would like ("frontier judges differ in calibration, not ranking, and that flips safety decisions") was not supported by the pilot's cheap judges** once thresholds were fixed in advance.
  - You now have a pre-registration that can fail cleanly. That is worth more than one that cannot.
  - Write the null-result framing before the money is spent: "At Petri's own cut-offs, judge disagreement rarely changes decisions, because target means sit far from the cut-offs, and transcript sampling dominates contrasts." That is still a publishable, useful finding for Petri users.
- **J = 3 cannot support any random-judge claim.** The Satterthwaite upper limits for σ²_j in the pilot reached 10 to 500,000 squared score points. If you stay at J = 3, cut H3′ to a single sentence.
- **The schedule risk is unchanged and is the real constraint.** The Opus leg (positions 121–260, about $40 at batch-high) needs no design decision. Every day spent choosing between B and C before filing pushes it toward 24 Nov.
- **What I did not verify:**
  - Batch support for Qwen3.8 Max on Qwen Cloud: the pages contradict each other.
  - DeepInfra quantization.
  - Kimi K2.6's max output tokens.
  - That gpt-5.1 is named in OpenAI's temperature-error rule. I inferred it.

## S2.6 Open questions for Thomas

1. **Design A, B, C or C-lite.** I recommend C or A, not B.
2. If B or C: build the Kimi Batch and DeepSeek off-peak runners next, with the same spend gate and mocked tests.
3. **Opus 4.5 `effort`:** keep Petri-faithful (no effort; my recommendation) or add effort high?
4. **Accept the departures from the review's letter:** primary φ = plug-in + CI by inversion, not the bias-corrected point; the model check uses a bracket, not ±0.05.
5. **File on OSF, then submit the Opus leg the same day.**

## S2.7 Addendum (same day): Design C chosen, DeepSeek and Kimi runners built

Thomas chose **Design C (J = 8)**. Fix 11 in S2.2 ("not done") is now **done**.
- No paid calls. No keys exist in this environment.
- Tests: 98 passed, 2 skipped. There are 21 new tests, all with mocked HTTP and no network.

**`petri_v2/runner_kimi.py`** (Moonshot Batch API, judge `kimik26`):
- It follows the OpenAI-compatible flow: upload with `POST /v1/files` (purpose `batch`), create with `POST /v1/batches` (endpoint `/v1/chat/completions`, window `24h`), then poll and download the output and error files.
- Base URL: `https://api.moonshot.ai/v1`. Files are limited to 100 MB, and each file holds one model.
- The request body is `{model: kimi-k2.6, messages: [system, user], max_tokens: 32000, thinking: {type: enabled}}`, with no sampling parameters, as Moonshot requires.
- `reasoning_content` is dropped from the judge output.
- **Assumptions, because the docs do not state them:**
  - a 50,000-request limit per file;
  - the error code for expired items (both `batch_expired` and `expired` are handled).

**`petri_v2/runner_deepseek.py`** (judge `deepseekv4pro`; DeepSeek has no Batch API):
- **What it does:** synchronous `POST https://api.deepseek.com/chat/completions` with `thinking: {type: enabled}`, `reasoning_effort: high` and `max_tokens: 32000`. Requests run in concurrent waves (default 8).
- **Off-peak only:** a request starts only if the next peak window (01–04 and 06–10 UTC, Monday to Friday) is at least 15 minutes away. That margin is longer than the 10-minute request timeout. During peak hours the runner sleeps through the window, or stops if run with `--no-wait`. The spend gate uses the off-peak price.
- **Chinese public holidays** are treated as weekdays. This is conservative: some cheap hours are lost, but nothing is ever paid at peak rates.
- **Same safeguards as the batch runners:** the spend gate, resuming from `results.jsonl`, at most 3 attempts per request, and keys redacted.
- **An HTTP 401, 402 or 403 aborts the run.** Responses already paid for in that wave are saved first, so they are never bought twice.

**Shared:**
- `jobs.chat_body` builds the request bodies.
- `http.KEY_ENV` now redacts `MOONSHOT_API_KEY` and `DEEPSEEK_API_KEY`.
- In `judges.py`, `runner` is True for both judges.
- The no-sampling-parameters test now covers all 8 Design C judges.

**Docs:**
- Prereg §3, §6 and §8 now register Design C.
- Per-judge caps total USD 210, against a dry-run batch-high estimate of $183.49.
- The README has the run commands.

**Limitation, stated plainly:** none of the five extra-judge runners has made a real API call. The mocks follow the documented shapes, but a mock cannot catch a wrong guess about an undocumented field. The first live submission of each provider should be the confirmatory 140 only, and its first results file should be inspected before anything else is sent.
