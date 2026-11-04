"""DeepSeek synchronous off-peak runner, against a fake server (no network, no keys)."""
import datetime as dt
import glob
import json
import os

import pytest

import fakes
from petri_v2 import jobs, runner_deepseek as rd
from petri_v2.batch import SpendRefused
from test_runners import SECRET, synthetic_inputs

UTC = dt.timezone.utc
OFFPEAK = dt.datetime(2026, 10, 12, 12, 0, tzinfo=UTC)  # Monday 12:00 UTC, next peak Tue 01:00


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += dt.timedelta(seconds=s)


@pytest.fixture
def keys(monkeypatch):
    for k, v in SECRET.items():
        monkeypatch.setenv(k, v)


def make(tmp_path, logs, start=OFFPEAK, **kw):
    t = fakes.FakeTransport()
    server = fakes.DeepSeekServer(t)
    clock = Clock(start)
    r = rd.DeepSeekRunner(str(tmp_path), transport=t, sleep=clock.sleep, log=logs.append, clock=clock,
                          concurrency=kw.pop("concurrency", 1), **kw)
    return r, t, server, clock


def results(r):
    return [json.loads(x) for x in open(r.results_path)]


@pytest.mark.parametrize("t,ok", [
    (dt.datetime(2026, 10, 12, 0, 44, tzinfo=UTC), True),    # Mon 00:44: 16 min before 01:00
    (dt.datetime(2026, 10, 12, 0, 46, tzinfo=UTC), False),   # 14 min before peak: too close
    (dt.datetime(2026, 10, 12, 2, 0, tzinfo=UTC), False),    # inside 01-04
    (dt.datetime(2026, 10, 12, 4, 30, tzinfo=UTC), True),    # gap 04-06, 90 min to peak
    (dt.datetime(2026, 10, 12, 5, 50, tzinfo=UTC), False),
    (dt.datetime(2026, 10, 12, 9, 59, tzinfo=UTC), False),   # inside 06-10
    (dt.datetime(2026, 10, 12, 10, 0, tzinfo=UTC), True),
    (dt.datetime(2026, 10, 17, 2, 0, tzinfo=UTC), True),     # Saturday: all off-peak
    (dt.datetime(2026, 10, 18, 23, 50, tzinfo=UTC), True),   # Sunday 23:50, next peak Mon 01:00
])
def test_offpeak_window(t, ok):
    assert rd.can_start(t) is ok


def test_full_cycle_offpeak_resume_and_retry(tmp_path, keys, capsys):
    logs = []
    r, t, server, _ = make(tmp_path, logs)
    job_list = jobs.build_jobs(synthetic_inputs(4), ["deepseekv4pro"])
    r.run(job_list, budget_usd=100.0, confirm_spend=True)
    res = results(r)
    responded = {x["custom_id"] for x in res if x["status"] == "responded"}
    assert responded == {j["custom_id"] for j in job_list}  # the one 500 was retried within the run
    errs = [x for x in res if x["status"] == "errored"]
    assert len(errs) == 1 and set(errs[0]["parse"]["missing"].values()) == {"no_response"}
    good = [x for x in res if x["status"] == "responded" and x["parse"]["scores"]]
    assert good and "SECRET THOUGHTS" not in good[0]["content"]  # reasoning_content is not judge output
    assert any("refusal_suspect" in x["parse"]["flags"] for x in res if x["status"] == "responded")

    # request shape: thinking on, effort high, Petri's max_tokens, no sampling parameters
    b = server.requests[0]
    assert b["model"] == "deepseek-v4-pro" and b["max_tokens"] == 32000
    assert b["thinking"] == {"type": "enabled"} and b["reasoning_effort"] == "high"
    assert not {"temperature", "top_p", "presence_penalty", "frequency_penalty"} & set(b)
    c = [x for x in t.calls if x["method"] == "POST"][0]
    assert c["url"] == "https://api.deepseek.com/chat/completions"
    assert c["headers"]["Authorization"] == f"Bearer {SECRET['DEEPSEEK_API_KEY']}"

    # resume: nothing left to do, no new calls
    n = len(t.calls)
    assert r.run(job_list, budget_usd=100.0, confirm_spend=True) == []
    assert len(t.calls) == n

    # key never written or printed
    out = capsys.readouterr()
    blob = out.out + out.err + "\n".join(logs)
    for f in glob.glob(os.path.join(str(tmp_path), "**", "*"), recursive=True):
        if os.path.isfile(f):
            blob += open(f, encoding="utf-8").read()
    assert SECRET["DEEPSEEK_API_KEY"] not in blob


