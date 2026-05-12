"""제조기술 로드맵 인사이트보드 — Streamlit 평탄 진입점.

다이어그램 5단계:
  1. 데이터 입력  → ui.ingest_tab, ui.roadmap_tab
  2. 저장·정제    → store, roadmap
  3. AI 분석(SOLA) → ui.sola_tab (M2)
  4. 서비스 UI    → ui.news_tab, ui.board_tab
  5. 산출물·활용  → M3 (제안서 export)
"""
from __future__ import annotations

import streamlit as st

from config import ensure_data_dirs
from ui import board_tab, ingest_tab, news_tab, roadmap_tab, sola_tab
from ui.styles import inject_global_styles


st.set_page_config(
    page_title="제조기술 로드맵 인사이트보드",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_data_dirs()
inject_global_styles()

with st.sidebar:
    st.markdown("## 🛠️ 메뉴")
    mode = st.radio(
        "단계",
        (
            "1. 뉴스 수집",
            "2. 로드맵 업로드",
            "3. SOLA (AI 분석)",
            "4. 뉴스 콘텐츠",
            "5. 인사이트보드",
        ),
        key="app_mode",
    )
    st.caption("M1 — 룰 기반 매칭까지 동작. SOLA·LLM UI는 M2/M3.")

if mode.startswith("1"):
    ingest_tab.render()
elif mode.startswith("2"):
    roadmap_tab.render()
elif mode.startswith("3"):
    sola_tab.render()
elif mode.startswith("4"):
    news_tab.render()
else:
    board_tab.render()
