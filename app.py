"""제조기술 로드맵 인사이트보드 — 업무 흐름형 Streamlit 진입점.

5개 업무 메뉴 (UX Phase 3 에서 산출물 보관함에 섞여 있던 '뉴스 콘텐츠' 를
데이터 관리 아래로 이동해 IA 단일화):
  1. 오늘의 보드      — 매일 확인하는 맞춤 인사이트
  2. 데이터 관리      — 뉴스 수집 + 뉴스 둘러보기 + 로드맵 업로드
  3. 인사이트 분석    — 트렌드·매칭·자동화 기회 (탭 분할)
  4. SOLA 작업실      — 요약·과제·제안서 초안
  5. 산출물 보관함    — 북마크·채택 의사결정 (단일 페이지)
"""
from __future__ import annotations

import streamlit as st

from config import ensure_data_dirs
from store import bookmarks as _bookmarks_store
from ui import (
    board_tab,
    board_v2,
    bookmarks_tab,
    data_health,  # noqa: F401 — v2 마이그레이션 중, 롤백용 보존.
    data_management_v2,
    home_tab,  # noqa: F401 — v2 마이그레이션 중, 롤백용 보존.
    ingest_tab,  # noqa: F401 — v2 마이그레이션 중, 롤백용 보존.
    news_tab,  # noqa: F401 — v2 마이그레이션 중, 롤백용 보존.
    persona_page,
    proposal_workbench,
    roadmap_tab,  # noqa: F401 — v2 마이그레이션 중, 롤백용 보존.
    sidebar,
    sola_tab,
)
from ui.styles import inject_global_styles


st.set_page_config(
    page_title="제조기술 로드맵 인사이트보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_data_dirs()
inject_global_styles()

# 세션당 1회: 미채택 제안서 만료 정리 (기본 30일, adopted 는 보존).
if not st.session_state.get("_did_expire_check"):
    _bookmarks_store.expire_old()
    st.session_state["_did_expire_check"] = True

with st.sidebar:
    area = sidebar.render()

if st.session_state.get("show_persona_editor"):
    persona_page.render()
elif area == "📊 오늘의 보드":
    board_v2.render()
elif area == "🧱 데이터 관리":
    data_management_v2.render()
elif area == "🔎 인사이트 분석":
    board_tab.render()
elif area == "🤖 SOLA 작업실":
    tab_sola, tab_wb = st.tabs(["SOLA 작업", "제안서 작업장"])
    with tab_sola:
        sola_tab.render()
    with tab_wb:
        proposal_workbench.render()
else:
    bookmarks_tab.render()
