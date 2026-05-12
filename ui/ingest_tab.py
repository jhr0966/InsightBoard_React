"""수집 탭: 네이버 뉴스 키워드 검색 → Parquet 저장."""
from __future__ import annotations

import html

import streamlit as st

from scraping.naver import search
from store.news_db import load_latest, save_articles
from ui.styles import page_header


def _run_search() -> None:
    keyword = st.session_state.get("ins_keyword", "").strip()
    max_results = int(st.session_state.get("ins_max_results", 20))
    if not keyword:
        st.session_state["ins_status"] = ("warn", "키워드를 입력하세요.")
        return
    try:
        articles = search(keyword, max_results=max_results)
    except RuntimeError as e:
        st.session_state["ins_status"] = ("error", str(e))
        return
    path = save_articles(articles, source="naver")
    st.session_state["ins_status"] = (
        "ok",
        f"{len(articles)}건 수집·저장 완료 ({path.name if path else '저장 없음'}).",
    )


def render() -> None:
    page_header("뉴스 수집", "네이버 뉴스 → 일자별 Parquet")

    st.text_input("검색 키워드", key="ins_keyword", placeholder="예: 조선소 자동화, 용접 로봇")
    st.slider("수집 건수", min_value=5, max_value=50, value=20, step=5, key="ins_max_results")

    if st.button("검색·저장", type="primary"):
        st.session_state["_do_search"] = True

    if st.session_state.pop("_do_search", False):
        _run_search()
        st.rerun()

    status = st.session_state.get("ins_status")
    if status:
        kind, msg = status
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](msg)

    st.markdown("---")
    df = load_latest(source="naver")
    st.caption(f"오늘 저장된 네이버 기사: {len(df)}건")
    if not df.empty:
        for _, row in df.head(10).iterrows():
            st.markdown(
                f"""
                <div class="news-card">
                    <div class="card-meta">
                        <span class="card-press">{html.escape(str(row.get('press', '')))}</span>
                        <span class="card-date">{html.escape(str(row.get('date', '')))}</span>
                    </div>
                    <div class="card-title">{html.escape(str(row.get('title', '')))}</div>
                    <div class="card-body">{html.escape(str(row.get('summary', '')))}</div>
                    <div class="card-link"><a href="{html.escape(str(row.get('link', '')))}" target="_blank">원문 보기 →</a></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
