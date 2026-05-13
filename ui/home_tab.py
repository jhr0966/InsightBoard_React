"""홈: 페르소나 기반 오늘의 인사이트 + 빠른 행동 + 사이드 채팅."""
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
from ui.layout import main_and_chat
from ui.styles import page_header, section_label


def _persona_welcome(persona: Persona) -> str:
    """페르소나 카드 HTML 반환 (메인에 출력)."""
    if not persona.is_set():
        return (
            '<div class="card-flat">'
            '⬅️ <b>사이드바</b>에서 페르소나를 설정하면 맞춤 인사이트가 표시됩니다.'
            '</div>'
        )
    chips_html = ""
    for label, val in (("부서", persona.dept), ("직무", persona.job), ("팀", persona.team)):
        if val:
            chips_html += (
                f'<span class="card-press">{html.escape(label)}</span>'
                f'<span style="color:var(--text-2);font-size:0.85rem;margin:0 14px 0 6px;">'
                f'{html.escape(val)}</span>'
            )
    name = html.escape(persona.name or "사용자")
    return f"""
    <div class="card">
      <div style="font-size:1.4rem;font-weight:700;color:var(--text-1);letter-spacing:-0.02em;
                  margin-bottom:6px;">안녕하세요, {name} 님</div>
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;">{chips_html}</div>
    </div>
    """


def _dept_news_cards(persona: Persona, roadmap: pd.DataFrame, news: pd.DataFrame) -> tuple[str, list[dict]]:
    """부서 매칭 뉴스 카드 HTML + 컨텍스트용 dict 리스트 반환."""
    if not persona.dept:
        target = roadmap
        caption = "부서 미설정 — 전체 매칭 점수 상위로 표시합니다."
    else:
        target = roadmap[roadmap["dept"] == persona.dept]
        if target.empty:
            return (
                f'<div class="card-flat">로드맵에 \'{html.escape(persona.dept)}\' 작업이 없습니다.</div>',
                [],
            )
        caption = ""

    if persona.interest_lv3:
        sub = target[target["lv3"].astype(str).isin(persona.interest_lv3)]
        if not sub.empty:
            target = sub

    matches = score_matches(news, target, top_k=2)
    if matches.empty:
        return ('<div class="card-flat">매칭되는 뉴스가 없습니다.</div>', [])

    top = matches.sort_values("score", ascending=False).drop_duplicates("link").head(6)

    parts: list[str] = []
    ctx_items: list[dict] = []
    if caption:
        parts.append(f'<div style="font-size:0.78rem;color:var(--text-3);margin-bottom:8px;">{caption}</div>')

    for _, row in top.iterrows():
        related = news[news["link"] == row["link"]].head(1)
        body = ""
        if not related.empty:
            r = related.iloc[0]
            body = str(r.get("summary_llm") or r.get("summary") or "")
        parts.append(f"""
        <div class="card" style="margin-bottom:12px;">
          <div class="card-meta">
            <span class="card-press">{html.escape(str(row['dept']))}</span>
            <span class="card-date">{html.escape(str(row['lv3']))} · {html.escape(str(row['task']))}</span>
            <span class="card-num">score {row['score']:.1f}</span>
          </div>
          <div class="card-title" style="-webkit-line-clamp:2;">{html.escape(str(row['news_title']))}</div>
          <div class="card-body" style="-webkit-line-clamp:3;">{html.escape(body[:240])}</div>
          <div class="card-link"><a href="{html.escape(str(row['link']))}" target="_blank">원문 보기 →</a></div>
        </div>
        """)
        ctx_items.append({
            "title": str(row["news_title"]),
            "dept": str(row["dept"]),
            "lv3": str(row["lv3"]),
            "task": str(row["task"]),
            "summary": body[:200],
        })
    return ("".join(parts), ctx_items)


def _dept_insight_card(persona: Persona, news: pd.DataFrame) -> tuple[str, str]:
    """부서 AI 인사이트 카드 HTML + raw 텍스트 반환."""
    if not persona.dept:
        return ('<div class="card-flat" style="font-size:0.85rem;color:var(--text-3);">부서 미설정</div>', "")
    if not llm_ready():
        return (
            '<div class="card-flat" style="font-size:0.85rem;color:var(--text-3);">'
            'LLM 미설정 — <code>.env</code> 의 <code>LLM_API_KEY</code> 후 표시됩니다.</div>',
            "",
        )
    text = insight_for_dept(persona.dept, news)
    return (
        f'<div class="card"><div class="card-meta">'
        f'<span class="card-press">{html.escape(persona.dept)} · AI 인사이트</span></div>'
        f'<div class="card-body" style="-webkit-line-clamp:8;font-size:0.92rem;">'
        f'{html.escape(text)}</div></div>',
        text,
    )


