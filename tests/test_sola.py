"""SOLA 모듈 단위 테스트 (LLM 호출은 모킹)."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from sola import chat_ctx, propose, summarize


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


def test_chat_ctx_build_includes_news_and_roadmap():
    news = pd.DataFrame([
        {"title": "용접 자동화", "press": "AITimes"},
    ])
    roadmap = pd.DataFrame([
        {"dept": "가공부", "lv3": "전처리"},
        {"dept": "가공부", "lv3": "가공"},
        {"dept": "조립부", "lv3": "가공"},
    ])
    block = chat_ctx.build_context_block(news, roadmap)
    assert "오늘 뉴스 헤드라인" in block
    assert "용접 자동화" in block
    assert "로드맵 요약" in block
    assert "가공부" in block


def test_chat_ctx_empty_returns_empty_string():
    assert chat_ctx.build_context_block(pd.DataFrame(), pd.DataFrame()) == ""


def test_chat_ctx_includes_proposal_first_when_provided():
    news = pd.DataFrame([{"title": "용접 자동화", "press": "AITimes"}])
    proposal_md = "## 1. 작업 개요\n- 강재선별 자동화"
    block = chat_ctx.build_context_block(news, pd.DataFrame(), proposal=proposal_md)
    assert "첨부 제안서" in block
    assert "강재선별 자동화" in block
    # 제안서가 뉴스보다 먼저 등장해야 한다.
    assert block.index("첨부 제안서") < block.index("오늘 뉴스 헤드라인")


def test_chat_ctx_proposal_only_works_without_news_roadmap():
    block = chat_ctx.build_context_block(
        pd.DataFrame(), pd.DataFrame(), proposal="제안서 본문",
    )
    assert "첨부 제안서" in block
    assert "제안서 본문" in block


def test_chat_ctx_proposal_none_or_empty_ignored():
    news = pd.DataFrame([{"title": "용접", "press": "X"}])
    assert "첨부 제안서" not in chat_ctx.build_context_block(news, pd.DataFrame())
    assert "첨부 제안서" not in chat_ctx.build_context_block(
        news, pd.DataFrame(), proposal="",
    )
    assert "첨부 제안서" not in chat_ctx.build_context_block(
        news, pd.DataFrame(), proposal=None,
    )


def test_chat_ctx_includes_adopted_proposals_with_title_and_note():
    from store.bookmarks import Bookmark

    adopted = [
        Bookmark(
            id="a", type="proposal", title="용접 자동화 도입",
            status="adopted", decided_at="2026-05-10T00:00:00+00:00",
            decision_note="3분기 PoC 승인",
        ),
        Bookmark(
            id="b", type="proposal", title="디지털 트윈 확장",
            status="adopted", decided_at="2026-05-08T00:00:00+00:00",
        ),
    ]
    block = chat_ctx.build_context_block(
        pd.DataFrame(), pd.DataFrame(), adopted_proposals=adopted,
    )
    assert "이전 사이클에서 채택된 제안서" in block
    assert "용접 자동화 도입" in block
    assert "2026-05-10" in block
    assert "3분기 PoC 승인" in block
    assert "디지털 트윈 확장" in block
    # 본문 content 는 노출 X (decision_note 만)


def test_chat_ctx_adopted_proposals_after_attached_proposal_before_news():
    """배치 순서: 첨부 제안서 → 채택 제안서 → 오늘 뉴스."""
    from store.bookmarks import Bookmark

    news = pd.DataFrame([{"title": "용접 로봇 신기술", "press": "AITimes"}])
    block = chat_ctx.build_context_block(
        news, pd.DataFrame(),
        proposal="현재 제안서 본문",
        adopted_proposals=[Bookmark(id="x", type="proposal", title="과거 채택", status="adopted")],
    )
    i_prop = block.index("첨부 제안서")
    i_adopt = block.index("이전 사이클에서 채택된 제안서")
    i_news = block.index("오늘 뉴스 헤드라인")
    assert i_prop < i_adopt < i_news


def test_chat_ctx_empty_or_none_adopted_ignored():
    news = pd.DataFrame([{"title": "용접", "press": "X"}])
    assert "이전 사이클" not in chat_ctx.build_context_block(news, pd.DataFrame())
    assert "이전 사이클" not in chat_ctx.build_context_block(
        news, pd.DataFrame(), adopted_proposals=[],
    )
    assert "이전 사이클" not in chat_ctx.build_context_block(
        news, pd.DataFrame(), adopted_proposals=None,
    )
