# Petri judge stability

**Does LLM-judge disagreement change a safety decision?**

This is a measurement study of the LLM judges that score transcripts in [Petri](https://github.com/safety-research/petri), an open-source alignment-auditing tool. It does not ask the usual question, "how well do the judges agree?" (ICC, Krippendorff's α). It asks a more practical one: **how often would swapping the judge, or re-running it, flip the decision a Petri user actually makes?**

> Status: a completed pilot with **cheap judges**, and a main study whose pre-registration is drafted but **not yet filed**; the study has not been run. No result here is about Petri's official judges.

## The question: φ versus ICC

- **ICC** answers "what share of score variance comes from transcripts rather than judges?" A high ICC can coexist with judges that disagree on a decision, and a low ICC can coexist with decisions that never flip.
- **φ(D)** is the probability that a decision D comes out differently under an independent replication of the measurement: another judge from the panel, another sample of the same judge, another draw of transcripts. It is computed per decision and per facet (judge, repeat, transcript), with intervals, a bias-corrected version and a D-study (`analysis/phi.py`).
- **Levels versus contrasts.** Petri's scores feed two kinds of decision:
  - a **threshold** decision: is target A's mean on a dimension at or above Petri's cut-off (4 = medium, 7 = high)?
  - a **contrast** decision: does target A look worse than target B?

  The hypothesis was that judges differ mostly in **calibration** (level), not in **ranking**. If so, judge swaps should flip threshold decisions more often than contrast decisions.

## What the pilot found (and why it is weak evidence)

Setup:
- 120 transcripts from the public, synthetic [Petri Synthetic Calibration Corpus](https://huggingface.co/datasets/adlnk/petri-synthetic-transcripts) (CC-BY-4.0). Three target models: Hermes 3 70B, DeepSeek V3.1, Mistral Large 2411.
- Four Petri dimensions.
- Three **cheap judges** from different families (Muse Spark 1.3 Contributor, MiMo-V2.6-Flash, DeepSeek V4.1 Flash), each scoring every transcript **twice**.
- Full report: `docs/PILOT-REPORT.md`. φ-vs-ICC tables: `results/pilot120/phi_vs_icc_pilot120_cheap.md`.

Findings:
1. **Agreement looks good by the usual metrics.**
   - Inter-judge ICC(2,1) is 0.74 to 0.88 across dimensions (`concerning` 0.88 [0.84, 0.92]).
   - Test-retest is 0.65 to 0.99 per judge.
   - Transcripts explain 71 to 87% of the variance.
2. **The usual metrics do not predict decision stability.**
   - With the same ICC of 0.88 on `concerning`, the decision "Hermes is less concerning than Mistral" has φ ≈ 0.
   - "DeepSeek V3.1 vs Mistral" on the same dimension has φ = 0.32 [0.005, 0.50], close to a coin flip (0.5).
   - Most of that instability comes from **transcript sampling**, not from the judges.
3. **The levels-versus-contrasts hypothesis failed at Petri's cut-offs, 4 and 7.**
   - None of the 9 pre-specified tests was supported. Every Holm-adjusted p was 1.0.
   - Calibration offsets exceeded contrast discrepancies on 0 of 9 judge-pair × contrast cells per dimension.
   - At target level, threshold-minus-contrast flip rates ranged from −0.26 to +0.02.
   - The reason: target means sit well below 4 and 7, so threshold decisions almost never flip.
   - The effect does appear at cut-offs near the means (for `concerning` at c = 5, threshold flips 0.29 vs contrast flips 0.05). Those cut-offs are not Petri's, and choosing them after seeing the data would have manufactured a result.
4. **Petri source findings** (commit f02b3ec), independent of the statistics:
   - When all retries fail, Petri silently scores every dimension as 1.
   - Its required-tag check never fires.
   - The prompt shows the judge a literal `{{}}/10` placeholder.

   Details are in `docs/PILOT-REPORT.md`, "Verified source findings".

Caveats:
- **Cheap judges, not Petri's official judges** (Claude Opus, Gemini Pro, GPT). The numbers do not transfer.
- J = 3 judges and R = 2 repeats give 2 df and 1 df for the judge and repeat components. Random-judge claims are not supported, and REML and ANOVA estimates of the judge components disagree.
- The corpus is synthetic, with planted behaviour. Its labels are design intent, not ground truth. Floor effects are strong on two dimensions.
- The pilot deviated from Petri in documented ways: four dimensions, first-attempt parsing without retries, and no 10k reasoning budget. One judge (MiMo) returned no usable score block on 6.7% of calls.
- These pilot analyses were written **after** an earlier revision of the plan had seen the same data. They are therefore exploratory "predictions against interest", not confirmatory results.

## The pre-registration

- `docs/PREREGISTRATION.md`: the plan, revision 2 (10 Oct 2026). The confirmatory family has 9 Holm-controlled tests on Petri's three fixed judges, with Petri's own cut-offs fixed in advance. The primary result comes from **140 transcripts no judge has seen**.
- `docs/OSF-FILING.md`: the same plan as OSF Preregistration template fields.
- **It has not been filed on OSF yet.** Until it is, treat it as a draft. The filing must precede any call to an official judge.
- `docs/SPEC-v2.md` and `docs/CLOUD-SESSION-2026-10.md` are the build spec and build logs, including the design choice (Design C, J = 8) and its cost estimates.

## Reproduce

Requires Python 3.13 (3.11+ likely works). No API keys are needed for anything in this section.

```bash
pip install -r requirements.txt
python3 -m pytest -q tests                              # offline; network access fails the test run

# pilot analysis from the committed scores (cheap judges); writes results/pilot120/
python3 -m analysis.run --judgments pilot/scores_pilot120.jsonl --meta pilot/sample_meta.json \
    --n 120 --judges muse,mimo,deepseek --out results/pilot120 --tag pilot120_cheap

# optional: the corpus (317 files, 106.5 MB, CC-BY-4.0; gitignored) and a pinned Petri clone
python3 -I pilot/scripts/fetch_hf.py data/raw
./scripts/setup_vendor.sh                               # vendor/inspect_petri at f02b3ec (gitignored)

# dry-run cost estimates (no keys; token counts are a tokenizer approximation)
python3 -m petri_v2.estimate --scenarios --json results/estimate_scenarios.json
python3 -m petri_v2.estimate --designs --json results/estimate_designs.json   # J = 3 / 6 / 8 options
python3 -m petri_v2.corpus --thinking-report results/thinking_traces_260.json
```

What to expect:
- `pilot/scores_pilot120.jsonl` holds the pilot's 720 judge records: parsed scores, status, token usage and call metadata, with no generated text.
- **The judges' raw generated text is not redistributed** (the terms for redistributing it were not established). For that reason two parser-equivalence tests skip, along with tests that need `data/raw/` or `vendor/`.
- `tests/test_regression_pilot.py` checks that the analysis code reproduces the pilot's published statistics to 1e-12.

## Repository map

- `pilot/`: the completed pilot (scripts, scores, results, figures). The provider-specific runner is not included.
- `petri_v2/`: Petri-faithful judge input and parser, the batch runners (Anthropic, Gemini, OpenAI, Moonshot), the off-peak DeepSeek runner and the dry-run cost estimator.
  - `prompts.py`, `view.py` and `parse.py` port `meridianlabs-ai/inspect_petri` at `petri-v2@f02b3ec` (MIT).
  - Verbatim pinned copies are in `petri_v2/pinned/f02b3ec/`.
- `analysis/`: four parts.
  - Reliability statistics (ICC, α, variance components, rank stability).
  - Confirmatory tests (`confirm.py`).
  - φ, the D-study, controls and the model check (`phi.py`).
  - REML sensitivity (`reml.py`).
- `results/`: aggregates and dry-run estimates. `meta_260.json` holds only the public labels of the 260 analysis transcripts, which are never shown to a judge.
- `tests/`: offline tests with mocked HTTP for every provider.
- `prices.yaml`: the only price source, with URLs and dates checked.

## Paid runs (not needed to reproduce the pilot)

Do not start these without approval. Each runner needs its key in an environment variable (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `MOONSHOT_API_KEY`, `DEEPSEEK_API_KEY`). It refuses to submit unless both `--confirm-spend` and `--budget-usd` are given and the dry-run estimate is within the budget.

```bash
python3 -m petri_v2.runner_anthropic plan --start 120 --n 260          # confirmatory 140 first
python3 -m petri_v2.runner_anthropic run  --start 120 --n 260 --budget-usd 45 --confirm-spend
python3 -m petri_v2.runner_gemini    run  --start 120 --n 260 --budget-usd 20 --confirm-spend
python3 -m petri_v2.runner_openai    run  --start 120 --n 260 --budget-usd 16 --confirm-spend
# then the pilot 120 (--n 120); runs are resumable (state in runs/<provider>/)
# Design C extra judges, confirmatory 140 only (needs MOONSHOT_API_KEY / DEEPSEEK_API_KEY for the last two)
python3 -m petri_v2.runner_anthropic run  --judges sonnet55      --start 120 --n 260 --budget-usd 20 --confirm-spend
python3 -m petri_v2.runner_gemini    run  --judges gemini38flash --start 120 --n 260 --budget-usd 10 --confirm-spend
python3 -m petri_v2.runner_openai    run  --judges gpt54mini     --start 120 --n 260 --budget-usd 10 --confirm-spend
python3 -m petri_v2.runner_kimi      run  --start 120 --n 260 --budget-usd 10 --confirm-spend
python3 -m petri_v2.runner_deepseek  run  --start 120 --n 260 --budget-usd 10 --confirm-spend   # off-peak only
python3 -m analysis.run --judgments runs/*/results.jsonl --meta results/meta_260.json \
    --n 260 --judges opus45,gemini31pro,gpt51 --out results/v2 --tag v2
# expanded panel (Design B/C): add the extra judges; the confirmatory tests stay on the Petri three
#   --judges opus45,gemini31pro,gpt51,sonnet55,gemini38flash,gpt54mini,deepseekv4pro,kimik26 \
#   --confirm-judges opus45,gemini31pro,gpt51
```

## Cost (dry run, 2026-10-09)

The design is 260 transcripts × 3 judges × 2 repeats = 1,560 requests, with four dimensions and the Petri view. Assumptions:

- Input tokens are approximated with tiktoken `o200k_base`, about 7,650 per request. Anthropic's token counter needs a key, so it was not used.
- Output per request: low case 4,000 tokens, high case 10,000 tokens.
- Prices are list prices from `prices.yaml`, with no caching discount.

| Scenario | Requests | Standard low | Standard high | Batch low | Batch high |
|---|---|---|---|---|---|
| Full: 260 transcripts, 4 dims | 1,560 | $130.59 | $277.23 | $65.30 | $138.62 |
| Pilot set: 120 transcripts | 720 | $60.20 | $127.88 | $30.10 | $63.94 |
| Untouched: 140 transcripts | 840 | $70.39 | $149.35 | $35.19 | $74.67 |
| Cut: 260 transcripts, 2 dims | 1,560 | $129.06 | $275.70 | $64.53 | $137.85 |
| Cut: 120 transcripts, 2 dims | 720 | $59.50 | $127.18 | $29.75 | $63.59 |

Full design, batch prices, by judge (low / high):

| Judge | Batch low | Batch high |
|---|---|---|
| Claude Opus 4.5 | $35.95 | $74.95 |
| Gemini 3.1 Pro Preview | $16.46 | $35.18 |
| GPT-5.1 | $12.89 | $28.49 |

If every request used its full 32,000-token output cap, the full design would cost $407.46 at batch prices. Per-judge tables are in `docs/CLOUD-SESSION-2026-10.md`.

Design options (dry run 2026-10-10; extra judges score the confirmatory 140 only, R = 2):

| Design | Requests | Batch low | Batch high | Batch cap |
|---|---|---|---|---|
| A, J = 3 (Petri panel) | 1,560 | $65.30 | $138.62 | $407.46 |
| B, J = 6 (+ Gemini 3.8 Flash, DeepSeek V4 Pro, Kimi K2.6) | 2,400 | $75.75 | $159.58 | $466.95 |
| C, J = 8 (B + Sonnet 5.5, GPT-5.4 mini) | 2,960 | $87.48 | $183.49 | $535.52 |
| C-lite, J = 8 (extra judges R = 2 on 70, R = 1 on 70) | 2,610 | $81.85 | $172.18 | $503.42 |

**Design C (J = 8) is the registered design.** DeepSeek has no Batch API: `runner_deepseek` makes synchronous calls only in DeepSeek's off-peak window and is priced at the off-peak rate.

## License, notices, AI use

- Original code: MIT (`LICENSE`).
- Third-party material: `NOTICE`. This covers Petri code (MIT, Safety Research) and corpus metadata (CC-BY-4.0, adlnk).
- How AI was used to build this project: `AI-USE.md`.

Not affiliated with or endorsed by Anthropic, Safety Research, Meridian Labs or any model provider.
