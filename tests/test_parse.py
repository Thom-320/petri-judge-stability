"""Parser: Petri semantics, failures counted with reason codes, never floored."""
import json
import os

import pytest

from conftest import ROOT, petri_real
from petri_v2.parse import parse_response
from petri_v2.prompts import STUDY_DIMS

D = STUDY_DIMS


def scores_block(vals, extra=""):
    lines = "\n".join(f"{i + 1}. {d}: {v}/10" for i, (d, v) in enumerate(zip(D, vals)))
    return f"<highlights>h</highlights><summary>s</summary><scores>\n{lines}\n{extra}</scores><justification>j</justification>"


def test_full_parse():
    p = parse_response(scores_block([3, 1, 2, 10]), D)
    assert p["scores"] == dict(zip(D, [3, 1, 2, 10])) and p["missing"] == {} and p["petri_attempt_ok"]


def test_no_response_and_empty():
    assert set(parse_response(None, D)["missing"].values()) == {"no_response"}
    assert set(parse_response("  \n", D)["missing"].values()) == {"empty_response"}


def test_no_scores_block_with_refusal_flag():
    p = parse_response("I'm sorry, I can't help with that.", D)
    assert set(p["missing"].values()) == {"no_scores_block"} and "refusal_suspect" in p["flags"]
    assert p["scores"] == {}  # never floored to 1


def test_unclosed_scores_tag_is_missing_like_petri():
    p = parse_response("<scores>\n1. concerning: 3/10\n", D, finish_reason="length")
    assert set(p["missing"].values()) == {"no_scores_block"} and "truncated" in p["flags"]


def test_highlights_missing_does_not_matter_like_petri():
    txt = "<summary>s</summary><scores>\n" + "\n".join(f"{i + 1}. {d}: 2/10" for i, d in enumerate(D)) + "\n</scores>"
    assert parse_response(txt, D)["petri_attempt_ok"]


def test_no_score_lines_dim_missing_out_of_range():
    assert set(parse_response("<scores>nothing</scores>", D)["missing"].values()) == {"no_score_lines"}
    p = parse_response(scores_block([3, 1, 2]), D)
    assert p["missing"] == {D[3]: "dim_missing"} and not p["petri_attempt_ok"]
    p = parse_response(scores_block([0, 1, 2, 3]), D)
    assert p["missing"] == {D[0]: "out_of_range"} and p["petri_scores"][D[0]] == 0  # Petri would keep 0


def test_duplicates_last_wins_like_petri():
    p = parse_response(scores_block([3, 1, 2, 4], extra=f"5. {D[0]}: 7/10\n"), D)
    assert p["scores"][D[0]] == 7


RAW_PILOT = os.path.join(ROOT, "pilot", "raw", "judgments_final.jsonl")


def raw_pilot():
    """The raw judge outputs are not in the public repository ; skip if absent."""
    if not os.path.exists(RAW_PILOT):
        pytest.skip("pilot/raw/judgments_final.jsonl not present (raw judge outputs are not redistributed)")
    return [json.loads(x) for x in open(RAW_PILOT, encoding="utf-8")]


def test_matches_pilot_recorded_parse_on_720_outputs():
    recs = raw_pilot()
    for r in recs:
        p = parse_response(r.get("content"), D, finish_reason=r.get("finish_reason"))
        assert p["scores"] == r["parse"]["scores"], r["job"]
        assert sorted(p["missing"]) == sorted(r["parse"]["missing"]), r["job"]


def test_matches_live_petri_parser_on_720_outputs():
    _, _, _, judge = petri_real()
    recs = raw_pilot()
    for r in recs:
        p = parse_response(r["content"], D)
        try:
            ps = judge._parse_judge_response(r["content"], {}, [], set(D), 10).scores
        except ValueError:
            ps = {}
        assert ps == p["petri_scores"], r["job"]
        assert (set(ps) == set(D)) == p["petri_attempt_ok"]
