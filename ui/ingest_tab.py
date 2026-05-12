"""수집 탭: 네이버/구글 뉴스 키워드 검색 → Parquet 저장."""
from __future__ import annotations

import html

import streamlit as st

from scraping import google as google_news
from scraping import naver as naver_news
from store.news_db import load_all_today, save_articles
from ui.styles import page_header


_SOURCE_LABELS = {
    "둘 다": ("naver", "google"),
    "네이버 뉴스": ("naver",),
    "구글 뉴스": ("google",),
}


def _run(sources: tuple[str, ...], keyword: str, max_results: int) -> None:
    saved: list[tuple[str, int, str]] = []
    errors: list[str] = []
    for src in sources:
        try:
            if src == "naver":
                articles = naver_news.search(keyword, max_results=max_results)
            else:
                articles = google_news.search(keyword, max_results=max_results)
        except RuntimeError as e:
            errors.append(f"{src}: {e}")
            continue
        path = save_articles(articles, source=src)
        saved.append((src, len(articles), path.name if path else "(저장 없음)"))

    if errors:
        st.session_state["ins_status"] = ("error", " · ".join(errors))
        return
    msg = " · ".join(f"{src} {n}건 → {fname}" for src, n, fname in saved)
    st.session_state["ins_status"] = ("ok", msg or "수집된 기사가 없습니다.")


def render() -> None:
    page_header("뉴스 수집", "네이버 + 구글 뉴스 → 일자별 Parquet")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.text_input("검색 키워드", key="ins_keyword", placeholder="예: 조선소 자동화, 용접 로봇")
    with col2:
        st.selectbox("소스", list(_SOURCE_LABELS.keys()), key="ins_source")
    st.slider("소스당 수집 건수", min_value=5, max_value=50, value=20, step=5, key="ins_max_results")

    if st.button("검색·저장", type="primary"):
        st.session_state["_do_search"] = True

    if st.session_state.pop("_do_search", False):
        keyword = st.session_state.get("ins_keyword", "").strip()
        if not keyword:
            st.session_state["ins_status"] = ("warn", "키워드를 입력하세요.")
        else:
            sources = _SOURCE_LABELS[st.session_state.get("ins_source", "둘 다")]
            _run(sources, keyword, int(st.session_state.get("ins_max_results", 20)))
        st.rerun()

    status = st.session_state.get("ins_status")
    if status:
        kind, msg = status
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](msg)

    st.markdown("---")
    df = load_all_today()
    st.caption(f"오늘 저장된 전체 기사: {len(df)}건")
    if df.empty:
        return

    by_source = (
        df.groupby("source", dropna=False).size()
        .reset_index(name="count").sort_values("count", ascending=False, ignore_index=True)
    )
    st.dataframe(by_source, use_container_width=True, hide_index=True)

    st.markdown("**최근 10건**")
    for _, row in df.head(10).iterrows():
        st.markdown(
            f"""
            <div class="news-card">
                <div class="card-meta">
                    <span class="card-press">{html.escape(str(row.get('press', '')))}</span>
                    <span class="card-date">{html.escape(str(row.get('date', '')))}</span>
                    <span class="card-num">{html.escape(str(row.get('source', '')))}</span>
                </div>
                <div class="card-title">{html.escape(str(row.get('title', '')))}</div>
                <div class="card-body">{html.escape(str(row.get('summary', '')))}</div>
                <div class="card-link"><a href="{html.escape(str(row.get('link', '')))}" target="_blank">원문 보기 →</a></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
