"""인사이트보드 탭: 부서/공정 × 뉴스 매칭 (M1 룰 기반)."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from roadmap.query import filter_hierarchy, load_latest as load_roadmap
from store.match import score_matches
from store.news_db import load_all_today
from ui.styles import page_header


def _select(label: str, options: list[str], key: str) -> str | None:
    if not options:
        return None
    choice = st.selectbox(label, ["(전체)"] + options, key=key)
    return None if choice == "(전체)" else choice


def render() -> None:
    page_header("인사이트보드", "부서·공정 × 뉴스 매칭 (M1: 룰 기반)")

    roadmap = load_roadmap()
    news = load_all_today()

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("로드맵 작업", f"{len(roadmap):,}건")
    col_b.metric("오늘 뉴스", f"{len(news):,}건")
    col_c.metric("부서 수", f"{roadmap['dept'].nunique() if not roadmap.empty else 0}")

    if roadmap.empty or news.empty:
        st.info("로드맵 업로드와 뉴스 수집을 먼저 진행하세요.")
        return

    st.markdown("---")
    st.subheader("계층 필터")
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        dept = _select("부서", sorted(roadmap["dept"].dropna().astype(str).unique().tolist()), "board_dept")
    with fcol2:
        lv1 = _select("분류(Lv1)", sorted(roadmap["lv1"].dropna().astype(str).unique().tolist()), "board_lv1")
    with fcol3:
        lv3 = _select("공정(Lv3)", sorted(roadmap["lv3"].dropna().astype(str).unique().tolist()), "board_lv3")

    filtered = filter_hierarchy(roadmap, dept=dept, lv1=lv1, lv3=lv3)
    st.caption(f"필터 적용 작업: {len(filtered):,}건")

    if filtered.empty:
        st.warning("선택한 필터에 해당하는 작업이 없습니다.")
        return

    matches = score_matches(news, filtered, top_k=3)
    if matches.empty:
        st.info("매칭되는 뉴스가 없습니다. 다른 키워드로 수집해보세요.")
        return

    st.markdown("---")
    st.subheader("뉴스 매칭 결과")

    agg = (
        matches.groupby(["dept", "lv3", "task"], dropna=False)
        .agg(matched_news=("link", "nunique"), avg_score=("score", "mean"))
        .reset_index()
        .sort_values(["matched_news", "avg_score"], ascending=False, ignore_index=True)
    )
    st.dataframe(agg.head(30), use_container_width=True, hide_index=True)

    st.markdown("**매칭 상세 (상위 30)**")
    for _, row in matches.sort_values("score", ascending=False).head(30).iterrows():
        st.markdown(
            f"""
            <div class="news-card" style="min-height:auto;">
                <div class="card-meta">
                    <span class="card-press">{html.escape(str(row['dept']))}</span>
                    <span class="card-date">{html.escape(str(row['lv3']))} · {html.escape(str(row['task']))}</span>
                    <span class="card-num">score {row['score']:.1f}</span>
                </div>
                <div class="card-title">{html.escape(str(row['news_title']))}</div>
                <div class="card-link"><a href="{html.escape(str(row['link']))}" target="_blank">원문 보기 →</a></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
