# AI-use statement

This project studies LLM judges, and it was also built with heavy AI assistance. Both uses are declared here.

## AI as the object of study

- LLMs are the measured instruments.
- The pilot used three low-cost judges (Muse Spark, MiMo-Flash, DeepSeek-Flash) to score 120 synthetic Petri transcripts, twice each.
- The planned v2 study uses Petri's own judges and optional extra judges, called through their providers' batch APIs.
- Model names, IDs and settings are listed in `petri_v2/judges.py`, `docs/PILOT-REPORT.md` and `docs/PREREGISTRATION.md`.

## AI as a research and coding assistant

- **Code.** Most of the code was drafted by AI coding agents (Anthropic's Claude, via Claude Code), working under Thomas Chisica's direction. This covers the runners, the estimator, the parser and view ports, the analysis package and the tests. Commits co-authored by an agent carry a `Co-Authored-By: Claude` trailer or the `Claude <noreply@anthropic.com>` author line.
- **Documents.** The pilot report, the build logs (`docs/CLOUD-SESSION-2026-10.md`), the prior-work note, the v2 spec, the pre-registration drafts and this release's README were drafted by AI agents. Thomas reviewed and edited them.
- **Second opinions.** An independent AI reviewer critiqued the pre-registration. The fixes are logged in `docs/CLOUD-SESSION-2026-10.md`, Session 2.

## Human responsibility

- Thomas Chisica chose the research question, the design (including Design C), the hypotheses and the budget.
- Thomas approved every paid run, and is responsible for every claim.
- Statistical code is checked by tests. These include synthetic recovery checks and an exact (1e-12) reproduction of the pilot statistics.
- Claims about external sources are marked verified or unverified in the documents where they appear.
- AI-drafted text can contain errors. Please report any you find as an issue.
