"""Reuse the pilot's statistics functions without touching pilot/ (SPEC-v2: keep the pilot folder unchanged).

`pilot/scripts/analyze.py` is a script that runs on import, so its pure functions (icc21,
kalpha_interval, varcomp, auc) are extracted with `ast` and compiled on their own, the same way
`pilot/scripts/test_stats.py` does. No other pilot code is executed.
"""
import ast
import os

import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOT_ANALYZE = os.path.join(ROOT, "pilot", "scripts", "analyze.py")
_NAMES = ("icc21", "kalpha_interval", "varcomp", "auc")


def _load(path=PILOT_ANALYZE):
    tree = ast.parse(open(path, encoding="utf-8").read())
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in _NAMES]
    if {n.name for n in keep} != set(_NAMES):
        raise RuntimeError(f"pilot analyze.py is missing one of {_NAMES}")
    ns = {"np": np, "stats": stats}
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)
    return [ns[n] for n in _NAMES]


icc21, kalpha_interval, varcomp, auc = _load()
