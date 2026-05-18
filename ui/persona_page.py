"""Persona profile editor page.

Opened from the large avatar/profile card in the sidebar so persona fields do not
crowd the global navigation.
"""
from __future__ import annotations

import streamlit as st

from persona import store as persona_store
from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from ui.styles import page_header, section_label


def _options(df, col: str) -> list[str]:
    if df.empty or col not in df.columns:
        return [""]
    return [""] + sorted(df[col].dropna().astype(str).unique().tolist())


def _lv3_options(df) -> list[str]:
    if df.empty or "lv3" not in df.columns:
        return []
    return sorted(df["lv3"].dropna().astype(str).unique().tolist())


def _save_from_state(persona: Persona) -> None:
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
    st.session_state["persona_page_msg"] = ("ok", f"프로필 저장됨: {new.label()}")


def _handle_pending(persona: Persona) -> None:
    if st.session_state.pop("_do_persona_page_save", False):
        _save_from_state(persona)
        st.session_state["show_persona_editor"] = False
        st.rerun()

    if st.session_state.pop("_do_persona_page_reset", False):
        persona_store.reset()
        st.session_state["persona"] = Persona()
        st.session_state["persona_page_msg"] = ("warn", "페르소나 초기화 완료")
        st.rerun()

    if st.session_state.pop("_do_persona_page_back", False):
        st.session_state["show_persona_editor"] = False
        st.rerun()


def render() -> None:
    """Render the main-content persona editor page."""
    persona: Persona = st.session_state.get("persona") or persona_store.load()
    roadmap = load_roadmap()

    page_header(
        "사용자 프로필 설정",
        "부서·직무·관심 공정을 설정하면 오늘의 보드와 SOLA 컨텍스트가 개인화됩니다.",
    )

    msg = st.session_state.pop("persona_page_msg", None)
    if msg:
        kind, text = msg
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](text)

    _handle_pending(persona)

    section_label("기본 정보")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("이름", value=persona.name, key="px_name", placeholder="예: 홍길동")
            dept_opts = _options(roadmap, "dept")
            st.selectbox(
                "부서",
                dept_opts,
                index=dept_opts.index(persona.dept) if persona.dept in dept_opts else 0,
                key="px_dept",
            )
        with c2:
            team_opts = _options(roadmap, "team")
            st.selectbox(
                "팀",
                team_opts,
                index=team_opts.index(persona.team) if persona.team in team_opts else 0,
                key="px_team",
            )
            st.text_input(
                "직무",
                value=persona.job,
                key="px_job",
                placeholder="예: 용접 담당, 자동화 엔지니어, 검사관",
            )

        st.multiselect(
            "관심 공정(Lv3)",
            options=_lv3_options(roadmap),
            default=[v for v in persona.interest_lv3 if v in _lv3_options(roadmap)],
            key="px_lv3",
            help="관심 공정을 선택하면 오늘의 보드와 인사이트 분석이 더 좁은 업무 맥락으로 정렬됩니다.",
        )

    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        if st.button("저장", type="primary", key="persona_page_save_btn", use_container_width=True):
            st.session_state["_do_persona_page_save"] = True
            st.rerun()
    with b2:
        if st.button("초기화", key="persona_page_reset_btn", use_container_width=True):
            st.session_state["_do_persona_page_reset"] = True
            st.rerun()
    with b3:
        if st.button("돌아가기", key="persona_page_back_btn", use_container_width=True):
            st.session_state["_do_persona_page_back"] = True
            st.rerun()
