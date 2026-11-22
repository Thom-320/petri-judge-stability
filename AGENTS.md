# AGENTS.md

Research repo: decision stability of Petri's LLM judges. Read `README.md` first.

## Install

Python 3.13 (CI uses 3.13).

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## Test and reproduce (offline, no API keys)

```bash
python3 -m pytest -q tests                # 9 tests skip without data/raw/, vendor/ or the raw judge text
bash scripts/reproduce_offline.sh         # re-runs the pilot analysis (~2-5 min) and checks the README figures
```

`reproduce_offline.sh` exits non-zero if the regenerated `results/pilot120/` differs from the committed one or if
any README figure does not round to its published value. CI (`.github/workflows/reproduce.yml`) runs both on every PR.

## Do not touch

- Analysis code (`analysis/`, `pilot/scripts/`), results and data (`results/`, `pilot/`), and the figures in `README.md`
  and `docs/`. If a figure does not reproduce, report it; do not edit it.
- `petri_v2/pinned/` (verbatim upstream copies) and `prices.yaml`.
- Paid runs: never start a `petri_v2.runner_*` `run`, and never add API keys or secrets.
- Gitignored inputs (`data/raw/`, `vendor/`, `runs/`, raw judge outputs) are not committed.
