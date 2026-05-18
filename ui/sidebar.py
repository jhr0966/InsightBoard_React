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
    meta_bits = [bit for bit in (persona.dept, persona.job, persona.team) if bit]
    meta = _html.escape(" · ".join(meta_bits) or "정보 없음")
    return f"""
    <div class="persona-card">
      <div class="persona-avatar">{avatar}</div>
      <div class="persona-info">
        <div class="persona-name">{name}</div>
        <div class="persona-meta">{meta}</div>
      </div>
    </div>
    """


def _persona_form_body(persona: Persona, roadmap_df) -> None:
    """페르소나 입력 폼 (expander 안에 들어가는 내부 위젯들)."""
    dept_opts = (
        [""] + sorted(roadmap_df["dept"].dropna().astype(str).unique().tolist())
        if not roadmap_df.empty else [""]
    )
    team_opts = (
        [""] + sorted(roadmap_df["team"].dropna().astype(str).unique().tolist())
        if not roadmap_df.empty else [""]
    )
    lv3_opts = (
        sorted(roadmap_df["lv3"].dropna().astype(str).unique().tolist())
        if not roadmap_df.empty else []
    )

    st.text_input("이름(선택)", value=persona.name, key="px_name")
    st.selectbox(
        "팀", team_opts,
        index=team_opts.index(persona.team) if persona.team in team_opts else 0,
        key="px_team",
    )
    st.selectbox(
        "부서", dept_opts,
        index=dept_opts.index(persona.dept) if persona.dept in dept_opts else 0,
        key="px_dept",
    )
    st.text_input(
        "직무 (자유 입력)",
        value=persona.job,
        placeholder="예: 용접 담당, 절단 담당, 검사관",
        key="px_job",
    )
    st.multiselect(
        "관심 공정(Lv3)",
        options=lv3_opts,
        default=[v for v in persona.interest_lv3 if v in lv3_opts],
        key="px_lv3",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("저장", type="primary", key="px_save_btn", use_container_width=True):
            st.session_state["_do_persona_save"] = True
    with c2:
        if st.button("초기화", key="px_reset_btn", use_container_width=True):
            st.session_state["_do_persona_reset"] = True


def _handle_persona_pending(persona: Persona) -> None:
    if st.session_state.pop("_do_persona_save", False):
        new = Persona(
            name=st.session_state.get("px_name", "").strip(),
            team=st.session_state.get("px_team", "").strip(),
            dept=st.session_state.get("px_dept", "").strip(),
            job=st.session_state.get("px_job", "").strip(),
            interest_lv3=list(st.session_state.get("px_lv3", []) or []),
            interest_tasks=persona.interest_tasks,
        )
        persona_store.save(new)
        st.session_state["persona"] = new
        st.session_state["persona_msg"] = ("ok", f"저장됨: {new.label()}")
        st.session_state["_persona_edit_open"] = False
        st.rerun()

    if st.session_state.pop("_do_persona_reset", False):
        persona_store.reset()
        st.session_state["persona"] = Persona()
        st.session_state["persona_msg"] = ("warn", "페르소나 초기화 완료")
        st.rerun()

    msg = st.session_state.pop("persona_msg", None)
    if msg:
        kind, text = msg
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](text)


def _render_persona_block(persona: Persona, roadmap_df) -> None:
    """페르소나 영역: 설정됨 → 카드 + ✏️ 편집 토글, 미설정 → CTA + 폼 열림."""
    edit_open_key = "_persona_edit_open"

    if persona.is_set():
        st.markdown(_persona_card_html(persona), unsafe_allow_html=True)
        is_open = st.session_state.get(edit_open_key, False)
        if st.button(
            "닫기" if is_open else "✏️ 편집",
            key="persona_toggle_btn",
            use_container_width=True,
        ):
            st.session_state[edit_open_key] = not is_open
            st.rerun()
        if st.session_state.get(edit_open_key, False):
            _persona_form_body(persona, roadmap_df)
    else:
        st.markdown(
            '<div class="persona-cta">'
            '👤 페르소나를 설정하면 부서·직무 기반 맞춤 인사이트가 표시됩니다.'
            '</div>',
            unsafe_allow_html=True,
        )
        _persona_form_body(persona, roadmap_df)

    _handle_persona_pending(persona)


def render() -> str:
    """사이드바 렌더링 후 현재 선택된 영역(string) 반환."""
    roadmap_df = load_roadmap()
    persona = _load_persona_into_state()

    # 브랜드
    st.markdown(
        """
        <div class="sidebar-brand">
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

    # 페르소나
    st.markdown('<div class="sidebar-section">페르소나</div>', unsafe_allow_html=True)
    _render_persona_block(persona, roadmap_df)

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
