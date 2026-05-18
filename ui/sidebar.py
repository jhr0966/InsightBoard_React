"""사이드바: 업무 흐름형 네비 + 컴팩트 페르소나 카드 + 시스템 푸터."""
from __future__ import annotations

import html as _html

import streamlit as st

from config import llm_backend, llm_model
from persona import store as persona_store
from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from sola.client import is_configured as llm_ready


AREAS = (
    "📊 오늘의 보드",
    "🧱 데이터 관리",
    "🔎 인사이트 분석",
    "🤖 SOLA 작업실",
    "📦 산출물 보관함",
)


def _load_persona_into_state() -> Persona:
    if "persona" not in st.session_state:
        st.session_state["persona"] = persona_store.load()
    return st.session_state["persona"]


def _avatar_text(persona: Persona) -> str:
    if persona.name:
        return persona.name.strip()[0]
    if persona.dept:
        return persona.dept.strip()[0]
    return "?"


def _persona_card_html(persona: Persona) -> str:
    avatar = _html.escape(_avatar_text(persona))
    name = _html.escape(persona.name or "사용자")
    dept = _html.escape(persona.dept or "부서 미설정")
    job = _html.escape(persona.job or "직무 미설정")
    team = _html.escape(persona.team or "팀 미설정")
    interests = _html.escape(" · ".join(persona.interest_lv3[:3]) if persona.interest_lv3 else "관심 공정 미설정")
    return f"""
    <a class="persona-profile-link" href="?persona_editor=1" target="_self"
       aria-label="페르소나 편집 페이지 열기">
      <div class="persona-profile-card">
        <div class="persona-profile-avatar">
          <div class="persona-profile-head">{avatar}</div>
          <div class="persona-profile-body"></div>
        </div>
        <div class="persona-profile-name">{name}</div>
        <div class="persona-profile-role">{dept} · {job}</div>
        <div class="persona-profile-details">
          <div><span>팀</span><b>{team}</b></div>
          <div><span>관심</span><b>{interests}</b></div>
        </div>
        <div class="persona-profile-edit-hint">아바타를 눌러 프로필 편집</div>
      </div>
    </a>
    """


def _consume_persona_editor_query() -> None:
    """Open the persona editor when the sidebar avatar link is clicked."""
    if st.query_params.get("persona_editor") != "1":
        return
    st.session_state["show_persona_editor"] = True
    del st.query_params["persona_editor"]


def _render_persona_block(persona: Persona, _roadmap_df) -> None:
    """Render a clickable profile summary; editing happens on the main page."""
    _consume_persona_editor_query()
    st.markdown(_persona_card_html(persona), unsafe_allow_html=True)

    msg = st.session_state.pop("persona_page_msg", None)
    if msg:
        kind, text = msg
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](text)


def render() -> str:
    """사이드바 렌더링 후 현재 선택된 영역(string) 반환."""
    roadmap_df = load_roadmap()
    persona = _load_persona_into_state()

    # 최상단 사용자 프로필
    _render_persona_block(persona, roadmap_df)

    # 브랜드
    st.markdown(
        """
        <div class="sidebar-brand compact">
          <div class="sidebar-brand-mark">IB</div>
          <div class="sidebar-brand-text">Insight Board</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 업무 흐름 네비
    st.markdown('<div class="sidebar-section">업무 흐름</div>', unsafe_allow_html=True)
    if st.session_state.get("app_area") not in AREAS:
        st.session_state["app_area"] = AREAS[0]
    area = st.radio("업무 흐름", AREAS, key="app_area", label_visibility="collapsed")
    st.markdown(
        '<div class="sidebar-flow-hint">'
        '1 데이터 준비 → 2 인사이트 분석 → 3 SOLA 산출물 생성'
        '</div>',
        unsafe_allow_html=True,
    )

    # 시스템 푸터 (점선 인디케이터)
    dot_cls = "ok" if llm_ready() else "warn"
    backend = _html.escape(llm_backend())
    model = _html.escape(llm_model() or "(미설정)")
    st.markdown(
        f"""
        <div class="sidebar-footer">
          <span class="sidebar-dot {dot_cls}"></span>
          <span class="sidebar-footer-text">
            <b>LLM · {backend}</b><br>
            <span class="muted">{model}</span>
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return area
