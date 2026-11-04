"""Batch runners for all three providers against fake HTTP servers (no network, no keys)."""
import glob
import hashlib
import json
import os

import numpy as np
import pytest

import fakes
from petri_v2 import jobs, prompts
from petri_v2.batch import SpendRefused
from petri_v2.runner_anthropic import AnthropicRunner
from petri_v2.runner_gemini import GeminiRunner
from petri_v2.runner_kimi import KimiRunner
from petri_v2.runner_openai import OpenAIRunner

SECRET = {"ANTHROPIC_API_KEY": "sk-ant-TESTSECRET-0123456789", "GEMINI_API_KEY": "AIzaTESTSECRET0123456789",
          "OPENAI_API_KEY": "sk-proj-TESTSECRET-0123456789", "MOONSHOT_API_KEY": "sk-kimi-TESTSECRET-0123456789",
          "DEEPSEEK_API_KEY": "sk-ds-TESTSECRET-0123456789"}

CASES = [
    (AnthropicRunner, fakes.AnthropicServer, "opus45"),
    (GeminiRunner, fakes.GeminiServer, "gemini31pro"),
    (OpenAIRunner, fakes.OpenAIServer, "gpt51"),
    (KimiRunner, fakes.KimiServer, "kimik26"),
]


def synthetic_inputs(n=4):
    system = prompts.build_system_prompt()
    out = []
    for i in range(n):
        user = prompts.build_user_message(f"<transcript>\n<user index=\"1\">\nhello {i}\n</user>\n</transcript>")
        out.append({"pos": i + 1, "transcript_id": f"{i:03d}" + "a" * 29, "transcript_key": f"t{i}.json",
                    "system": system, "user": user, "dims": list(prompts.STUDY_DIMS), "view": "petri",
                    "input_sha256": hashlib.sha256((system + user).encode()).hexdigest()})
    return out


def make(runner_cls, server_cls, tmp_path, logs):
    t = fakes.FakeTransport()
    server = server_cls(t)
    r = runner_cls(str(tmp_path), transport=t, sleep=lambda s: None, log=logs.append)
    return r, t, server


@pytest.fixture
def keys(monkeypatch):
    for k, v in SECRET.items():
        monkeypatch.setenv(k, v)


@pytest.mark.parametrize("runner_cls,server_cls,label", CASES)
def test_full_cycle_resume_and_retry(runner_cls, server_cls, label, tmp_path, keys, capsys):
    logs = []
    r, t, server = make(runner_cls, server_cls, tmp_path, logs)
    job_list = jobs.build_jobs(synthetic_inputs(4), [label])
    r.run(job_list, budget_usd=100.0, confirm_spend=True)
    res = [json.loads(x) for x in open(r.results_path)]
    assert len(res) == 8
    by = {x["custom_id"]: x for x in res}
    good = by[jobs.custom_id("002" + "a" * 29, label, 1)]
    assert good["status"] == "responded" and good["parse"]["scores"] == {d: i + 2 for i, d in enumerate(prompts.STUDY_DIMS)}
    assert "SECRET THOUGHTS" not in good["content"]  # thinking/thought parts are not judge output
    refusal = by[jobs.custom_id("001" + "a" * 29, label, 1)]
    assert refusal["status"] == "responded" and refusal["parse"]["scores"] == {}
    assert set(refusal["parse"]["missing"].values()) == {"no_scores_block"} and "refusal_suspect" in refusal["parse"]["flags"]
    failed = by[jobs.custom_id("000" + "a" * 29, label, 2)]
    assert failed["status"] in ("errored", "expired") and set(failed["parse"]["missing"].values()) == {"no_response"}

    # resume: only the failed request is resubmitted, nothing else
    n_calls = len(t.calls)
    sub = r.submit(job_list, budget_usd=100.0, confirm_spend=True)
    assert len(sub) == 1
    new_batch = [c for c in t.calls[n_calls:] if c["method"] == "POST"]
    sent = json.dumps([c["body"].decode("utf-8", "replace") for c in new_batch if c["body"]])
    assert failed["custom_id"] in sent and good["custom_id"] not in sent
    # a pending batch is not resubmitted
    assert r.submit(job_list, budget_usd=100.0, confirm_spend=True) == []

    # keys: sent only in auth headers, never written or printed
    out = capsys.readouterr()
    blob = out.out + out.err + "\n".join(logs)
    for f in glob.glob(os.path.join(str(tmp_path), "**", "*"), recursive=True):
        if os.path.isfile(f):
            blob += open(f, encoding="utf-8").read()
    for v in SECRET.values():
        assert v not in blob
    for c in t.calls:
        assert SECRET[r.key_env] not in (c["body"] or b"").decode("utf-8", "replace")


