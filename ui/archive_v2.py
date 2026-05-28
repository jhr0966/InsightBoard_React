"""산출물 보관함 — v2 디자인 적용.

헤더 4 stats + 칸반 컬럼 카운트 (대기/채택/기각) 를 store.bookmarks 에서
실시간 계산. 칸반 카드 자체 (PoC 제안서 등) 는 시안 더미 콘텐츠 유지 —
실제 bookmark item → 카드 마크업 렌더는 별도 PR (카드 템플릿 dynamic build 필요).
"""
from __future__ import annotations

import html as _html

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


_ARCHIVE_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "archive_main.html"


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


@st.cache_data(ttl=60)
def _oa_stats() -> dict[str, str]:
    """산출물 보관함 헤더 4 stats — store/bookmarks 직접 계산."""
    summary = bookmarks_store.summary_counts()
    total = int(summary["total"])  # type: ignore[index]
    by_status = summary["proposal_status"]  # type: ignore[index]
    adopted = int(by_status.get("adopted", 0))
    pending = int(by_status.get("pending", 0))
    rejected = int(by_status.get("rejected", 0))

    decided = adopted + rejected
    adopted_pct = ""
    if decided > 0:
        adopted_pct = f"{(adopted / decided) * 100:.1f}%"
    else:
        adopted_pct = "—"

    return {
        "total": str(total),
        "adopted": str(adopted),
        "pending": str(pending),
        "rejected": str(rejected),
        "adopted_pct": adopted_pct,
    }


@st.cache_data(ttl=60)
def _archive_stats_oa() -> dict[str, int]:
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
    """산출물 보관함 v2 — topbar + app-side + main + app-sola."""
    inject_screen_css("archive")

    persona = _load_persona()
    stats = _archive_stats_oa()
    oa_stats = _oa_stats()
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

    template = _ARCHIVE_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{OA_TOTAL}}", _html.escape(oa_stats["total"]))
        .replace("{{OA_ADOPTED_PCT}}", _html.escape(oa_stats["adopted_pct"]))
        .replace("{{OA_ADOPTED}}", _html.escape(oa_stats["adopted"]))
        .replace("{{OA_PENDING}}", _html.escape(oa_stats["pending"]))
        .replace("{{OA_REJECTED}}", _html.escape(oa_stats["rejected"]))
    )
    st.html(html_out)

    app_shell.render_app_sola(
        context_label="산출물 보관함",
        context_sub=f"총 {oa_stats['total']} · 채택 {oa_stats['adopted']} · 대기 {oa_stats['pending']}",
        quick_prompts=[
            ("01", f"<b>대기 {oa_stats['pending']}건</b> 중 가장 빨리 검토해야 할 3건은?"),
            ("02", f"<b>채택 {oa_stats['adopted']}건</b>의 공통 성공 요인 정리"),
            ("03", f"기각 {oa_stats['rejected']}건 — 사유 패턴 분석"),
        ],
        last_q="채택된 도장 PoC 제안서들이 공통적으로 강조한 KPI는?",
        last_a_html=(
            "공통 KPI 3가지가 두드러져요. <b>불량률 ↓</b> (5건 평균 −34%), "
            "<b>검사 공수 ↓</b> (평균 −58%), <b>ROI 회수기간</b> (평균 6.4개월). "
            "특히 ROI 가 6개월 이내인 제안이 채택률 91% 였어요."
            "<span class='muted'>방금 · 컨텍스트: 채택</span>"
        ),
        last_time="방금",
    )
