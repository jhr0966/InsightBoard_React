"""인사이트 분석 — v2 디자인 적용.

핸드오프 `insights-analysis v2.html` 의 main 컬럼을 그대로 가져온다.
트렌드·매칭·매트릭스 데이터 와이어업은 후속 PR — 화면 자체는 placeholder
콘텐츠로 시각 완성 후 점진 교체.
"""
from __future__ import annotations

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from store import bookmarks as bookmarks_store
from ui import app_shell
from ui.styles import inject_screen_css


_IA_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "insights_main.html"


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
    """인사이트 분석 v2 — topbar + app-side + main + app-sola."""
    inject_screen_css("insights")

    persona = _load_persona()
    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="인사이트 분석",
        eyebrow_current="인사이트 분석",
        refresh_label=refresh,
        fresh_kind="fresh",
    )
    app_shell.render_app_side(
        active_area="🔎 인사이트 분석",
        persona=persona,
        stats=stats,
    )
    st.html(_IA_TEMPLATE.read_text(encoding="utf-8"))
    app_shell.render_app_sola(
        context_label="인사이트 분석",
        context_sub="8주 키워드 · 공정 매핑 · ROI×난이도 매트릭스",
        quick_prompts=[
            ("01", "<b>비전 검사</b> 트렌드 8주 동향 요약"),
            ("02", "우리 부서 매칭률 가장 높은 <b>키워드 3개</b>는?"),
            ("03", "매트릭스 우상단 4건 중 PoC 우선순위 추천"),
        ],
        last_q="비전 검사 키워드 8주 그래프가 의미하는 게 뭐야?",
        last_a_html=(
            "확연한 상승 추세예요. <b>지난 4주에서 누적 멘션 +62%</b> 증가, "
            "주체는 현대중공업·삼성중공업·대우조선해양 등 조선소 3사. "
            "우리 공정과 직결되는 비중이 78% 라 PoC 후보 1순위."
            "<span class='muted'>06:08 · 컨텍스트: 트렌드 8주 + 매칭</span>"
        ),
        last_time="2분 전",
    )
