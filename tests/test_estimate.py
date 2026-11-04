import pytest

from petri_v2 import estimate, jobs, judges
from test_runners import synthetic_inputs


def test_prices_cover_every_served_judge_and_name_sources():
    prices = estimate.load_prices()
    assert prices["checked"] == "2026-10-09"
    for label, j in judges.JUDGES.items():
        row = prices["models"][j.model]
        assert row["sources"] and all(s.startswith("https://") for s in row["sources"])
        assert row.get("checked", prices["checked"]) in ("2026-10-09", "2026-10-10")
        if j.served:
            assert "standard" in row or "tiers" in row
        else:
            assert row.get("retired") is True


def test_cost_arithmetic(monkeypatch):
    monkeypatch.setattr(estimate, "approx_tokens", lambda s: 500)
    job_list = jobs.build_jobs(synthetic_inputs(2), ["opus45"], [1, 2])
    res = estimate.estimate(job_list, estimate.load_prices())
    a = res["per_judge"]["opus45"]
    tin = 500 + 500 + estimate.MESSAGE_OVERHEAD
    assert a["requests"] == 4 and a["input_tokens"] == 4 * tin
    assert a["usd"]["batch_high"] == pytest.approx(4 * (tin * 2.5 + 10000 * 12.5) / 1e6)
    assert a["usd"]["standard_low"] == pytest.approx(4 * (tin * 5 + 4000 * 25) / 1e6)
    assert a["usd"]["batch_cap"] == pytest.approx(4 * (tin * 2.5 + 32000 * 12.5) / 1e6)
    assert a["token_method"].startswith("approximation")


def test_gemini_tier_selection():
    prices = estimate.load_prices()
    assert estimate.price_row(prices, "gemini-3.1-pro-preview", 7000)["batch"]["input"] == 1.00
    assert estimate.price_row(prices, "gemini-3.1-pro-preview", 250000)["batch"]["input"] == 2.00


def test_retired_judge_rejected_by_cli():
    with pytest.raises(SystemExit, match="not served"):
        estimate.main(["--panel", "gemini3pro", "--n", "1"])


def test_offline_fallback_is_labelled(monkeypatch):
    import sys
    monkeypatch.setattr(estimate, "_ENC", None)
    monkeypatch.setitem(sys.modules, "tiktoken", None)  # import fails
    monkeypatch.setattr(estimate, "TOKENIZER_LABEL", estimate.TOKENIZER_LABEL)
    assert estimate.approx_tokens("abcdefgh") == 2
    assert "characters / 4" in estimate.TOKENIZER_LABEL


def test_design_request_counts():
    """Exact request counts of the design options: sum over legs of judges x transcripts x repeats."""
    count = lambda d: sum(len(p) * (b - a) * len(r) for p, a, b, r in estimate.DESIGNS[d]["legs"])  # noqa: E731
    assert count("A_J3") == 1560
    assert count("B_J6") == 1560 + 3 * 140 * 2 == 2400
    assert count("C_J8") == 1560 + 5 * 140 * 2 == 2960
    assert count("C_J8_lite") == 1560 + 5 * (70 * 2 + 70) == 2610
    assert len(judges.PANEL_J6) == 6 and len(judges.PANEL_J8) == 8
    for panel in (judges.PANEL_J6, judges.PANEL_J8):
        assert len({judges.get(j).developer for j in panel}) >= 4
        assert panel[:3] == judges.DEFAULT_PANEL


def test_opus_leg_first_in_every_design():
    for d in ("A_J3", "B_J6", "C_J8", "C_J8_lite"):
        first = estimate.DESIGNS[d]["legs"][0]
        assert "opus45" in first[0] and (first[1], first[2]) == (120, 260)


def test_tokenizer_multiplier_and_derived_flags(monkeypatch):
    monkeypatch.setattr(estimate, "approx_tokens", lambda s: 500)
    prices = estimate.load_prices()
    res = estimate.estimate(jobs.build_jobs(synthetic_inputs(1), ["sonnet55", "opus45"], [1]), prices)
    tin = 500 + 500 + estimate.MESSAGE_OVERHEAD
    assert res["per_judge"]["sonnet55"]["input_tokens"] == round(tin * 1.3)
    assert res["per_judge"]["opus45"]["input_tokens"] == tin
    assert prices["models"][judges.get("qwen38max").model]["derived"] is True
    assert prices["models"][judges.get("kimik26").model].get("derived") is None