def test_waits_through_peak_and_never_calls_inside_it(tmp_path, keys):
    start = dt.datetime(2026, 10, 13, 6, 30, tzinfo=UTC)  # Tuesday, inside 06-10
    r, t, server, clock = make(tmp_path, [], start=start)
    seen = []
    orig = t.request

    def spy(method, url, headers=None, body=None):
        seen.append(clock())
        return orig(method, url, headers, body)
    t.request = spy
    r.run(jobs.build_jobs(synthetic_inputs(2), ["deepseekv4pro"]), budget_usd=100.0, confirm_spend=True)
    assert seen and all(rd.can_start(x) for x in seen)
    assert min(seen) >= dt.datetime(2026, 10, 13, 10, 0, tzinfo=UTC)


def test_no_wait_stops_at_peak(tmp_path, keys):
    r, t, server, _ = make(tmp_path, [], start=dt.datetime(2026, 10, 13, 2, 0, tzinfo=UTC), wait_for_offpeak=False)
    r.run(jobs.build_jobs(synthetic_inputs(2), ["deepseekv4pro"]), budget_usd=100.0, confirm_spend=True)
    assert server.requests == []


def test_abort_on_no_balance_keeps_paid_results(tmp_path, keys):
    r, t, server, _ = make(tmp_path, [])
    job_list = jobs.build_jobs(synthetic_inputs(2), ["deepseekv4pro"])
    server.status_override = 402
    with pytest.raises(SystemExit, match="aborting"):
        r.run(job_list, budget_usd=100.0, confirm_spend=True)
    assert not os.path.exists(r.results_path) or results(r) == []  # no retry budget burned


def test_retries_capped_at_three(tmp_path, keys):
    r, t, server, _ = make(tmp_path, [])
    server.status_override = 503
    job_list = jobs.build_jobs(synthetic_inputs(1), ["deepseekv4pro"], [1])
    r.run(job_list, budget_usd=100.0, confirm_spend=True)
    assert len(results(r)) == 3 and all(x["status"] == "errored" for x in results(r))
    assert r.run(job_list, budget_usd=100.0, confirm_spend=True) == []


def test_spend_gate_and_key(tmp_path, keys, monkeypatch):
    r, t, server, _ = make(tmp_path, [])
    job_list = jobs.build_jobs(synthetic_inputs(2), ["deepseekv4pro"])
    with pytest.raises(SpendRefused, match="confirm-spend"):
        r.run(job_list, budget_usd=100.0, confirm_spend=False)
    with pytest.raises(SpendRefused, match="exceeds"):
        r.run(job_list, budget_usd=0.001, confirm_spend=True)
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    with pytest.raises(SystemExit, match="is not set"):
        r.run(job_list, budget_usd=100.0, confirm_spend=True)
    assert server.requests == []


def test_wrong_provider_and_margin_guard(tmp_path, keys):
    r, t, server, _ = make(tmp_path, [])
    with pytest.raises(SystemExit, match="belongs to moonshot"):
        r.run(jobs.build_jobs(synthetic_inputs(1), ["kimik26"]), budget_usd=100.0, confirm_spend=True)
    with pytest.raises(ValueError, match="margin"):
        rd.DeepSeekRunner(str(tmp_path), margin_s=60)


def test_concurrent_waves_record_every_job(tmp_path, keys):
    r, t, server, _ = make(tmp_path, [], concurrency=4)
    job_list = jobs.build_jobs(synthetic_inputs(6), ["deepseekv4pro"])
    r.run(job_list, budget_usd=100.0, confirm_spend=True)
    done = {x["custom_id"] for x in results(r) if x["status"] == "responded"}
    assert done == {j["custom_id"] for j in job_list}