def _build_page_context(persona: Persona, news_items: list[dict], insight_text: str) -> str:
    """사이드 채팅에 주입할 페이지 컨텍스트."""
    lines = []
    if persona.is_set():
        lines.append(f"사용자 부서: {persona.dept or '미설정'}, 직무: {persona.job or '미설정'}")
    if insight_text:
        lines.append(f"\n부서 AI 인사이트:\n{insight_text}")
    if news_items:
        lines.append("\n표시 중인 부서 매칭 뉴스 (상위):")
        for it in news_items[:5]:
            lines.append(f"- [{it['dept']}/{it['lv3']}/{it['task']}] {it['title']}")
            if it["summary"]:
                lines.append(f"    {it['summary']}")
    return "\n".join(lines)


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    roadmap = load_roadmap()
    news = load_all_today()

    # 페이지 헤더 (채팅 토글 포함)
    chat_open = page_header(
        "홈",
        "오늘의 페르소나 기반 인사이트",
        chat_toggle_key="home",
    )

    # 본문 컨텍스트 채우기를 위해 미리 계산
    news_html, news_ctx = ("", [])
    insight_html, insight_text = ("", "")
    if not roadmap.empty and not news.empty:
        news_html, news_ctx = _dept_news_cards(persona, roadmap, news)
        insight_html, insight_text = _dept_insight_card(persona, news)
    page_ctx = _build_page_context(persona, news_ctx, insight_text)

    with main_and_chat(
        "home",
        page_context_fn=lambda: page_ctx,
        persona=persona,
        hint="현재 홈 화면(페르소나 · 매칭 뉴스 · AI 인사이트)을 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            # 페르소나 welcome
            st.markdown(_persona_welcome(persona), unsafe_allow_html=True)

            # 메트릭 3개
            m1, m2, m3 = st.columns(3)
            m1.metric("오늘 뉴스", f"{len(news):,}건")
            m2.metric("로드맵 작업", f"{len(roadmap):,}건")
            enr = int((news["content"].astype(str).str.len() >= 50).sum()) if not news.empty and "content" in news.columns else 0
            m3.metric("본문 확보", f"{enr:,}건")

            if roadmap.empty or news.empty:
                st.markdown(
                    '<div class="card-flat" style="margin-top:1.5rem;">'
                    '로드맵 업로드와 뉴스 수집을 먼저 진행하세요. '
                    '<b>🔍 탐색</b> 영역으로 이동.</div>',
                    unsafe_allow_html=True,
                )
            else:
                # 부서 뉴스 + 인사이트 2:1
                st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
                if chat_open:
                    # 채팅 패널 열려있으면 메인이 좁아지니 카드 세로 배치.
                    section_label("우리 부서 관련 뉴스")
                    st.markdown(news_html, unsafe_allow_html=True)
                    section_label("우리 부서 AI 인사이트")
                    st.markdown(insight_html, unsafe_allow_html=True)
                else:
                    left, right = st.columns([2, 1], gap="large")
                    with left:
                        section_label("우리 부서 관련 뉴스")
                        st.markdown(news_html, unsafe_allow_html=True)
                    with right:
                        section_label("우리 부서 AI 인사이트")
                        st.markdown(insight_html, unsafe_allow_html=True)

            # 빠른 행동
            st.markdown("<div style='margin-top:1.8rem;'></div>", unsafe_allow_html=True)
            section_label("빠른 행동")
            st.markdown(
                """
                <div class="quick-grid">
                  <div class="quick-tile">
                    <div class="quick-tile-icon">🔍</div>
                    <div class="quick-tile-title">뉴스 수집·Enrich</div>
                    <div class="quick-tile-desc">탐색 → 뉴스 수집. 새 키워드로 기사 추가.</div>
                  </div>
                  <div class="quick-tile">
                    <div class="quick-tile-icon">📊</div>
                    <div class="quick-tile-title">인사이트보드</div>
                    <div class="quick-tile-desc">탐색 → 트렌드·자동화 기회 매트릭스.</div>
                  </div>
                  <div class="quick-tile">
                    <div class="quick-tile-icon">💬</div>
                    <div class="quick-tile-title">SOLA 채팅</div>
                    <div class="quick-tile-desc">작업실 → 페르소나 컨텍스트로 질문.</div>
                  </div>
                  <div class="quick-tile">
                    <div class="quick-tile-icon">📝</div>
                    <div class="quick-tile-title">제안서 작업장</div>
                    <div class="quick-tile-desc">작업실 → 살아있는 제안서 수정·요약.</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
