"""SOLA 모듈 단위 테스트 (LLM 호출은 모킹)."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from sola import propose, summarize


def test_summarize_formats_articles_and_calls_chat():
    df = pd.DataFrame([
        {"title": "용접 자동화 도입", "press": "AITimes", "summary": "조선소 용접 자동화", "link": "x"},
        {"title": "디지털 트윈 확대", "press": "매일경제", "summary": "디지털 트윈", "link": "y"},
    ])
    captured: dict = {}

    def _fake_chat(messages, **kw):
        captured["messages"] = messages
        captured["kw"] = kw
        return "## 핵심 흐름\n- 자동화 가속"

    with patch.object(summarize, "chat", _fake_chat):
        out = summarize.summarize_news(df, max_items=10)
    assert "핵심 흐름" in out
    user = captured["messages"][-1]["content"]
    assert "용접 자동화 도입" in user
    assert "AITimes" in user


def test_propose_for_task_includes_task_and_news():
    news = pd.DataFrame([{"title": "용접 로봇 신기술", "press": "AITimes", "summary": "신기술", "link": "z"}])
    task = {
        "team": "가공팀", "dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "전처리",
        "task": "강재선별", "sub_task": "크레인", "task_def": "", "sws_no": "", "sws_name": "강재 하역",
    }
    captured: dict = {}

    def _fake_chat(messages, **kw):
        captured["messages"] = messages
        return "## 1. 작업 개요\n- ok"

    with patch.object(propose, "chat", _fake_chat):
        out = propose.propose_for_task(task, news)
    assert "작업 개요" in out
    user = captured["messages"][-1]["content"]
    assert "강재선별" in user
    assert "용접 로봇 신기술" in user


def test_propose_for_task_injects_persona_when_provided():
    from persona.schema import Persona

    news = pd.DataFrame([{"title": "용접 로봇", "press": "X", "summary": "", "link": "z"}])
    task = {"dept": "가공부", "task": "강재선별"}
    persona = Persona(dept="가공부", job="용접 담당")
    captured: dict = {}

    def _fake_chat(messages, **kw):
        captured["messages"] = messages
        return "## 1. 작업 개요"

    with patch.object(propose, "chat", _fake_chat):
        propose.propose_for_task(task, news, persona=persona)

    system_msg = captured["messages"][0]["content"]
    assert "사용자 페르소나" in system_msg
    assert "용접 담당" in system_msg