@pytest.mark.parametrize("runner_cls,server_cls,label", CASES)
def test_request_shapes(runner_cls, server_cls, label, tmp_path, keys):
    r, t, server = make(runner_cls, server_cls, tmp_path, [])
    job_list = jobs.build_jobs(synthetic_inputs(2), [label])
    r.submit(job_list, budget_usd=100.0, confirm_spend=True)
    posts = [c for c in t.calls if c["method"] == "POST" and "count_tokens" not in c["url"]]
    if runner_cls is AnthropicRunner:
        c = posts[0]
        assert c["url"] == "https://api.anthropic.com/v1/messages/batches"
        assert c["headers"]["anthropic-version"] == "2023-06-01" and c["headers"]["x-api-key"] == SECRET["ANTHROPIC_API_KEY"]
        req = json.loads(c["body"])["requests"][0]
        assert jobs.CUSTOM_ID_RE.match(req["custom_id"])
        p = req["params"]
        assert p["model"] == "claude-opus-4-5-20251101" and p["max_tokens"] == 32000
        assert p["thinking"] == {"type": "enabled", "budget_tokens": 10000} and "temperature" not in p
        assert p["system"].startswith("You are an impartial judge") and p["messages"][0]["role"] == "user"
    elif runner_cls is GeminiRunner:
        assert posts[0]["url"] == "https://generativelanguage.googleapis.com/upload/v1beta/files"
        assert posts[0]["headers"]["X-Goog-Upload-Protocol"] == "resumable"
        assert posts[2]["url"] == ("https://generativelanguage.googleapis.com/v1beta/models/"
                                   "gemini-3.1-pro-preview:batchGenerateContent")
        assert all(c["headers"]["x-goog-api-key"] == SECRET["GEMINI_API_KEY"] for c in posts)
        line = server.files["files/in1"][0]
        g = line["request"]["generationConfig"]
        assert g["maxOutputTokens"] == 32000 and g["thinkingConfig"] == {"thinkingLevel": "HIGH", "includeThoughts": True}
        assert "thinkingBudget" not in g["thinkingConfig"]
    elif runner_cls is KimiRunner:
        assert posts[0]["url"] == "https://api.moonshot.ai/v1/files" and posts[1]["url"] == "https://api.moonshot.ai/v1/batches"
        assert all(c["headers"]["Authorization"] == f"Bearer {SECRET['MOONSHOT_API_KEY']}" for c in posts)
        line = server.files["file-in1"][0]
        assert line["method"] == "POST" and line["url"] == "/v1/chat/completions"
        b = line["body"]
        assert b["model"] == "kimi-k2.6" and b["max_tokens"] == 32000 and b["thinking"] == {"type": "enabled"}
        assert [m["role"] for m in b["messages"]] == ["system", "user"]
        assert b["messages"][0]["content"].startswith("You are an impartial judge")
        assert not {"temperature", "top_p", "n", "presence_penalty", "frequency_penalty"} & set(b)
        assert len({ln["body"]["model"] for ln in server.files["file-in1"]}) == 1  # one model per batch file
    else:
        assert posts[0]["url"] == "https://api.openai.com/v1/files" and posts[1]["url"] == "https://api.openai.com/v1/batches"
        assert all(c["headers"]["Authorization"] == f"Bearer {SECRET['OPENAI_API_KEY']}" for c in posts)
        line = server.files["file-in1"][0]
        assert line["method"] == "POST" and line["url"] == "/v1/responses"
        b = line["body"]
        assert b["model"] == "gpt-5.1-2025-11-13" and b["max_output_tokens"] == 32000
        assert b["reasoning"] == {"effort": "high"} and b["input"][0]["role"] == "developer"


@pytest.mark.parametrize("runner_cls,server_cls,label", CASES)
def test_spend_gate(runner_cls, server_cls, label, tmp_path, keys):
    r, t, _ = make(runner_cls, server_cls, tmp_path, [])
    job_list = jobs.build_jobs(synthetic_inputs(2), [label])
    with pytest.raises(SpendRefused, match="confirm-spend"):
        r.submit(job_list, budget_usd=100.0, confirm_spend=False)
    with pytest.raises(SpendRefused, match="budget-usd not given"):
        r.submit(job_list, budget_usd=None, confirm_spend=True)
    with pytest.raises(SpendRefused, match="exceeds"):
        r.submit(job_list, budget_usd=0.01, confirm_spend=True)
    assert not [c for c in t.calls if "batches" in c["url"] or "files" in c["url"]]


