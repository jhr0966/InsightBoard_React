"""데이터 관리 — v2 디자인 적용.

핸드오프 `data-management v2.html` 의 main 컬럼을 그대로 가져오고 마지막 갱신
시각만 동적 치환. 데이터 와이어업(수집잡 상태, 뉴스 카드 등)은 후속 PR 에서
화면 자체를 건드리지 않고 placeholder 를 데이터 바인딩으로 교체.

CLAUDE.md 규칙:
  - on_click 금지 → 모든 인터랙션 disabled (visual handoff 단계)
  - HTML 직접 출력 시 사용자 문자열은 html.escape() 적용
"""
from __future__ import annotations

import html as _html
from datetime import datetime

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from store import bookmarks as bookmarks_store
from ui import app_shell
from ui.styles import inject_screen_css


_DM_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "data_management_main.html"


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


def _archive_stats() -> dict[str, int]:
    """app-side 좌측 카운트 — board_v2 와 동일 패턴.

    Phase 2 에서는 시안 카운트(32/4/대기수) 를 사용. 후속 PR 에서
    store/match.py + sola/opportunity.py 와 연결.
    """
    summary = bookmarks_store.summary_counts()
    pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
    return {
        "match_today": 32,
        "opportunities": 4,
        "pending_adopt": pending,
    }


def render() -> None:
    """데이터 관리 v2 — topbar + app-side + main + app-sola 풀 셸 렌더."""
    inject_screen_css("data_management")

    persona = _load_persona()
    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    # ── 1) 풀폭 topbar ──
    app_shell.render_topbar(
        page_title="데이터 관리",
        eyebrow_current="데이터 관리",
        refresh_label=refresh,
        fresh_kind="fresh",
    )

    # ── 2) 좌측 .app-side ──
    app_shell.render_app_side(
        active_area="🧱 데이터 관리",
        persona=persona,
        stats=stats,
    )

    # ── 3) 본문 main 템플릿 ──
    _render_main()

    # ── 4) 우측 .app-sola ──
    app_shell.render_app_sola(
        context_label="데이터 관리",
        context_sub="4개 출처 · DB chunks 156k · 5작업 중 1진행",
        quick_prompts=[
            ("01", "<b>Google RSS</b> 가 자주 느려지는 이유는?"),
            ("02", "<b>네이버 기술</b> 셀렉터 오류 자동 복구가 가능할까?"),
            ("03", "키워드 <b>'협동 로봇'</b> 추가하면 매칭이 늘어날까?"),
        ],
        last_q="오늘 수집된 156건 중 우리 부서와 가장 관련 깊은 건?",
        last_a_html=(
            "도장 카테고리 8건이 가장 가까워요. 그중 <b>현대중공업 AI 비전 검사 PoC</b>가 "
            "직결돼요 — 4개월 PoC 결과 + 부스 #3·#5 적용 사례까지 한 번에 정리돼 있어요."
            "<span class='muted'>06:08 · 컨텍스트: 오늘 수집 156건</span>"
        ),
        last_time="3분 전",
    )


def _render_main() -> None:
    """data_management_main.html 템플릿 로드 + placeholder 치환."""
    now = datetime.now()
    last_update = f"{now:%H:%M}"

    template = _DM_TEMPLATE.read_text(encoding="utf-8")
    html_out = template.replace("{{LAST_UPDATE}}", _html.escape(last_update))
    st.html(html_out)
