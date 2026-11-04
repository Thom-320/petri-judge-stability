import collections
import json
import os

import pytest

from conftest import DATA_DIR, HAVE_DATA, ROOT
from petri_v2 import corpus, jobs

pytestmark = pytest.mark.skipif(not HAVE_DATA, reason="corpus not downloaded (pilot/scripts/fetch_hf.py data/raw)")


def test_260_order_extends_pilot_120():
    rows = corpus.analysis_order(DATA_DIR)
    assert len(rows) == 260
    pilot = json.load(open(os.path.join(ROOT, "pilot", "sample_meta.json")))["rows"]
    assert [r["transcript_key"] for r in rows[:120]] == [p["transcript_key"] for p in pilot]
    assert collections.Counter(r["target"] for r in rows) == {"deepseek_v31": 100, "hermes3": 95, "mistral_large": 65}


def test_inputs_have_no_labels_and_no_seed_text():
    inp = jobs.build_inputs(3, data_dir=DATA_DIR)
    for i in inp:
        assert "expected_dimensions" not in i["user"] and "severity" not in i
        assert set(i) == {"pos", "transcript_id", "transcript_key", "system", "user", "dims", "view", "input_sha256"}
