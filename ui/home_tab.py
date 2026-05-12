"""홈: 페르소나 기반 오늘의 인사이트 + 빠른 행동."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from sola.client import is_configured as llm_ready
from sola.insight import insight_for_dept
from store.match import score_matches
from store.news_db import load_all_today
from ui.styles import page_header


def _persona_card(persona: Persona) -> None:
    if not persona.is_set():
        st.warning("⬅️ 사이드바에서 페르소나를 설정하면 맞춤 인사이트가 표시됩니다.")
        return

    chips = []
    for label, val in (
        ("부서", persona.dept),
        ("직무", persona.job),
        ("팀", persona.team),
    ):
        if val:
            chips.append(
                f'<span class="card-press">{html.escape(label)}</span> '
                f'<span class="card-date">{html.escape(val)}</span>'
            )
    chip_html = "  ·  ".join(chips)
    name_html = html.escape(persona.name or "사용자")
    st.markdown(
        f"""
        <div class="news-card" style="min-height:auto;">
            <div class="card-meta">
                <span class="card-title" style="margin-bottom:0;">안녕하세요, {name_html} 님</span>
            </div>
            <div class="card-meta" style="margin-top:6px;">{chip_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _my_dept_news(persona: Persona, roadmap: pd.DataFrame, news: pd.DataFrame) -> None:
    st.subheader("🎯 우리 부서 관련 뉴스")
    if not persona.dept:
        st.caption("부서 미설정 — 전체 뉴스 중 매칭 점수 상위로 표시합니다.")
        target = roadmap
    else:
        target = roadmap[roadmap["dept"] == persona.dept]
        if target.empty:
            st.info(f"'{persona.dept}' 작업이 로드맵에 없습니다.")
            return

    if persona.interest_lv3:
        sub = target[target["lv3"].astype(str).isin(persona.interest_lv3)]
        if not sub.empty:
            target = sub

    matches = score_matches(news, target, top_k=2)
    if matches.empty:
        st.info("매칭되는 뉴스가 없습니다. 키워드를 추가해 수집해보세요.")
        return

    top = matches.sort_values("score", ascending=False).drop_duplicates("link").head(8)
    for _, row in top.iterrows():
        related_news = news[news["link"] == row["link"]].head(1)
        body = ""
        if not related_news.empty:
            r = related_news.iloc[0]
            body = str(r.get("summary_llm") or r.get("summary") or "")
        st.markdown(
            f"""
            <div class="news-card" style="min-height:auto;">
                <div class="card-meta">
                    <span class="card-press">{html.escape(str(row['dept']))}</span>
                    <span class="card-date">{html.escape(str(row['lv3']))} · {html.escape(str(row['task']))}</span>
                    <span class="card-num">score {row['score']:.1f}</span>
                </div>
                <div class="card-title">{html.escape(str(row['news_title']))}</div>
                <div class="card-body">{html.escape(body)}</div>
                <div class="card-link"><a href="{html.escape(str(row['link']))}" target="_blank">원문 보기 →</a></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _my_dept_insight(persona: Persona, news: pd.DataFrame) -> None:
    st.subheader("💡 우리 부서 AI 인사이트")
    if not persona.dept:
        st.caption("부서 미설정")
        return
    if not llm_ready():
        st.info("LLM 미설정 — `.env` 의 `LLM_API_KEY` 설정 후 표시됩니다.")
        return
    text = insight_for_dept(persona.dept, news)
    st.markdown(
        f"""
        <div class="news-card" style="min-height:auto;">
            <div class="card-meta">
                <span class="card-press">{html.escape(persona.dept)}</span>
            </div>
            <div class="card-body" style="-webkit-line-clamp: 6;">{html.escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render() -> None:
    page_header("홈", "오늘의 페르소나 기반 인사이트")

    persona: Persona = st.session_state.get("persona") or Persona()
    _persona_card(persona)

    roadmap = load_roadmap()
    news = load_all_today()

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("오늘 뉴스", f"{len(news):,}건")
    col_b.metric("로드맵 작업", f"{len(roadmap):,}건")
    enr = int((news["content"].astype(str).str.len() >= 50).sum()) if not news.empty and "content" in news.columns else 0
    col_c.metric("본문 확보", f"{enr:,}건")

    if roadmap.empty or news.empty:
        st.markdown("---")
        st.info("로드맵 업로드와 뉴스 수집을 먼저 진행하세요. [🔍 탐색] 영역으로 이동.")
        return

    st.markdown("---")
    left, right = st.columns([2, 1])
    with left:
        _my_dept_news(persona, roadmap, news)
    with right:
        _my_dept_insight(persona, news)

    st.markdown("---")
    st.subheader("⚡ 빠른 행동")
    st.markdown(
        """
        - **🔍 탐색 → 뉴스 수집**: 새 키워드로 뉴스 추가
        - **🔍 탐색 → 인사이트보드**: 부서·공정별 트렌드와 매칭
        - **💼 작업실 → SOLA 채팅**: 페르소나 컨텍스트로 질문
        - **💼 작업실 → 제안서**: 관심 작업으로 자동화 과제 제안서 생성
        """
    )
