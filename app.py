"""제조기술 로드맵 인사이트보드 — 업무 흐름형 Streamlit 진입점.

UX_REDESIGN_PLAN Phase 1: 3영역(홈/탐색/작업실)을 아래 5개 업무 메뉴로
재구성한다.
  1. 오늘의 보드      — 매일 확인하는 맞춤 인사이트
  2. 데이터 관리      — 뉴스 수집·Enrich + 로드맵 업로드
  3. 인사이트 분석    — 트렌드·매칭·자동화 기회
  4. SOLA 작업실      — 요약·과제·제안서 초안
  5. 산출물 보관함    — 뉴스 콘텐츠·북마크
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

if area == "📊 오늘의 보드":
    home_tab.render()
elif area == "🧱 데이터 관리":
    tab_collect, tab_roadmap = st.tabs(["1. 뉴스 수집·Enrich", "2. 로드맵 업로드"])
    with tab_collect:
        ingest_tab.render()
    with tab_roadmap:
        roadmap_tab.render()
elif area == "🔎 인사이트 분석":
    board_tab.render()
elif area == "🤖 SOLA 작업실":
    tab_sola, tab_wb = st.tabs(["SOLA 작업", "제안서 작업장"])
    with tab_sola:
        sola_tab.render()
    with tab_wb:
        proposal_workbench.render()
else:
    tab_bm, tab_news = st.tabs(["📌 북마크·채택", "뉴스 콘텐츠"])
    with tab_bm:
        bookmarks_tab.render()
    with tab_news:
        news_tab.render()
