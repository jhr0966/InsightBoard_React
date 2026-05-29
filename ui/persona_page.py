"""Persona profile editor page.

Opened from the large avatar/profile card in the sidebar so persona fields do not
crowd the global navigation.

v2: 글로벌 셸(topbar + app-side)로 감싸 다른 화면과 시각 통일. 폼 본문은 실제
Streamlit 위젯(selectbox/multiselect/button)을 그대로 사용 — HTML 치환 불가
(편집 입력이 필요). `body:has(.db-topbar)` 패딩 안에 위젯이 정렬된다.
"""
from __future__ import annotations

import streamlit as st

from persona import store as persona_store
from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from store import bookmarks as _bookmarks_store
from ui import app_shell
from ui.styles import inject_screen_css, page_header, section_label


def _archive_stats() -> dict[str, int]:
    """app-side 좌측 통계 — bookmarks summary 기반 (다른 화면과 동일 키)."""
    try:
        summary = _bookmarks_store.summary_counts()
        pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
    except Exception:
        pending = 0
    return {"match_today": 0, "opportunities": 0, "pending_adopt": pending}


def _options(df, col: str) -> list[str]:
    if df.empty or col not in df.columns:
        return [""]
    return [""] + sorted(df[col].dropna().astype(str).unique().tolist())


def _has_roadmap_options(opts: list[str]) -> bool:
    """`_options()` 결과에서 실제 선택지가 있는지 (빈 값 외에 1개라도 있는지)."""
    return len(opts) > 1


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
    """Render the main-content persona editor page (v2 셸 적용)."""
    persona: Persona = st.session_state.get("persona") or persona_store.load()
    roadmap = load_roadmap()

    # ── v2 글로벌 셸 — 다른 화면과 동일한 topbar + 좌측 네비 ──
    inject_screen_css("board")  # 공통 토큰만 필요 (.db-* 미사용이나 안전)
    app_shell.render_topbar(
        page_title="프로필 설정",
        eyebrow_current="프로필 / 페르소나",
        refresh_label=app_shell.refresh_label_now(),
        fresh_kind="",
    )
    app_shell.render_app_side(
        active_area="",  # 5-nav 중 해당 없음 — 강조 없이 표시
        persona=persona,
        stats=_archive_stats(),
    )
    app_shell.render_setup_banner_if_needed()

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
    dept_opts = _options(roadmap, "dept")
    team_opts = _options(roadmap, "team")
    lv3_opts = _lv3_options(roadmap)
    no_roadmap = (
        not _has_roadmap_options(dept_opts)
        and not _has_roadmap_options(team_opts)
        and not lv3_opts
    )
    if no_roadmap:
        st.info(
            "🗂 로드맵이 아직 업로드되지 않아 부서·팀·관심 공정 추천 목록이 비어있습니다. "
            "일단 자유 입력으로 설정해도 OK — 로드맵을 올린 뒤 다시 들어오면 드롭다운으로 바뀝니다."
        )

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("이름", value=persona.name, key="px_name", placeholder="예: 홍길동")
            if _has_roadmap_options(dept_opts):
                st.selectbox(
                    "부서",
                    dept_opts,
                    index=dept_opts.index(persona.dept) if persona.dept in dept_opts else 0,
                    key="px_dept",
                )
            else:
                st.text_input(
                    "부서",
                    value=persona.dept,
                    key="px_dept",
                    placeholder="예: 생산기술팀, 자동화기술팀",
                    help="로드맵을 업로드하면 이 자리에 부서 추천 목록이 나타납니다.",
                )
        with c2:
            if _has_roadmap_options(team_opts):
                st.selectbox(
                    "팀",
                    team_opts,
                    index=team_opts.index(persona.team) if persona.team in team_opts else 0,
                    key="px_team",
                )
            else:
                st.text_input(
                    "팀",
                    value=persona.team,
                    key="px_team",
                    placeholder="예: 자동화 1팀",
                    help="로드맵을 업로드하면 이 자리에 팀 추천 목록이 나타납니다.",
                )
            st.text_input(
                "직무",
                value=persona.job,
                key="px_job",
                placeholder="예: 용접 담당, 자동화 엔지니어, 검사관",
            )

        if lv3_opts:
            st.multiselect(
                "관심 공정",
                options=lv3_opts,
                default=[v for v in persona.interest_lv3 if v in lv3_opts],
                key="px_lv3",
                help="관심 공정을 선택하면 오늘의 보드와 인사이트 분석이 그 공정 중심으로 정렬됩니다. (로드맵의 Lv3 항목 기준)",
            )
        else:
            st.caption(
                "관심 공정 선택은 로드맵 업로드 후 활성화됩니다. "
                "현재 저장된 관심 공정: " + (" · ".join(persona.interest_lv3) if persona.interest_lv3 else "없음")
            )
            # 입력 누락 시에도 _save_from_state 에서 빈 리스트가 들어가지 않도록 기존 값 유지.
            st.session_state["px_lv3"] = list(persona.interest_lv3)

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
