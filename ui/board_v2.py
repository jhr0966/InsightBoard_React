"""오늘의 보드 — v2 디자인 적용.

핸드오프 `dashboard-full v2.html` 의 main 컬럼을 그대로 가져오고 persona 이름과
갱신 시각 + 4 KPI 카드 (수집·매칭·자동화 기회·채택 대기) 를 동적 치환.

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
from roadmap.query import load_latest as _load_roadmap
from store import bookmarks as bookmarks_store
from store import news_db as _news_db
from store.match import score_matches as _score_matches
from sola.opportunity import score_cells as _score_cells
from ui import app_shell
from ui.styles import inject_screen_css


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


@st.cache_data(ttl=60)
def _board_kpis() -> dict[str, int]:
    """4 KPI 실데이터 계산 — 60초 캐시. 실패 시 0 폴백 (시각 화면은 항상 렌더).

    Returns:
      collect: 오늘 수집된 뉴스 수
      match:   강한 매칭 (score>0) 뉴스 수
      opp:     자동화 기회 셀 수 (dept × lv3)
      pending: 채택 대기 제안서 수
    """
    try:
        news_df = _news_db.load_news_for_days(days=1)
    except Exception:
        news_df = None
    try:
        roadmap_df = _load_roadmap()
    except Exception:
        roadmap_df = None

    collect = int(len(news_df)) if news_df is not None else 0

    match_count = 0
    opp_count = 0
    if (
        news_df is not None and not news_df.empty
        and roadmap_df is not None and not roadmap_df.empty
    ):
        try:
            matches = _score_matches(news_df, roadmap_df, top_k=3)
            if not matches.empty:
                match_count = int(matches[matches["score"] > 0]["link"].nunique())
        except Exception:
            pass
        try:
            cells = _score_cells(news_df, roadmap_df)
            opp_count = int(len(cells))
        except Exception:
            pass

    summary = bookmarks_store.summary_counts()
    pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]

    return {
        "collect": collect,
        "match": match_count,
        "opp": opp_count,
        "pending": pending,
    }


def _archive_stats() -> dict[str, int]:
    """app-side 좌측 카운트 — 보드 KPI 와 동일 소스 재사용."""
    kpis = _board_kpis()
    return {
        "match_today": kpis["match"],
        "opportunities": kpis["opp"],
        "pending_adopt": kpis["pending"],
    }


def render() -> None:
    """오늘의 보드 v2 — topbar + app-side + main + app-sola 풀 셸 렌더."""
    # 보드 화면 전용 스타일 (.db-greet, .db-kpi, .db-stories, .db-trend 등)
    inject_screen_css("board")

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
    kpis = _board_kpis()
    # 델타는 yesterday snapshot 비교 후속 PR — 일단 빈 값
    template = _BOARD_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{REFRESH_LABEL}}", _html.escape(refresh_label))
        .replace("{{PERSONA_GREET}}", _html.escape(_persona_greet(persona)))
        .replace("{{PERSONA_NAME}}", _html.escape(_persona_short(persona)))
        .replace("{{KPI_COLLECT}}", str(kpis["collect"]))
        .replace("{{KPI_MATCH}}", str(kpis["match"]))
        .replace("{{KPI_OPP}}", str(kpis["opp"]))
        .replace("{{KPI_PENDING}}", str(kpis["pending"]))
        .replace("{{KPI_COLLECT_DELTA}}", "")
        .replace("{{KPI_MATCH_DELTA}}", "")
        .replace("{{KPI_OPP_DELTA}}", "")
        .replace("{{KPI_PENDING_DELTA}}", "")
        .replace("{{KPI_COLLECT_CLS}}", "db-delta-flat")
        .replace("{{KPI_MATCH_CLS}}", "db-delta-flat")
        .replace("{{KPI_OPP_CLS}}", "db-delta-flat")
        .replace("{{KPI_PENDING_CLS}}", "db-delta-flat")
    )
    st.html(html_out)
