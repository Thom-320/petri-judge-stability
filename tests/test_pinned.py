"""Our copy of Petri's prompt, dimensions and source files vs the pinned commit f02b3ec."""
import ast
import hashlib
import inspect
import json
import os
import subprocess

import pytest

from conftest import HAVE_VENDOR, ROOT, VENDOR_SRC
from petri_v2 import PETRI_COMMIT, prompts

PIN_DIR = os.path.join(ROOT, "petri_v2", "pinned", "f02b3ec")
PIN = json.load(open(os.path.join(PIN_DIR, "PIN.json")))


def test_pin_manifest_hashes_match_pinned_copies():
    assert PIN["commit"] == PETRI_COMMIT
    for name, meta in PIN["files"].items():
        data = open(os.path.join(PIN_DIR, name), "rb").read()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], name


@pytest.mark.skipif(not HAVE_VENDOR, reason="vendor/inspect_petri not cloned (scripts/setup_vendor.sh)")
def test_pinned_copies_are_byte_identical_to_vendor_at_commit():
    repo = os.path.join(ROOT, "vendor", "inspect_petri")
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert head == PETRI_COMMIT
    for name, meta in PIN["files"].items():
        ours = open(os.path.join(PIN_DIR, name), "rb").read()
        theirs = open(os.path.join(repo, meta["upstream_path"]), "rb").read()
        assert ours == theirs, f"{name} differs from {meta['upstream_path']} at {PETRI_COMMIT}"


@pytest.mark.skipif(not HAVE_VENDOR, reason="vendor/inspect_petri not cloned")
def test_prompt_literals_equal_vendor():
    dims, judge = prompts._load_literals(os.path.join(VENDOR_SRC, "petri", "scorers", "prompts.py"))
    assert dims == prompts.DIMENSIONS
    assert judge == prompts.JUDGE_PROMPT


def test_study_dims_exist_and_cut_is_subset():
    assert all(d in prompts.DIMENSIONS for d in prompts.STUDY_DIMS)
    assert set(prompts.CUT_DIMS) <= set(prompts.STUDY_DIMS)


def test_system_prompt_assembly_and_documented_placeholder_quirk():
    sp = prompts.build_system_prompt()
    for i, d in enumerate(prompts.STUDY_DIMS, 1):
        assert f"{i}. {d}: [score]/10" in sp
        assert f"### {d.replace('_', ' ').title()}" in sp
    # Petri's descriptions end in '{{}}/10'; str.format does not unescape inserted values.
    assert sp.count("{{}}/10") == 4
    # Same length as the pilot's system prompt (pilot/sample_meta.json), built from the same commit.
    meta = json.load(open(os.path.join(ROOT, "pilot", "sample_meta.json")))
    assert len(sp) == meta["system_prompt_chars"]


def _fstring_block(src, anchor):
    i = src.index('f"""', src.index(anchor))
    return src[i: src.index('"""', i + 4) + 3]


def test_user_message_fstring_is_petris():
    """The judge user-message f-string (text and 12-space indentation) is identical to judge.py's."""
    theirs = _fstring_block(open(os.path.join(PIN_DIR, "judge.py"), encoding="utf-8").read(), "user_content = dedent(")
    ours = _fstring_block(inspect.getsource(prompts), "def build_user_message")
    assert ours == theirs


def test_user_message_rendering_matches_petri_dedent():
    xml = "<transcript>\n<user index=\"1\">\nhi\n</user>\n</transcript>"
    msg = prompts.build_user_message(xml)
    assert msg.startswith("Analyze the following transcript between the alignment auditor and the target model.")
    # Because the transcript lines are not indented, dedent removes nothing: later lines keep 12 spaces.
    assert "\n            Analyze the transcript and score it" in msg


def test_pinned_prompts_file_holds_only_literals():
    tree = ast.parse(open(os.path.join(PIN_DIR, "prompts.py"), encoding="utf-8").read())
    for node in tree.body:
        assert isinstance(node, (ast.Expr, ast.Assign)), type(node)
