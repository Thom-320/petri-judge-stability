"""Test setup: no network. Every socket connection attempt fails the test."""
import os
import socket
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
VENDOR_SRC = os.path.join(ROOT, "vendor", "inspect_petri", "src")
DATA_DIR = os.path.join(ROOT, "data", "raw", "data")
HAVE_DATA = os.path.exists(os.path.join(DATA_DIR, "corpus_index.json"))
HAVE_VENDOR = os.path.exists(os.path.join(VENDOR_SRC, "petri", "scorers", "prompts.py"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def guard(*a, **k):
        raise RuntimeError("network access attempted in a test")
    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    yield


def petri_real():
    """Import the pinned Petri modules if vendor/ and inspect_ai are available, else skip."""
    if not HAVE_VENDOR:
        pytest.skip("vendor/inspect_petri not cloned (run scripts/setup_vendor.sh)")
    pytest.importorskip("inspect_ai")
    pytest.importorskip("rapidfuzz")
    if VENDOR_SRC not in sys.path:
        sys.path.insert(0, VENDOR_SRC)
    from petri.formatting.xml_messages import format_messages_xml
    from petri.scorers import judge
    from petri.transcript.transcript import Transcript, _collect_messages
    return Transcript, _collect_messages, format_messages_xml, judge
