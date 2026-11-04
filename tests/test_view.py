"""The judge transcript view: port vs Petri's real code and vs committed fingerprints."""
import glob
import hashlib
import json
import os

import pytest

from conftest import DATA_DIR, HAVE_DATA, ROOT, petri_real
from petri_v2 import view


def ev(view_name, patch, kind="json_patch"):
    return {"type": "transcript_event", "view": view_name, "edit": {"operation": kind, "patch": patch}}


def add(i, m):
    return {"op": "add", "path": f"/{i}", "from_": None, "value": m, "replaced": None}


SYS = {"id": "s", "role": "system", "content": "You are helpful."}
U1 = {"id": "u1", "role": "user", "content": "first"}
A1 = {"id": "a1", "role": "assistant", "content": [{"type": "reasoning", "reasoning": "hmm", "redacted": False},
                                                    {"type": "text", "text": "answer one"}]}
U2 = {"id": "u2", "role": "user", "content": "retry"}
A2 = {"id": "a2", "role": "assistant", "content": "answer two",
      "tool_calls": [{"id": "c1", "function": "bash", "arguments": {"cmd": "ls", "n": 3}}]}
AUD = {"id": "x", "role": "user", "content": "AUDITOR COMMENTARY"}


def synthetic():
    return {"events": [
        ev("target", [add(0, SYS)]), ev("auditor", [add(0, AUD)]), ev("target", [add(1, U1)]),
        ev("target", [add(2, A1)]),
        ev("target", [{"op": "remove", "path": "/2"}]), ev("target", [{"op": "remove", "path": "/1"}]),  # rollback
        ev("target", [add(1, U2)]), ev("target", [add(2, A2)]),
        {"type": "decision_event", "content": "ignored"}],
        "target_messages": [SYS, U2, A2]}


def test_rollback_branches_are_kept_with_info_markers():
    # Two single-message removes create an intermediate branch [S, U1], so Petri emits two markers
    # (checked against the real Petri code with the same events).
    msgs = view.judge_messages(synthetic(), "petri")
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "info", "info", "user", "assistant"]
    assert msgs[3]["content"].startswith("Starting new conversation branch from this message:\n<message>\nfirst")
    assert msgs[4]["content"].startswith("Starting new conversation branch from this message:\n<message>\nYou are helpful.")
    xml = view.format_messages_xml(msgs)[0]
    assert "AUDITOR COMMENTARY" not in xml
    assert "<info>\nStarting new conversation branch" in xml
    assert '<assistant index="5">\nanswer two\n<tool_call name="bash" id="c1">' in xml  # info has no index
    assert '<parameter name="n">3</parameter>' in xml
    assert "<thinking>\nhmm\n</thinking>\nanswer one" in xml


def test_target_messages_view_is_final_branch_only():
    xml = view.transcript_xml(synthetic(), "target_messages")
    assert "first" not in xml and "retry" in xml and "<info>" not in xml


def test_branch_from_beginning_marker():
    t = {"events": [ev("target", [add(0, U1)]), ev("target", [{"op": "remove", "path": "/0"}]),
                    ev("target", [add(0, U2)])]}
    msgs = view.judge_messages(t)
    assert [m.get("content") for m in msgs] == ["first", "Starting new conversation branch from the beginning.", "retry"]


def test_long_branch_point_is_truncated_like_petri():
    long = {"id": "L", "role": "user", "content": "a" * 600 + "b" * 600}
    t = {"events": [ev("target", [add(0, long)]), ev("target", [add(1, A1)]),
                    ev("target", [{"op": "remove", "path": "/1"}]), ev("target", [add(1, A2)])]}
    info = [m for m in view.judge_messages(t) if m["role"] == "info"][0]["content"]
    assert "a" * 500 + "..." + "b" * 500 in info


def test_other_edit_operations():
    msgs = [SYS, U1]
    assert view._apply_edit({"operation": "add", "message": A1}, msgs)[-1] == A1
    assert view._apply_edit({"operation": "rollback", "count": 1}, msgs) == [SYS]
    assert view._apply_edit({"operation": "rollback", "count": 0, "to_id": "s"}, msgs) == [SYS]
    assert view._apply_edit({"operation": "reset", "new_messages": [U2]}, msgs) == [U2]


@pytest.mark.skipif(not HAVE_DATA, reason="corpus not downloaded (pilot/scripts/fetch_hf.py data/raw)")
def test_corpus_view_matches_committed_petri_fingerprints():
    fp = json.load(open(os.path.join(ROOT, "tests", "fixtures", "petri_view_sha256.json")))["sha256"]
    files = sorted(glob.glob(os.path.join(DATA_DIR, "transcripts", "*.json")))
    assert len(files) == len(fp) == 311
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        assert hashlib.sha256(view.transcript_xml(d).encode()).hexdigest() == fp[os.path.basename(f)], f


@pytest.mark.skipif(not HAVE_DATA, reason="corpus not downloaded")
def test_corpus_view_matches_live_petri_code_sample():
    Transcript, collect, fmt, _ = petri_real()
    files = sorted(glob.glob(os.path.join(DATA_DIR, "transcripts", "*.json")))
    rollback = [f for f in files if view.n_target_branches(json.load(open(f))) > 1][:10]
    for f in files[:10] + rollback:
        d = json.load(open(f, encoding="utf-8"))
        t = Transcript.model_validate(d)
        assert fmt(collect(t.events, "target", add_only=True, indicate_rollbacks=True))[0] == view.transcript_xml(d)


@pytest.mark.skipif(not HAVE_DATA, reason="corpus not downloaded")
def test_views_differ_exactly_on_rollback_transcripts():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "transcripts", "*.json")))
    n_rb = n_diff = 0
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        rb = view.n_target_branches(d) > 1
        diff = view.transcript_xml(d, "petri") != view.transcript_xml(d, "target_messages")
        assert rb == diff, f
        n_rb += rb
        n_diff += diff
    assert n_rb == 64
