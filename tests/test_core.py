"""Unit tests that run offline: the Gemini call is replaced with a stub."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm  # noqa: E402
from risk import MAX_SCORE, score_flags  # noqa: E402


def stub(monkeypatch, payload):
    """Make every LLM call return `payload` (dict -> JSON string)."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(llm, "_generate", lambda *a, **k: text)


def test_headlines_aligned_by_index_even_if_model_reorders_or_drops(monkeypatch):
    stub(monkeypatch, {"results": [
        {"index": 1, "sentiment": "negative", "reasoning": "cuts"},
        {"index": 0, "sentiment": "POSITIVE", "reasoning": "beat"},
    ]})
    rows = llm.classify_headlines(["beat", "cuts", "missing"], ["A", "B", "C"])
    assert [r["sentiment"] for r in rows] == ["Positive", "Negative", "Unclassified"]
    assert [r["ticker"] for r in rows] == ["A", "B", "C"]


def test_code_fences_are_stripped(monkeypatch):
    stub(monkeypatch, '```json\n{"results": [{"index": 0, "flag": true, "category": "fraud"}]}\n```')
    rows = llm.screen_adverse_media(["x"])
    assert rows[0]["flag"] is True and rows[0]["category"] == "fraud"


def test_invalid_json_raises_llm_error(monkeypatch):
    stub(monkeypatch, "not json at all")
    with pytest.raises(llm.LLMError):
        llm.screen_adverse_media(["x"])


def test_earnings_fields_are_normalised(monkeypatch):
    stub(monkeypatch, {"company": "Clearbrook", "eps": 0.92, "highlights": "one", "guidance": {"nii": "4.8bn"}})
    s = llm.summarise_earnings("transcript")
    assert s["eps"] == "0.92" and s["highlights"] == ["one"] and s["revenue"] == "Not stated"
    assert isinstance(s["guidance"], str)


def test_batch_limit(monkeypatch):
    stub(monkeypatch, {"results": []})
    with pytest.raises(llm.LLMError):
        llm.classify_headlines(["h"] * (llm.MAX_BATCH + 1))


def test_transient_errors_are_retried(monkeypatch):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return '{"results": []}'

    monkeypatch.setattr(llm, "_generate", flaky)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.screen_adverse_media(["x"])[0]["category"] == "not returned"
    assert calls["n"] == 3


def test_non_transient_error_not_retried(monkeypatch):
    calls = {"n": 0}

    def bad(*a, **k):
        calls["n"] += 1
        raise RuntimeError("400 INVALID_ARGUMENT")

    monkeypatch.setattr(llm, "_generate", bad)
    with pytest.raises(llm.LLMError):
        llm.ask_llm("p", "s")
    assert calls["n"] == 1


def test_rating_is_validated(monkeypatch):
    stub(monkeypatch, {"risk_rating": "extreme", "narrative": "n"})
    assert llm.assess_red_flags([], "", {})["risk_rating"] == "Unrated"


def test_rule_score_bands():
    assert score_flags([])["band"] == "Low"
    assert score_flags(["Opaque or undisclosed beneficial ownership", "Cash-intensive business model"])["band"] == "Medium"
    high = score_flags(["Shell-company indicators", "Opaque or undisclosed beneficial ownership",
                        "Politically exposed person (PEP) involved"])
    assert high["score"] == 8 and high["band"] == "High" and high["max_score"] == MAX_SCORE
    with pytest.raises(ValueError):
        score_flags(["made-up flag"])


def test_provider_is_passed_through_and_unknown_provider_fails(monkeypatch):
    seen = {}

    def capture(*a, **k):
        seen.update(k)
        return '{"results": []}'

    monkeypatch.setattr(llm, "_generate", capture)
    llm.screen_adverse_media(["x"], provider="claude", model="m")
    assert seen["provider"] == "claude"
    monkeypatch.undo()
    with pytest.raises(llm.LLMError):
        llm.ask_llm("p", "s", provider="mistral")


def test_mixed_label_only_when_allowed(monkeypatch):
    stub(monkeypatch, {"results": [{"index": 0, "sentiment": "Mixed"}]})
    assert llm.classify_headlines(["h"])[0]["sentiment"] == "Unclassified"
    assert llm.classify_headlines(["h"], allow_mixed=True)[0]["sentiment"] == "Mixed"


def test_diagnose_maps_lab_troubleshooting():
    assert "Wait a minute" in llm.diagnose("429 RESOURCE_EXHAUSTED")[1]
    assert llm.diagnose("something odd") is None
