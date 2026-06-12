"""각 v2 화면의 chat_context_block — '보이는 모든 것' 이 텍스트로 packaging 되는지.

각 화면이 자기가 보여주는 데이터를 LLM 컨텍스트로 정확히 변환하는지 검증.
사용자가 화면 보다가 SOLA 에게 무엇이든 물어보면 LLM 이 답할 수 있어야 함.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from persona.schema import Persona


# ── 보드 ────────────────────────────────────────────────────

def test_board_chat_context_includes_screen_marker_and_kpis():
    from ui import board_v2

    with patch.object(board_v2, "_board_kpis",
                      return_value={"collect": 125, "match": 18, "opp": 4, "pending": 3}):
        ctx = board_v2.chat_context_block(Persona())

    assert "현재 화면: 오늘의 보드" in ctx
    assert "125" in ctx and "18" in ctx and "4" in ctx and "3" in ctx


def test_board_chat_context_includes_brief_items_from_session():
    from ui import board_v2
    import streamlit as st

    st.session_state["_board_brief_items"] = [
        {"title": "도장 비전 PoC 38% 절감", "source": "AI Times", "when": ""},
        {"title": "VOC 예측 트윈", "source": "Google RSS", "when": ""},
    ]
    try:
        with patch.object(board_v2, "_board_kpis", return_value={"collect": 0, "match": 0, "opp": 0, "pending": 0}):
            ctx = board_v2.chat_context_block(Persona())
        assert "도장 비전 PoC" in ctx
        assert "VOC 예측 트윈" in ctx
        assert "AI Times" in ctx
    finally:
        st.session_state.pop("_board_brief_items", None)


def test_board_chat_context_includes_opportunities_and_matrix_top():
    from ui import board_v2

    cells = pd.DataFrame([
        {"dept": "도장", "lv3": "비전 검사", "cell_score": 95.0,
         "matched_news": 40, "matched_tasks": 18, "sample_tasks": "AI 도막 검사", "sample_news": ""},
        {"dept": "용접", "lv3": "비드 검사", "cell_score": 70.0,
         "matched_news": 28, "matched_tasks": 12, "sample_tasks": "", "sample_news": ""},
    ])
    fake_news = pd.DataFrame([{"title": "x", "source": "y", "collected_at": "2026-05-29T00:00:00+00:00"}])
    fake_roadmap = pd.DataFrame([{"a": 1}])
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=fake_news), \
         patch.object(board_v2, "_load_tasks", return_value=fake_roadmap), \
         patch.object(board_v2, "_score_cells", return_value=cells), \
         patch.object(board_v2, "_board_kpis", return_value={"collect": 0, "match": 0, "opp": 0, "pending": 0}):
        ctx = board_v2.chat_context_block(Persona())

    assert "자동화 제안 top 4" in ctx
    assert "도장 · 비전 검사" in ctx
    assert "점수 95" in ctx
    assert "AI 도막 검사" in ctx
    assert "매트릭스 1위" in ctx


def test_board_chat_context_includes_trend_keywords():
    from ui import board_v2

    with patch.object(board_v2, "_weekly_keyword_series",
                      return_value=(["W1","W2","W3","W4","W5","W6","W7","금주"],
                                    [{"name": "비전 검사", "counts": [5,8,12,18,25,30,38,40]},
                                     {"name": "협동 로봇", "counts": [3,3,5,7,10,12,12,12]}])), \
         patch.object(board_v2, "_board_kpis", return_value={"collect": 0, "match": 0, "opp": 0, "pending": 0}):
        ctx = board_v2.chat_context_block(Persona())
    assert "트렌드" in ctx
    assert "비전 검사" in ctx
    assert "협동 로봇" in ctx
    assert "변화율" in ctx


def test_board_chat_context_includes_persona_user_keywords():
    from ui import board_v2

    p = Persona(interest_lv3=["비전 검사", "협동 로봇"], interest_tasks=["막두께 측정"])
    with patch.object(board_v2, "_board_kpis", return_value={"collect": 0, "match": 0, "opp": 0, "pending": 0}):
        ctx = board_v2.chat_context_block(p)
    assert "내가 추가한 키워드" in ctx
    assert "비전 검사" in ctx
    assert "막두께 측정" in ctx


def test_board_chat_context_empty_state_does_not_crash():
    from ui import board_v2

    with patch.object(board_v2._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(board_v2, "_load_tasks", return_value=pd.DataFrame()), \
         patch.object(board_v2, "_weekly_keyword_series", return_value=([], [])):
        ctx = board_v2.chat_context_block(Persona())
    assert "현재 화면: 오늘의 보드" in ctx
    # 데이터 없어도 헤더는 나옴
    assert len(ctx) > 20


# ── 데이터 관리 ──────────────────────────────────────────────

def test_data_mgmt_chat_context_includes_screen_marker_and_stats():
    from ui import data_management_v2

    data_management_v2._chat_context_collect_cached.clear()  # 60s 캐시 — 테스트 격리
    with patch.object(data_management_v2, "_dm_stats", return_value={
        "active_sources": "4", "today_count": "125", "total_chunks": "8.4k", "last_update": "08:24"}), \
         patch.object(data_management_v2._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(data_management_v2._news_db, "load_all_today", return_value=pd.DataFrame()):
        ctx = data_management_v2.chat_context_block_collect(Persona())
    assert "현재 화면: 뉴스 수집" in ctx
    assert "활성 출처 4개" in ctx
    assert "125" in ctx
    assert "8.4k" in ctx


def test_data_mgmt_chat_context_includes_news_library_and_sources():
    from ui import data_management_v2

    data_management_v2._chat_context_collect_cached.clear()  # 60s 캐시 — 테스트 격리
    news = pd.DataFrame([
        {"title": "현대重 AI 비전 PoC", "source": "AI Times",
         "collected_at": "2026-05-29T08:00:00+00:00", "summary_llm": "38% 불량률 절감"},
        {"title": "삼성중 협동로봇 도입", "source": "Google RSS",
         "collected_at": "2026-05-29T07:00:00+00:00", "summary_llm": ""},
    ])
    with patch.object(data_management_v2, "_dm_stats", return_value={
        "active_sources": "—", "today_count": "—", "total_chunks": "—", "last_update": "—"}), \
         patch.object(data_management_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(data_management_v2._news_db, "load_all_today", return_value=news):
        ctx = data_management_v2.chat_context_block_collect(Persona())
    assert "뉴스 라이브러리" in ctx
    assert "현대重 AI 비전 PoC" in ctx
    assert "38% 불량률 절감" in ctx
    assert "출처별" in ctx
    assert "AI Times" in ctx


def test_data_mgmt_chat_context_includes_live_cardview_filter_and_cards():
    """사용자가 보고 있는 카드뷰 필터(대분류·출처칩·검색어)와 그 카드들이 컨텍스트에 포함."""
    from ui import data_management_v2 as dm
    import streamlit as st

    dm._chat_context_collect_cached.clear()
    dm._sc_browse_records.clear()
    browse = pd.DataFrame([
        {"title": "네이버 용접 로봇 기사", "source": "naver", "press": "",
         "summary": "용접 자동화 본문", "link": "n1",
         "collected_at": "2026-05-29T08:00:00+00:00"},
        {"title": "AI Times 비전 검사", "source": "tech", "press": "AI Times",
         "summary": "비전 검사 본문", "link": "t1",
         "collected_at": "2026-05-29T07:00:00+00:00"},
    ])
    # 사용자가 '키워드 뉴스 > 네이버 뉴스' 탭을 보고 있는 상태
    st.session_state["sc_browse_mode"] = "cards"
    st.session_state["sc_news_cat"] = "keyword"
    st.session_state["sc_chan_keyword"] = "네이버 뉴스"
    st.session_state[dm._NEWS_SEARCH_KEY] = ""
    try:
        with patch.object(dm, "_dm_stats", return_value={
            "active_sources": "—", "today_count": "—", "total_chunks": "—", "last_update": "—"}), \
             patch.object(dm._news_db, "load_news_for_days", return_value=browse), \
             patch.object(dm._news_db, "load_all_today", return_value=browse):
            ctx = dm.chat_context_block_collect(Persona())
    finally:
        for k in ("sc_browse_mode", "sc_news_cat", "sc_chan_keyword", dm._NEWS_SEARCH_KEY):
            st.session_state.pop(k, None)
    assert "지금 화면에 보이는 뉴스" in ctx
    # live 섹션만 분리 — 필터 무관 '뉴스 라이브러리'(최근 6건)와 섞이지 않게 검증
    live = ctx.split("--- 지금 화면에 보이는 뉴스(현재 필터) ---", 1)[1]
    assert "네이버 뉴스" in live             # 선택된 출처칩
    assert "네이버 용접 로봇 기사" in live    # 그 필터로 보이는 카드
    assert "AI Times 비전 검사" not in live   # 포탈 카드는 키워드 탭에서 제외


# ── 인사이트 분석 ────────────────────────────────────────────

def test_insights_chat_context_includes_screen_marker_and_top_keywords():
    from ui import insights_v2

    top = pd.DataFrame([
        {"keyword": "비전 검사", "count": 152},
        {"keyword": "협동 로봇", "count": 88},
    ])
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=pd.DataFrame([{"x": 1}])), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame()), \
         patch.object(insights_v2._trends, "top_keywords", return_value=top), \
         patch.object(insights_v2._trends, "keyword_emergence",
                      return_value={"new": pd.DataFrame(columns=["keyword"])}):
        ctx = insights_v2.chat_context_block(Persona())
    assert "현재 화면: 인사이트 분석" in ctx
    assert "비전 검사" in ctx
    assert "152" in ctx


def test_insights_chat_context_includes_matrix_cells():
    from ui import insights_v2

    cells = pd.DataFrame([
        {"dept": "도장", "lv3": "비전 검사", "cell_score": 95.0,
         "matched_news": 40, "matched_tasks": 18, "sample_tasks": "", "sample_news": "현대重 PoC 사례"},
    ])
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=pd.DataFrame([{"x": 1}])), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame([{"y": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells), \
         patch.object(insights_v2._trends, "top_keywords", return_value=pd.DataFrame(columns=["keyword","count"])), \
         patch.object(insights_v2._trends, "keyword_emergence",
                      return_value={"new": pd.DataFrame(columns=["keyword"])}):
        ctx = insights_v2.chat_context_block(Persona())
    assert "기회 매트릭스 top" in ctx
    assert "도장 · 비전 검사" in ctx
    assert "현대重 PoC 사례" in ctx


# ── 산출물 보관함 ────────────────────────────────────────────

def test_archive_chat_context_includes_screen_marker_and_counts():
    from ui import archive_v2
    from store.bookmarks import Bookmark

    items = [
        Bookmark(id="a", type="proposal", title="도장 PoC", content="설명1", tags=["AI"],
                 created_at="2026-05-29T00:00:00+00:00", status="adopted"),
        Bookmark(id="b", type="proposal", title="용접 검사", content="설명2", tags=[],
                 created_at="2026-05-28T00:00:00+00:00", status="pending"),
        Bookmark(id="c", type="proposal", title="X 제안", content="기각 사유", tags=[],
                 created_at="2026-05-27T00:00:00+00:00", status="rejected"),
    ]
    with patch.object(archive_v2.bookmarks_store, "list_all", return_value=items):
        ctx = archive_v2.chat_context_block(Persona())
    assert "현재 화면: 산출물 보관함" in ctx
    assert "총 3건" in ctx
    assert "채택 1건" in ctx
    assert "대기 1건" in ctx
    assert "기각 1건" in ctx
    # 칸반 카드 각 컬럼이 노출
    assert "도장 PoC" in ctx
    assert "용접 검사" in ctx
    assert "X 제안" in ctx
    # 본문 발췌
    assert "설명1" in ctx or "기각 사유" in ctx


# ── 페르소나 설정 화면 ───────────────────────────────────────

def test_persona_page_chat_context_shows_filled_and_empty_fields():
    from ui import persona_page

    full = Persona(name="홍길동", dept="도장1팀", team="자동화1팀", job="검사관",
                   interest_lv3=["비전 검사", "협동 로봇"])
    ctx = persona_page.chat_context_block(full)
    assert "현재 화면: 페르소나 / 프로필 편집" in ctx
    assert "홍길동" in ctx
    assert "도장1팀" in ctx
    assert "비전 검사" in ctx
    assert "비어있는 필드: (없음)" in ctx

    empty = Persona()
    ctx2 = persona_page.chat_context_block(empty)
    assert "채워진 필드: (없음)" in ctx2
    assert "관심 공정: 미설정" in ctx2
    # 빈 필드 4개 (이름/팀/부서/직무)
    for label in ("이름", "팀", "부서", "직무"):
        assert label in ctx2


def test_persona_page_chat_context_includes_interest_tasks_when_set():
    from ui import persona_page
    p = Persona(dept="도장", interest_tasks=["막두께 측정", "부스 환기"])
    ctx = persona_page.chat_context_block(p)
    assert "관심 작업: 막두께 측정, 부스 환기" in ctx
