from __future__ import annotations

import streamlit as st


def render_workspace(metrics: dict[str, int]) -> None:
    st.markdown(
        """
        <div class="header-wrap">
            <span class="header-logo">🏠 워크스페이스</span>
            <span class="header-sub">오늘의 수집/분석 현황 요약</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("네이버 기사", f"{metrics['naver_articles']}건")
    col2.metric("기술동향 기사", f"{metrics['tech_articles']}건")
    col3.metric("전체 기사", f"{metrics['total_articles']}건")
    col4.metric("생성된 제안", f"{metrics['proposals']}건")

    st.markdown("---")
    st.info("왼쪽 메뉴에서 수집 → 인사이트 → 제안 순서로 진행하면 최신 데이터가 자동 반영됩니다.")
