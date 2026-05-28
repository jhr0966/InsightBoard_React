"""산출물 보관함 — v2 디자인 적용.

칸반 (대기·채택·기각·적용 4-열) + 리스트 + 타임라인 뷰. 드래그앤드롭과
실제 데이터(`store/bookmarks.py`) 와이어업은 후속 PR.
"""
from __future__ import annotations

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from store import bookmarks as bookmarks_store
from ui import app_shell
from ui.styles import inject_screen_css


_ARCHIVE_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "archive_main.html"


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
    """산출물 보관함 v2 — topbar + app-side + main + app-sola."""
    inject_screen_css("archive")

    persona = _load_persona()
    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="산출물 보관함",
        eyebrow_current="산출물 보관함",
        refresh_label=refresh,
        fresh_kind="accent",
    )
    app_shell.render_app_side(
        active_area="📦 산출물 보관함",
        persona=persona,
        stats=stats,
    )
    st.html(_ARCHIVE_TEMPLATE.read_text(encoding="utf-8"))
    app_shell.render_app_sola(
        context_label="산출물 보관함",
        context_sub="제안서 32 · 브리핑 8 · 보고서 5 · 채택 28건",
        quick_prompts=[
            ("01", "<b>대기 12건</b> 중 가장 빨리 검토해야 할 3건은?"),
            ("02", "<b>채택 28건</b>의 공통 성공 요인 정리"),
            ("03", "기각 5건 — 사유 패턴 분석"),
        ],
        last_q="채택된 도장 PoC 제안서들이 공통적으로 강조한 KPI는?",
        last_a_html=(
            "공통 KPI 3가지가 두드러져요. <b>불량률 ↓</b> (5건 평균 −34%), "
            "<b>검사 공수 ↓</b> (평균 −58%), <b>ROI 회수기간</b> (평균 6.4개월). "
            "특히 ROI 가 6개월 이내인 제안이 채택률 91% 였어요."
            "<span class='muted'>06:08 · 컨텍스트: 채택 28건</span>"
        ),
        last_time="5분 전",
    )
