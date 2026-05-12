"""사이드바: 페르소나 설정 + 영역 선택 + 시스템 상태."""
from __future__ import annotations

import streamlit as st

from config import llm_backend, llm_model
from persona import store as persona_store
from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from sola.client import is_configured as llm_ready


AREAS = ("🏠 홈", "🔍 탐색", "💼 작업실")


def _load_persona_into_state() -> Persona:
    if "persona" not in st.session_state:
        st.session_state["persona"] = persona_store.load()
    return st.session_state["persona"]


def _persona_form(roadmap_df) -> None:
    persona = _load_persona_into_state()

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

    with st.expander("👤 페르소나 설정", expanded=not persona.is_set()):
        new_name = st.text_input("이름(선택)", value=persona.name, key="px_name")
        new_team = st.selectbox(
            "팀", team_opts,
            index=team_opts.index(persona.team) if persona.team in team_opts else 0,
            key="px_team",
        )
        new_dept = st.selectbox(
            "부서", dept_opts,
            index=dept_opts.index(persona.dept) if persona.dept in dept_opts else 0,
            key="px_dept",
        )
        new_job = st.text_input(
            "직무 (자유 입력)",
            value=persona.job,
            placeholder="예: 용접 담당, 절단 담당, 검사관",
            key="px_job",
        )
        new_interest_lv3 = st.multiselect(
            "관심 공정(Lv3)",
            options=lv3_opts,
            default=[v for v in persona.interest_lv3 if v in lv3_opts],
            key="px_lv3",
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("저장", type="primary", key="px_save_btn"):
                st.session_state["_do_persona_save"] = True
        with c2:
            if st.button("초기화", key="px_reset_btn"):
                st.session_state["_do_persona_reset"] = True

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


def render() -> str:
    """사이드바 렌더링 후 현재 선택된 영역(string) 반환."""
    roadmap_df = load_roadmap()
    persona = _load_persona_into_state()

    st.markdown("## 🛠️ 인사이트보드")
    st.caption(f"페르소나: **{persona.label()}**" if persona.is_set() else "페르소나 미설정")

    area = st.radio("영역", AREAS, key="app_area")
    st.markdown("---")

    _persona_form(roadmap_df)

    st.markdown("---")
    st.caption("🔌 LLM 상태")
    st.markdown(f"- backend: `{llm_backend()}`")
    st.markdown(f"- model: `{llm_model() or '(미설정)'}`")
    st.markdown(f"- ready: {'✅' if llm_ready() else '❌'}")

    return area
