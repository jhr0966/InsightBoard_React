"""제조기술 로드맵 인사이트보드 — Streamlit 평탄 진입점 (3영역 재편).

영역:
  🏠 홈   — 페르소나 기반 오늘의 인사이트 (ui.home_tab)
  🔍 탐색 — 뉴스 수집 / 로드맵 / 인사이트보드 (sub-tabs)
  💼 작업실 — SOLA 채팅·요약·제안서 / 뉴스 콘텐츠 (sub-tabs)
"""
from __future__ import annotations

import streamlit as st

from config import ensure_data_dirs
from store import bookmarks as _bookmarks_store
from ui import (
    board_tab,
    bookmarks_tab,
    home_tab,
    ingest_tab,
    news_tab,
    proposal_workbench,
    roadmap_tab,
    sidebar,
    sola_tab,
)
from ui.styles import inject_global_styles


st.set_page_config(
    page_title="제조기술 로드맵 인사이트보드",
    page_icon="📰",
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

if area.startswith("🏠"):
    home_tab.render()
elif area.startswith("🔍"):
    tab_collect, tab_roadmap, tab_board = st.tabs(
        ["뉴스 수집·Enrich", "로드맵 업로드", "인사이트보드"]
    )
    with tab_collect:
        ingest_tab.render()
    with tab_roadmap:
        roadmap_tab.render()
    with tab_board:
        board_tab.render()
else:
    tab_sola, tab_wb, tab_news, tab_bm = st.tabs(
        ["SOLA (요약·제안서·채팅)", "📝 제안서 작업장", "뉴스 콘텐츠", "📌 북마크"]
    )
    with tab_sola:
        sola_tab.render()
    with tab_wb:
        proposal_workbench.render()
    with tab_news:
        news_tab.render()
    with tab_bm:
        bookmarks_tab.render()
