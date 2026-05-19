from __future__ import annotations

from ui import sola_tab


def test_workspace_cards_html_shows_work_types_and_counts():
    html = sola_tab._workspace_cards_html(
        news_count=12,
        roadmap_count=5,
        proposal_count=2,
        ready=True,
    )

    assert html.startswith('<div class="action-grid">')
    assert "뉴스 요약" in html
    assert "자동화 과제 제안서" in html
    assert "저장된 제안서 2건" in html
    assert html.count('<div class="action-card ') == 4


def test_workspace_readiness_html_warns_missing_items():
    html = sola_tab._workspace_readiness_html(ready=False, news_count=0, roadmap_count=3)

    assert "SOLA 실행 전 준비가 필요합니다" in html
    assert "뉴스 수집" in html
    assert "LLM 설정" in html
    assert "로드맵 업로드" not in html


def test_workspace_readiness_html_ok_when_ready():
    html = sola_tab._workspace_readiness_html(ready=True, news_count=3, roadmap_count=2)

    assert "SOLA 산출물 생성 준비 완료" in html
    assert 'class="status-card ok"' in html


def test_bookmark_workbench_state_routes_to_workbench():
    from ui import bookmarks_tab

    state = bookmarks_tab._workbench_state_for_bookmark("abc")

    assert state == {
        "app_area": "🤖 SOLA 작업실",
        "pw_select": "bm:abc",
        "pw_active_source": "",
        "pw_mode": "✏️ 수정",
    }


def test_build_page_context_summarizes_mode_and_counts():
    """SOLA 사이드 채팅에 주입되는 page_context 가 현재 모드/카운트/페르소나를 압축한다."""
    import pandas as pd
    from persona.schema import Persona
    import streamlit as st

    # 모드/필터/세션 결과를 정해놓고 호출
    st.session_state["sola_mode"] = "자동화 과제 제안서"
    st.session_state["prop_dept"] = "생산기술"
    st.session_state["prop_lv3"] = "용접"
    st.session_state["sola_prop_result"] = "## 제안서 본문\n…"

    ctx = sola_tab._build_page_context(
        news=pd.DataFrame([{"title": "n"}] * 5),
        roadmap=pd.DataFrame([{"dept": "x"}] * 3),
        persona=Persona(dept="생산기술", job="자동화 엔지니어"),
    )

    assert "SOLA 작업실" in ctx
    assert "현재 모드: 자동화 과제 제안서" in ctx
    assert "생산기술" in ctx
    assert "자동화 엔지니어" in ctx
    assert "오늘 뉴스: 5" in ctx
    assert "로드맵 작업: 3" in ctx
    assert "용접" in ctx
    assert "자동화 과제 제안서(세션 보유)" in ctx

    # cleanup
    for k in ("sola_mode", "prop_dept", "prop_lv3", "sola_prop_result"):
        st.session_state.pop(k, None)


def test_sola_tab_no_longer_exposes_main_chat_helpers():
    """채팅 UI 단일화 후 main-area 채팅 헬퍼들이 sola_tab 에서 제거되었는지 확인."""
    assert not hasattr(sola_tab, "_render_chat")
    assert not hasattr(sola_tab, "_build_proposal_context")
