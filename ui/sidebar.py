"""사이드바: 업무 흐름형 네비 + 컴팩트 페르소나 카드 + 시스템 푸터."""
from __future__ import annotations

import html as _html
from urllib.parse import quote, unquote

import streamlit as st

from ui.components import render_html

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

_AREA_DESCRIPTIONS = {
    "📊 오늘의 보드": "맞춤 인사이트",
    "🧱 데이터 관리": "수집 · 둘러보기 · 로드맵",
    "🔎 인사이트 분석": "트렌드 · 기회 · 매칭",
    "🤖 SOLA 작업실": "초안 · 대화",
    "📦 산출물 보관함": "북마크 · 채택",
}


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


def _llm_footer_html(*, ready: bool, backend: str, model: str) -> str:
    """LLM 상태 + 미설정 시 Groq 키 발급 안내 카드.

    헬퍼로 분리해 단위 테스트 가능.
    """
    dot_cls = "ok" if ready else "warn"
    backend_safe = _html.escape(backend)
    model_safe = _html.escape(model or "(미설정)")
    if ready:
        return f"""
        <div class="sidebar-footer">
          <span class="sidebar-dot {dot_cls}"></span>
          <span class="sidebar-footer-text">
            <b>LLM · {backend_safe}</b><br>
            <span class="muted">{model_safe}</span>
          </span>
        </div>
        """
    return f"""
    <div class="sidebar-footer sidebar-footer-empty">
      <div class="sidebar-footer-row">
        <span class="sidebar-dot {dot_cls}"></span>
        <span class="sidebar-footer-text">
          <b>LLM · {backend_safe}</b><br>
          <span class="muted">키 미설정</span>
        </span>
      </div>
      <div class="sidebar-llm-empty-hint">
        요약·제안서·채팅 등 AI 기능을 쓰려면 키가 필요합니다.<br>
        <a href="https://console.groq.com/keys" target="_blank" rel="noopener">
          🔑 Groq 키 발급 (무료)
        </a>
        · 발급 후 <code>.env</code>의<br><code>LLM_API_KEY=gsk_…</code> 한 줄만 채우면 OK
      </div>
    </div>
    """


def _persona_card_html(persona: Persona) -> str:
    avatar = _html.escape(_avatar_text(persona))
    name = _html.escape(persona.name or "사용자")
    dept = _html.escape(persona.dept or "부서 미설정")
    job = _html.escape(persona.job or "직무 미설정")
    team = _html.escape(persona.team or "팀 미설정")
    interests = _html.escape(
        " · ".join(persona.interest_lv3[:3]) if persona.interest_lv3 else "관심 공정 미설정"
    )
    if persona.is_set():
        hint = "아바타를 눌러 프로필 편집"
        card_extra_class = ""
    else:
        hint = "👋 클릭해서 프로필 설정 시작"
        card_extra_class = " persona-profile-card-empty"
    return f"""
    <a class="persona-profile-link" href="?persona_editor=1" target="_self"
       aria-label="페르소나 편집 페이지 열기">
      <div class="persona-profile-card{card_extra_class}">
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
        <div class="persona-profile-edit-hint">{hint}</div>
      </div>
    </a>
    """


def _consume_persona_editor_query() -> None:
    """Open the persona editor when the sidebar avatar link is clicked."""
    if st.query_params.get("persona_editor") != "1":
        return
    st.session_state["show_persona_editor"] = True
    del st.query_params["persona_editor"]


def _consume_area_query() -> None:
    """Open a sidebar area when the Apple-style nav link is clicked."""
    raw = st.query_params.get("app_area")
    if not raw:
        return
    area = unquote(raw)
    if area in AREAS:
        st.session_state["app_area"] = area
        st.session_state["show_persona_editor"] = False
    del st.query_params["app_area"]


def _sidebar_nav_html(current_area: str) -> str:
    """Return Apple-style sidebar navigation links without radio/button chrome."""
    items = []
    for idx, area in enumerate(AREAS, start=1):
        active = area == current_area
        cls = "sidebar-nav-item active" if active else "sidebar-nav-item"
        title = _html.escape(area)
        desc = _html.escape(_AREA_DESCRIPTIONS.get(area, ""))
        href = f"?app_area={quote(area)}"
        aria_current = ' aria-current="page"' if active else ""
        items.append(
            f"""<a class="{cls}" href="{href}" target="_self"{aria_current}>
                <span class="sidebar-nav-index">{idx:02d}</span>
                <span class="sidebar-nav-copy">
                  <span class="sidebar-nav-title">{title}</span>
                  <span class="sidebar-nav-desc">{desc}</span>
                </span>
              </a>"""
        )
    return '<nav class="sidebar-nav" aria-label="업무 흐름">' + "".join(items) + "</nav>"


def _render_persona_block(persona: Persona, _roadmap_df) -> None:
    """Render a clickable profile summary; editing happens on the main page."""
    _consume_persona_editor_query()
    render_html(_persona_card_html(persona), unsafe_allow_html=True)

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
    render_html(
        """
        <div class="sidebar-brand compact">
          <div class="sidebar-brand-mark">IB</div>
          <div class="sidebar-brand-text">Insight Board</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 업무 흐름 네비
    _consume_area_query()
    if st.session_state.get("app_area") not in AREAS:
        st.session_state["app_area"] = AREAS[0]
    area = st.session_state["app_area"]
    render_html('<div class="sidebar-section sidebar-section-nav">Workflow</div>', unsafe_allow_html=True)
    render_html(_sidebar_nav_html(area), unsafe_allow_html=True)
    render_html(
        '<div class="sidebar-flow-hint apple">'
        '데이터 준비 → 분석 → SOLA 산출물 → 보관'
        '</div>',
        unsafe_allow_html=True,
    )

    # 시스템 푸터 (점선 인디케이터 + 미설정 시 안내 카드)
    render_html(
        _llm_footer_html(
            ready=llm_ready(),
            backend=llm_backend(),
            model=llm_model() or "",
        ),
        unsafe_allow_html=True,
    )

    return area
