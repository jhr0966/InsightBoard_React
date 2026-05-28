"""인사이트 분석 — v2 디자인 적용.

헤더 4 stats (분석 뉴스 / 신규 트렌드 / 매칭 공정 / PoC 후보) + app-side
카운트를 실데이터로 (store/news_db, store/trends, store/match, sola/opportunity,
store/bookmarks). 트렌드 차트·매트릭스·키워드 리스트 시각은 시안 데이터 유지.
"""
from __future__ import annotations

import html as _html

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from roadmap.query import load_latest as _load_roadmap
from store import bookmarks as bookmarks_store
from store import news_db as _news_db
from store import trends as _trends
from store.match import score_matches as _score_matches
from sola.opportunity import score_cells as _score_cells
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


@st.cache_data(ttl=60)
def _ia_stats() -> dict[str, str]:
    """인사이트 분석 헤더 4 stats.

    Returns:
      news_30d: 최근 30일 뉴스 수
      new_trends: 이번 주 신규 emerge 키워드 수 (지난주 대비 +)
      matched_processes: 뉴스가 매칭된 Lv3 공정 unique 수
      poc_candidates: 자동화 기회 + 채택 대기 합 (검토 대기 후보)
    """
    try:
        news_30d = _news_db.load_news_for_days(days=30)
    except Exception:
        news_30d = None
    try:
        news_7d = _news_db.load_news_for_days(days=7)
    except Exception:
        news_7d = None
    try:
        roadmap_df = _load_roadmap()
    except Exception:
        roadmap_df = None

    n_30d = int(len(news_30d)) if news_30d is not None else 0

    # 신규 트렌드: keyword_emergence 함수가 있으면 사용
    new_trends = 0
    try:
        if news_30d is not None and not news_30d.empty:
            emergence_df = _trends.keyword_emergence(news_30d, weeks=4)
            if hasattr(emergence_df, "empty") and not emergence_df.empty:
                # 신규 emerge 만: prev=0 인 항목
                if "prev_count" in emergence_df.columns:
                    new_trends = int((emergence_df["prev_count"] == 0).sum())
                else:
                    new_trends = int(len(emergence_df))
    except Exception:
        pass

    # 매칭 공정 (Lv3 unique): 매치된 뉴스의 lv3 컬럼 카운트
    matched_processes = 0
    if (
        news_7d is not None and not news_7d.empty
        and roadmap_df is not None and not roadmap_df.empty
    ):
        try:
            matches = _score_matches(news_7d, roadmap_df, top_k=3)
            if not matches.empty and "lv3" in matches.columns:
                matched_processes = int(matches[matches["score"] > 0]["lv3"].nunique())
        except Exception:
            pass

    # PoC 후보: 자동화 기회 셀 + 채택 대기 제안서
    poc_candidates = 0
    if (
        news_7d is not None and not news_7d.empty
        and roadmap_df is not None and not roadmap_df.empty
    ):
        try:
            cells = _score_cells(news_7d, roadmap_df)
            poc_candidates += int(len(cells))
        except Exception:
            pass
    summary = bookmarks_store.summary_counts()
    poc_candidates += int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]

    return {
        "news_30d": str(n_30d),
        "new_trends": (f"+{new_trends}" if new_trends > 0 else "0"),
        "matched_processes": str(matched_processes),
        "poc_candidates": str(poc_candidates),
    }


@st.cache_data(ttl=60)
def _archive_stats_ia() -> dict[str, int]:
    """app-side 좌측 — 보드와 동일 소스."""
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
    return {"match_today": match_count, "opportunities": opp_count, "pending_adopt": pending}


def render() -> None:
    """인사이트 분석 v2 — topbar + app-side + main + app-sola."""
    inject_screen_css("insights")

    persona = _load_persona()
    stats = _archive_stats_ia()
    ia_stats = _ia_stats()
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

    template = _IA_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{IA_NEWS_30D}}", _html.escape(ia_stats["news_30d"]))
        .replace("{{IA_NEW_TRENDS}}", _html.escape(ia_stats["new_trends"]))
        .replace("{{IA_MATCHED_PROCESSES}}", _html.escape(ia_stats["matched_processes"]))
        .replace("{{IA_POC_CANDIDATES}}", _html.escape(ia_stats["poc_candidates"]))
    )
    st.html(html_out)

    app_shell.render_app_sola(
        context_label="인사이트 분석",
        context_sub=f"30일 뉴스 {ia_stats['news_30d']}건 · 매칭 공정 {ia_stats['matched_processes']}",
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
            "<span class='muted'>방금 · 컨텍스트: 트렌드 + 매칭</span>"
        ),
        last_time="방금",
    )
