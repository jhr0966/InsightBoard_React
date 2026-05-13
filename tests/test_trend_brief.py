"""sola/trend_brief.brief() — LLM 호출 + 캐시 + graceful fallback."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from sola import trend_brief
from sola.client import LLMNotConfigured


def _sample_payload(rising_kw: str = "용접 자동화"):
    vol = pd.DataFrame([
        {"date": "2026-05-11", "count": 3},
        {"date": "2026-05-12", "count": 5},
        {"date": "2026-05-13", "count": 8},
    ])
    emergence = {
        "new": pd.DataFrame([{"keyword": "디지털트윈", "count": 2}]),
        "gone": pd.DataFrame([{"keyword": "구식기술", "count": 1}]),
        "rising": pd.DataFrame([
            {"keyword": rising_kw, "today": 4, "base": 1, "delta": 3},
        ]),
    }
    return vol, emergence


def test_brief_calls_llm_with_period_and_emergence():
    vol, emergence = _sample_payload()
    captured: dict = {}

    def _fake_chat(messages, **kw):
        captured["messages"] = messages
        captured["kw"] = kw
        return "최근 일주일 **용접 자동화** 가 두드러집니다."

    with patch.object(trend_brief, "chat", _fake_chat):
        out = trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence)

    user = captured["messages"][-1]["content"]
    assert "최근 7일" in user
    assert "2026-05-13=8" in user        # 일자별 기사 수 포맷
    assert "디지털트윈" in user           # new
    assert "용접 자동화" in user          # rising
    assert "구식기술" in user             # gone
    assert "용접 자동화" in out
    # 시스템 프롬프트 자리 확인
    assert captured["messages"][0]["role"] == "system"
    # 토큰·온도 가벼움
    assert captured["kw"].get("temperature") == 0.2


def test_brief_caches_repeat_calls():
    vol, emergence = _sample_payload()
    calls: list = []

    def _fake_chat(messages, **kw):
        calls.append(1)
        return "동일 입력 한 줄 해석."

    with patch.object(trend_brief, "chat", _fake_chat):
        a = trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence)
        b = trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence)
    assert a == b
    # 두 번째는 캐시 hit → LLM 1회만 호출
    assert len(calls) == 1


def test_brief_force_bypasses_cache():
    vol, emergence = _sample_payload()
    calls: list = []

    def _fake_chat(messages, **kw):
        calls.append(1)
        return f"call#{len(calls)}"

    with patch.object(trend_brief, "chat", _fake_chat):
        a = trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence)
        b = trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence, force=True)
    assert a != b
    assert len(calls) == 2


def test_brief_falls_back_when_llm_not_configured():
    vol, emergence = _sample_payload()

    def _raise(*a, **kw):
        raise LLMNotConfigured("no key")

    with patch.object(trend_brief, "chat", _raise):
        out = trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence)
    # 룰 기반 fallback — 총합 + 새 키워드 + 상승 키워드 포함
    assert "16건" in out or "16,건" in out or "16" in out  # 총합 3+5+8=16
    assert "디지털트윈" in out
    assert "용접 자동화" in out


def test_brief_falls_back_when_chat_raises_generic_error():
    vol, emergence = _sample_payload()

    def _raise(*a, **kw):
        raise RuntimeError("boom")

    with patch.object(trend_brief, "chat", _raise):
        out = trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence)
    assert "16" in out  # fallback 했다


def test_brief_fallback_with_no_changes_says_no_significant_change():
    vol = pd.DataFrame([{"date": "2026-05-13", "count": 0}])
    emergence = {
        "new": pd.DataFrame(columns=["keyword", "count"]),
        "gone": pd.DataFrame(columns=["keyword", "count"]),
        "rising": pd.DataFrame(columns=["keyword", "today", "base", "delta"]),
    }
    with patch.object(trend_brief, "chat", lambda *a, **kw: (_ for _ in ()).throw(LLMNotConfigured("none"))):
        out = trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence)
    assert "유의미한 키워드 변화" in out


def test_brief_cache_distinguishes_different_periods():
    vol, emergence = _sample_payload()
    calls: list = []

    def _fake_chat(messages, **kw):
        calls.append(1)
        return f"call#{len(calls)}"

    with patch.object(trend_brief, "chat", _fake_chat):
        trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence)
        trend_brief.brief(period_label="최근 30일", vol_df=vol, emergence=emergence)
    # 두 period 는 별도 캐시 키
    assert len(calls) == 2


def test_brief_cache_distinguishes_different_keywords():
    vol, emergence_a = _sample_payload(rising_kw="용접 자동화")
    _, emergence_b = _sample_payload(rising_kw="레이저 절단")
    calls: list = []

    def _fake_chat(messages, **kw):
        calls.append(1)
        return f"call#{len(calls)}"

    with patch.object(trend_brief, "chat", _fake_chat):
        trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence_a)
        trend_brief.brief(period_label="최근 7일", vol_df=vol, emergence=emergence_b)
    # 키워드가 다르면 별도 캐시
    assert len(calls) == 2
