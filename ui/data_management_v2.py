"""데이터 관리 — v2 디자인 적용.

헤더 4 stats + 뉴스 라이브러리 카드 (최근 6건) 실데이터 바인딩.
수집잡 5행과 14일 sparkline 은 별도 PR (ingest job tracking + SVG 동적 빌드 필요).
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone

import pandas as pd
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


# 뉴스 라이브러리에 노출할 카드 수
_MAX_NEWS_CARDS = 6

# 출처별 그라데이션 — 시안과 일관성 유지
_SOURCE_GRADIENTS = {
    "AI Times": "linear-gradient(135deg,#DC2626,#F87171)",
    "오토메이션월드": "linear-gradient(135deg,#D97706,#F59E0B)",
    "automationworld": "linear-gradient(135deg,#D97706,#F59E0B)",
    "Google RSS": "linear-gradient(135deg,#047857,#14B8A6)",
    "google": "linear-gradient(135deg,#047857,#14B8A6)",
    "네이버 기술": "linear-gradient(135deg,#6D28D9,#A78BFA)",
    "naver": "linear-gradient(135deg,#6D28D9,#A78BFA)",
}
_DEFAULT_GRADIENT = "linear-gradient(135deg,#475569,#94A3B8)"


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


def _news_age_label(when: str) -> str:
    """ISO 시각 → '3시간 전' / '어제' / '5월 17일'."""
    if not when:
        return ""
    try:
        ts = when.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "방금"
        if secs < 3600:
            return f"{secs // 60}분 전"
        if secs < 86400:
            return f"{secs // 3600}시간 전"
        if secs < 172800:
            return "어제"
        if secs < 86400 * 30:
            return f"{secs // 86400}일 전"
        return f"{dt.month}월 {dt.day}일"
    except Exception:
        return ""


def _news_card_html(row: pd.Series, *, is_strong: bool = False) -> str:
    """단일 뉴스 row → 카드 HTML (`<li class="dm-art">`)."""
    title = _html.escape(str(row.get("title", "") or "(제목 없음)"))
    body_raw = str(row.get("content", "") or "")[:140].strip()
    if len(str(row.get("content", "") or "")) > 140:
        body_raw += "…"
    body = _html.escape(body_raw)
    source = str(row.get("source", "") or "")
    source_safe = _html.escape(source)
    gradient = _SOURCE_GRADIENTS.get(source, _DEFAULT_GRADIENT)
    when = str(row.get("collected_at", "") or row.get("published_at", "") or "")
    age = _html.escape(_news_age_label(when))

    li_cls = "dm-art dm-art-strong" if is_strong else "dm-art"
    tag_html = ""
    if is_strong:
        tag_html = '<span class="dm-art-tag dm-art-tag-strong">★ 강한 매칭</span>'

    # tags / keywords — content_keywords 컬럼이 있으면 활용
    chips_html = ""
    kw = row.get("keywords") if hasattr(row, "get") else None
    if isinstance(kw, (list, tuple)):
        for k in list(kw)[:3]:
            chips_html += f'<span class="dm-mini">{_html.escape(str(k))}</span>'

    return f"""<li class="{li_cls}">
      <div class="dm-art-img">
        <span class="dm-art-img-stripe"></span>
        {tag_html}
      </div>
      <div class="dm-art-body">
        <div class="dm-art-meta">
          <span class="dm-src"><span class="dm-src-mark" style="background:{gradient};"></span>{source_safe}</span>
          <span class="dm-time">{age}</span>
        </div>
        <h3 class="dm-art-h">{title}</h3>
        {f'<p class="dm-art-p">{body}</p>' if body else ''}
        {f'<div class="dm-art-chips">{chips_html}</div>' if chips_html else ''}
      </div>
    </li>"""


def _news_empty_html() -> str:
    return """<li class="dm-art" style="
        grid-column: 1 / -1; padding: 32px 18px; text-align: center;
        color: var(--text-muted); font-size: 14px;
        border: 1px dashed var(--surface-divider); border-radius: 12px;
        background: rgba(0,0,0,0.01);">
      아직 수집된 뉴스가 없어요.<br>
      <span style="font-size:12.5px;">'지금 실행' 버튼으로 수집을 시작하세요.</span>
    </li>"""


@st.cache_data(ttl=60)
def _news_cards_html() -> str:
    """최근 뉴스 6건 → 카드 HTML 결합."""
    try:
        news = _news_db.load_news_for_days(days=3)
    except Exception:
        news = None
    if news is None or news.empty:
        return _news_empty_html()

    # collected_at 내림차순 정렬 (있으면)
    if "collected_at" in news.columns:
        news = news.sort_values("collected_at", ascending=False)
    elif "published_at" in news.columns:
        news = news.sort_values("published_at", ascending=False)

    top = news.head(_MAX_NEWS_CARDS)
    parts = []
    for i, (_, row) in enumerate(top.iterrows()):
        parts.append(_news_card_html(row, is_strong=(i == 0)))
    return "\n".join(parts)


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
        .replace("{{NEWS_CARDS}}", _news_cards_html())
    )
    st.html(html_out)
