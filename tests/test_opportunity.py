"""sola.opportunity — 부서×공정 매트릭스 점수."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from sola import opportunity


def _sample_news():
    return pd.DataFrame([
        {"title": "용접 자동화 로봇 도입", "press": "AI Times",
         "summary": "용접 자동화 로봇", "keywords": "용접, 자동화, 로봇", "link": "x1"},
        {"title": "강재 절단 효율화", "press": "오토메이션월드",
         "summary": "강재 절단 효율", "keywords": "강재, 절단", "link": "x2"},
        {"title": "검사 시스템 비전 AI", "press": "AI Times",
         "summary": "비전 AI 검사", "keywords": "비전 AI, 검사", "link": "x3"},
    ])


def _sample_roadmap():
    return pd.DataFrame([
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "전처리",
         "task": "강재선별", "sub_task": "크레인", "task_def": "", "sws_no": "", "sws_name": "강재 하역"},
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "가공",
         "task": "절단", "sub_task": "강재 절단", "task_def": "", "sws_no": "", "sws_name": "절단 작업"},
        {"dept": "조립부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "형강",
         "task": "용접", "sub_task": "B/up 용접", "task_def": "", "sws_no": "", "sws_name": "용접 작업"},
    ])


def test_score_cells_returns_ranked_dept_lv3_aggregate():
    out = opportunity.score_cells(_sample_news(), _sample_roadmap())
    assert not out.empty
    assert set(out.columns) >= {"dept", "lv3", "cell_score", "avg_score",
                                "matched_news", "matched_tasks",
                                "sample_tasks", "sample_news"}
    # cell_score 내림차순
    scores = out["cell_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_score_cells_empty_for_empty_inputs():
    out = opportunity.score_cells(pd.DataFrame(), _sample_roadmap())
    assert out.empty
    out = opportunity.score_cells(_sample_news(), pd.DataFrame())
    assert out.empty


def test_score_cells_sample_fields_populated():
    out = opportunity.score_cells(_sample_news(), _sample_roadmap())
    for _, row in out.iterrows():
        assert isinstance(row["sample_tasks"], str)
        assert isinstance(row["sample_news"], str)


def test_llm_commentary_uses_cache():
    from store import cache as cache_mod

    cache_mod.clear()
    calls = {"n": 0}

    def _fake_chat(messages, **kw):
        calls["n"] += 1
        return "이 공정은 **비전 AI** 도입이 유망합니다."

    with patch.object(opportunity, "chat", _fake_chat):
        a = opportunity.llm_commentary("가공부", "가공", "절단 효율", "절단; 강재선별")
        b = opportunity.llm_commentary("가공부", "가공", "절단 효율", "절단; 강재선별")
    assert a == b
    assert calls["n"] == 1


def test_llm_commentary_returns_empty_when_not_configured():
    from sola.client import LLMNotConfigured

    def _fake_chat(messages, **kw):
        raise LLMNotConfigured("no key")

    with patch.object(opportunity, "chat", _fake_chat):
        out = opportunity.llm_commentary("부서X", "공정Y", "뉴스", "작업")
    assert out == ""
