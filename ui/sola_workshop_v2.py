"""SOLA 작업실 — v2 디자인 적용.

특수성: SOLA workshop 화면은 우측 .app-sola 패널을 그리지 않는다. 대신 화면
자체가 3-열 `.ws-shell` (쓰레드 / 채팅 / 컨텍스트) 로 구성되어 SOLA 경험을
풀스크린으로 제공.

CSS 규칙은 `body:has(.ws-shell)` 분기로 block-container 우측 패딩을 축소
(scale.css 에 추가).
"""
from __future__ import annotations

import html as _html

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from store import bookmarks as bookmarks_store
from ui import app_shell
from ui.styles import inject_screen_css


_SOLA_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "sola_main.html"


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


def _archive_stats() -> dict[str, int]:
    summary = bookmarks_store.summary_counts()
    pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
    return {"match_today": 32, "opportunities": 4, "pending_adopt": pending}


def render() -> None:
    """SOLA 작업실 v2 — topbar + app-side + 3-열 ws-shell (app-sola 없음)."""
    inject_screen_css("sola")

    persona = _load_persona()
    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="SOLA 작업실",
        eyebrow_current="SOLA 작업실",
        refresh_label=refresh,
        fresh_kind="accent",
    )
    app_shell.render_app_side(
        active_area="🤖 SOLA 작업실",
        persona=persona,
        stats=stats,
    )
    _render_main(persona)
    # 의도적으로 app-sola 미렌더 — ws-ctx 가 그 역할 대체


def _render_main(persona: Persona) -> None:
    """sola_main.html 템플릿 로드 + persona snapshot 치환."""
    name = persona.name or "사용자"
    dept = persona.dept or ""
    job = persona.job or ""
    line_parts = [p for p in (name, job, dept) if p]
    persona_line = " · ".join(line_parts) if line_parts else "사용자"

    interests = persona.interest_lv3 or persona.interest_tasks or []
    interests_label = ", ".join(interests[:3]) if interests else "미설정"

    template = _SOLA_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{PERSONA_LINE}}", _html.escape(persona_line))
        .replace("{{PERSONA_INTERESTS}}", _html.escape(interests_label))
        .replace("{{PERSONA_TEAM_SIZE}}", "5–15명")
        .replace("{{KEYWORDS_COUNT}}", "8개")
    )
    st.html(html_out)
