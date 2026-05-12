"""sola.insight — 부서 인사이트 캐시 동작 검증 (LLM 모킹)."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from sola import insight as insight_mod


def test_insight_for_dept_uses_cache_on_second_call():
    news = pd.DataFrame([
        {"title": "용접 자동화 도입", "press": "AITimes"},
        {"title": "디지털 트윈 확대", "press": "매일경제"},
    ])
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        return "**자동화** 흐름이 가속 중입니다."

    with patch.object(insight_mod, "chat", _fake_chat):
        a = insight_mod.insight_for_dept("가공부", news)
        b = insight_mod.insight_for_dept("가공부", news)
    assert a == b
    assert calls["n"] == 1, "동일 입력에 대해 LLM 호출이 2번 발생함 (캐시 미동작)"


def test_insight_for_dept_force_bypasses_cache():
    news = pd.DataFrame([{"title": "용접 자동화", "press": "X"}])
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        return f"응답 #{calls['n']}"

    with patch.object(insight_mod, "chat", _fake_chat):
        insight_mod.insight_for_dept("조립부", news)
        result = insight_mod.insight_for_dept("조립부", news, force=True)
    assert calls["n"] == 2
    assert result == "응답 #2"


def test_insight_for_dept_distinct_dept_distinct_call():
    news = pd.DataFrame([{"title": "용접", "press": "X"}])
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        return f"dept call #{calls['n']}"

    with patch.object(insight_mod, "chat", _fake_chat):
        insight_mod.insight_for_dept("가공부", news)
        insight_mod.insight_for_dept("조립부", news)
    assert calls["n"] == 2
