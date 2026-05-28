"""오늘의 보드 — v2 디자인 적용.

핸드오프 `dashboard-full v2.html` 의 main 컬럼을 그대로 가져오고 persona 이름과
갱신 시각만 동적 치환. 데이터 와이어업(KPI · 탑 스토리 · 트렌드 등)은 후속 PR
에서 화면 자체를 건드리지 않고 placeholder 를 데이터 바인딩으로 교체하는 방식
으로 점진 적용한다.

CLAUDE.md 규칙:
  - on_click 금지 → 모든 인터랙션 disabled (visual handoff 단계)
  - HTML 직접 출력 시 사용자 문자열은 html.escape() 적용
"""
from __future__ import annotations

import html as _html
from pathlib import Path

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from store import bookmarks as bookmarks_store
from ui import app_shell


_BOARD_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "board_main.html"


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


def _persona_greet(persona: Persona) -> str:
    """헤더 인사: '박정훈 책임' / '자동화기술팀' / '사용자' 우선순위."""
    if persona.name and persona.job:
        return f"{persona.name} {persona.job}"
    if persona.name:
        return persona.name
    if persona.dept:
        return persona.dept
    return "사용자"


def _persona_short(persona: Persona) -> str:
    """본문 '박정훈님이' 같은 호칭."""
    return persona.name or persona.dept or "사용자"


def _archive_stats() -> dict[str, int]:
    """app-side 통계 — 북마크 store 에서 가능한 부분만 채움.

    오늘 매칭/자동화 기회 카운트는 후속 PR 에서 store/match.py 와 연결할 때 합류.
    지금은 핸드오프 시안의 시각적 무게를 살리려고 시안 카운트(32/4/대기수) 를 사용.
    """
    summary = bookmarks_store.summary_counts()
    pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
    return {
        "match_today": 32,         # TODO: store/match.py 연결 시 실제값
        "opportunities": 4,         # TODO: sola/opportunity.py 연결 시 실제값
        "pending_adopt": pending,
    }


def render() -> None:
    """오늘의 보드 v2 — topbar + app-side + main + app-sola 풀 셸 렌더."""
    persona = _load_persona()
    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    # ── 1) 풀폭 topbar ──
    app_shell.render_topbar(
        page_title="오늘의 보드",
        eyebrow_current="오늘의 보드",
        refresh_label=refresh,
        fresh_kind="fresh",
    )

    # ── 2) 좌측 .app-side ──
    app_shell.render_app_side(
        active_area="📊 오늘의 보드",
        persona=persona,
        stats=stats,
    )

    # ── 3) 본문 (main) — 템플릿 로드 후 placeholder 치환 ──
    _render_main(persona=persona, refresh_label=refresh)

    # ── 4) 우측 .app-sola ──
    app_shell.render_app_sola(
        context_label="오늘의 보드",
        context_sub=f"오늘 매칭 {stats['match_today']}건 · 자동화 기회 {stats['opportunities']}건",
        quick_prompts=[
            ("01", "이 페이지 <b>탑 스토리 3건</b>을 부서장 메시지로 요약해줘"),
            ("02", "<b>도장 비전 검사</b> PoC 일정·예산 초안 만들어줘"),
            ("03", "<b>트렌드</b> 그래프에서 우리 작업과 가장 관련 큰 키워드 3개는?"),
        ],
        last_q="자동화 기회 4건 중 가장 빨리 시작할 수 있는 건 뭐야?",
        last_a_html=(
            "도장 비전 검사가 가장 빨라요. <b>설비 변경 없이 카메라 1대 추가</b>로 "
            "1주 안에 시작 가능 — 게다가 도장팀이 작년에 비슷한 PoC 제안한 적이 있어 "
            "공감대도 있어요.<span class='muted'>05:54 · 컨텍스트: 자동화 기회 4건</span>"
        ),
        last_time="2분 전",
    )


def _render_main(*, persona: Persona, refresh_label: str) -> None:
    template = _BOARD_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{REFRESH_LABEL}}", _html.escape(refresh_label))
        .replace("{{PERSONA_GREET}}", _html.escape(_persona_greet(persona)))
        .replace("{{PERSONA_NAME}}", _html.escape(_persona_short(persona)))
    )
    st.html(html_out)
