"""데이터 관리 — v2 디자인 적용.

핸드오프 `data-management v2.html` 의 main 컬럼 + 헤더 4 stats (활성 출처,
수집량, DB chunks, 마지막 갱신) + app-side 카운트를 실데이터 (store/news_db,
store/match, sola/opportunity) 에서 계산. 수집잡 5개 / 뉴스 카드 / 키워드는
별도 PR (ingest job tracking 필요).

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
from roadmap.query import load_latest as _load_roadmap
from store import bookmarks as bookmarks_store
from store import news_db as _news_db
from store.match import score_matches as _score_matches
from sola.opportunity import score_cells as _score_cells
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


@st.cache_data(ttl=60)
def _dm_stats() -> dict[str, str | int]:
    """헤더 4 stats 실데이터.

    Returns dict with str values (formatted for direct template substitution):
      active_sources: '4' — 최근 7일 동안 적어도 1건 수집한 unique source 수
      today_count:    '125' — 오늘 수집 뉴스 row 수
      total_chunks:   '8.4k' — 30일 누적 뉴스 row 수 (human-friendly)
      last_update:    '08:24' — 가장 최근 수집 시각 (없으면 현재 시각)
    """
    try:
        today_df = _news_db.load_all_today()
    except Exception:
        today_df = None
    try:
        week_df = _news_db.load_news_for_days(days=7)
    except Exception:
        week_df = None
    try:
        month_df = _news_db.load_news_for_days(days=30)
    except Exception:
        month_df = None

    today_count = int(len(today_df)) if today_df is not None else 0

    active_sources = 0
    if week_df is not None and not week_df.empty and "source" in week_df.columns:
        active_sources = int(week_df["source"].nunique())

    month_count = int(len(month_df)) if month_df is not None else 0
    # human-friendly thousand format
    if month_count >= 1000:
        total_chunks = f"{month_count / 1000:.1f}k"
    else:
        total_chunks = str(month_count)

    # 가장 최근 수집 시각 — today_df 의 published_at 또는 collected_at 최대값
    last_update = ""
    if today_df is not None and not today_df.empty:
        for col in ("collected_at", "published_at", "fetched_at"):
            if col in today_df.columns:
                try:
                    ts = today_df[col].dropna().astype(str).max()
                    if ts:
                        # 시각 부분만 (HH:MM)
                        if "T" in ts:
                            last_update = ts.split("T")[1][:5]
                        elif " " in ts:
                            last_update = ts.split(" ")[1][:5]
                        else:
                            last_update = ts[:5]
                        break
                except Exception:
                    pass
    if not last_update:
        last_update = f"{datetime.now():%H:%M}"

    return {
        "active_sources": str(active_sources),
        "today_count": str(today_count),
        "total_chunks": str(total_chunks),
        "last_update": last_update,
    }


@st.cache_data(ttl=60)
def _archive_stats_dm() -> dict[str, int]:
    """app-side 좌측 카운트 — 보드와 동일 소스 재사용."""
    try:
        news_df = _news_db.load_news_for_days(days=1)
    except Exception:
        news_df = None
    try:
        roadmap_df = _load_roadmap()
    except Exception:
        roadmap_df = None

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
        "match_today": match_count,
        "opportunities": opp_count,
        "pending_adopt": pending,
    }


def render() -> None:
    """데이터 관리 v2 — topbar + app-side + main + app-sola 풀 셸 렌더."""
    inject_screen_css("data_management")

    persona = _load_persona()
    stats = _archive_stats_dm()
    dm_stats = _dm_stats()
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
    _render_main(dm_stats)

    # ── 4) 우측 .app-sola ──
    sources_n = dm_stats["active_sources"]
    today_n = dm_stats["today_count"]
    app_shell.render_app_sola(
        context_label="데이터 관리",
        context_sub=f"{sources_n}개 출처 · DB {dm_stats['total_chunks']} · 오늘 {today_n}건",
        quick_prompts=[
            ("01", "<b>Google RSS</b> 가 자주 느려지는 이유는?"),
            ("02", "<b>네이버 기술</b> 셀렉터 오류 자동 복구가 가능할까?"),
            ("03", "키워드 <b>'협동 로봇'</b> 추가하면 매칭이 늘어날까?"),
        ],
        last_q=f"오늘 수집된 {today_n}건 중 우리 부서와 가장 관련 깊은 건?",
        last_a_html=(
            "도장 카테고리가 가장 가까워요. <b>현대중공업 AI 비전 검사 PoC</b>가 "
            "직결돼요 — 4개월 PoC 결과 + 부스 #3·#5 적용 사례까지 한 번에 정리돼 있어요."
            "<span class='muted'>방금 · 컨텍스트: 오늘 수집</span>"
        ),
        last_time="방금",
    )


def _render_main(dm_stats: dict[str, str | int]) -> None:
    """data_management_main.html 템플릿 로드 + placeholder 치환."""
    template = _DM_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{LAST_UPDATE}}", _html.escape(str(dm_stats["last_update"])))
        .replace("{{ACTIVE_SOURCES}}", _html.escape(str(dm_stats["active_sources"])))
        .replace("{{TODAY_COUNT}}", _html.escape(str(dm_stats["today_count"])))
        .replace("{{TOTAL_CHUNKS}}", _html.escape(str(dm_stats["total_chunks"])))
    )
    st.html(html_out)