@pytest.mark.parametrize("runner_cls,server_cls,label", CASES)
def test_refuses_without_key(runner_cls, server_cls, label, tmp_path, monkeypatch):
    for k in SECRET:
        monkeypatch.delenv(k, raising=False)
    r, t, _ = make(runner_cls, server_cls, tmp_path, [])
    with pytest.raises(SystemExit, match="is not set"):
        r.submit(jobs.build_jobs(synthetic_inputs(1), [label]), budget_usd=100.0, confirm_spend=True)
    assert t.calls == []


def test_retired_judge_is_refused(tmp_path, keys):
    r, t, _ = make(GeminiRunner, fakes.GeminiServer, tmp_path, [])
    with pytest.raises(SystemExit, match="not served"):
        r.submit(jobs.build_jobs(synthetic_inputs(1), ["gemini3pro"]), budget_usd=100.0, confirm_spend=True)


def test_wrong_provider_is_refused(tmp_path, keys):
    r, t, _ = make(OpenAIRunner, fakes.OpenAIServer, tmp_path, [])
    with pytest.raises(SystemExit, match="belongs to anthropic"):
        r.submit(jobs.build_jobs(synthetic_inputs(1), ["opus45"]), budget_usd=100.0, confirm_spend=True)


def test_anthropic_gate_uses_count_tokens_endpoint_when_key_present(tmp_path, keys):
    logs = []
    r, t, _ = make(AnthropicRunner, fakes.AnthropicServer, tmp_path, logs)
    r.submit(jobs.build_jobs(synthetic_inputs(2), ["opus45"]), budget_usd=100.0, confirm_spend=True)
    ct = [c for c in t.calls if c["url"].endswith("/v1/messages/count_tokens")]
    assert len(ct) == 2  # one per distinct input, shared by both repeats
    body = json.loads(ct[0]["body"])
    assert set(body) == {"model", "system", "messages", "thinking"}


def test_opus55_successor_uses_adaptive_thinking():
    job = jobs.build_jobs(synthetic_inputs(1), ["opus55"])[0]
    p = jobs.anthropic_params(job)
    assert p["thinking"] == {"type": "adaptive"} and p["output_config"] == {"effort": "high"}


def test_http_error_text_is_redacted(monkeypatch):
    from petri_v2 import http
    monkeypatch.setenv("OPENAI_API_KEY", SECRET["OPENAI_API_KEY"])
    e = http.HTTPError(401, f"bad key {SECRET['OPENAI_API_KEY']} Bearer abc.def")
    assert SECRET["OPENAI_API_KEY"] not in str(e) and "abc.def" not in str(e)


def test_runner_records_load_into_analysis(tmp_path, keys):
    from analysis import data
    r, t, _ = make(AnthropicRunner, fakes.AnthropicServer, tmp_path, [])
    inputs = synthetic_inputs(4)
    r.run(jobs.build_jobs(inputs, ["opus45"]), budget_usd=100.0, confirm_spend=True)
    recs = data.read_records(r.results_path)
    meta = [{"pos": i["pos"], "transcript_id": i["transcript_id"]} for i in inputs]
    Y = data.score_tensor(recs, meta, "concerning", ["opus45"])
    assert Y.shape == (4, 1, 2) and np.isnan(Y[0, 0, 1]) and np.isnan(Y[1, 0, 0]) and Y[2, 0, 0] == 2
    miss = data.missing_summary(recs, ["opus45"], prompts.STUDY_DIMS)["opus45"]["missing_cells_by_reason"]
    assert miss == {"no_response": 4, "no_scores_block": 4}


def test_provider_failures_retried_at_most_three_times(tmp_path, keys):
    r, t, _ = make(AnthropicRunner, fakes.AnthropicServer, tmp_path, [])
    job_list = jobs.build_jobs(synthetic_inputs(1), ["opus45"])  # t000...-r2 always errors
    for _ in range(5):
        r.run(job_list, budget_usd=100.0, confirm_spend=True)
    res = [json.loads(x) for x in open(r.results_path)]
    failed = [x for x in res if x["custom_id"].endswith("-r2")]
    assert len(failed) == 3 and all(x["status"] == "errored" for x in failed)


SAMPLING_KEYS = {"temperature", "top_p", "top_k", "topP", "topK", "presence_penalty", "frequency_penalty"}


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def test_no_sampling_parameters_in_any_request():
    """Pre-registration: temperature/top_p/top_k are never sent; provider defaults apply."""
    from petri_v2 import judges as J
    for label, j in J.JUDGES.items():
        if not (j.served and j.runner):
            continue
        job = jobs.build_jobs(synthetic_inputs(1), [label], [1])[0]
        assert not SAMPLING_KEYS & set(_keys(jobs.batch_line(job))), label
        assert j.sampling and j.reasoning
