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
def _ingest_jobs_html() -> str:
    """오늘의 수집잡 — source 별 카운트 + 마지막 시각 → dm-job 행 빌드.

    실제 ingest job tracker 가 없어 news_db 의 source 별 그룹 카운트로 대체.
    상태는 모두 'done' 으로 표시 (실시간 진행 상태 트래킹은 후속 PR).
    """
    try:
        today_df = _news_db.load_all_today()
    except Exception:
        today_df = None

    if today_df is None or today_df.empty:
        return ('<li class="dm-job" style="border:1px dashed var(--surface-divider); '
                'padding:14px; text-align:center; color: var(--text-muted); font-size: 14px;">'
                '오늘 실행된 수집잡이 없습니다.<br>'
                '<span style="font-size:12.5px;">[지금 실행] 으로 수집 시작</span>'
                '</li>')

    if "source" not in today_df.columns:
        return ""

    grouped = today_df.groupby("source").size().reset_index(name="count")
    grouped = grouped.sort_values("count", ascending=False).head(5)

    parts = []
    for _, row in grouped.iterrows():
        src = str(row["source"])
        cnt = int(row["count"])
        gradient = _SOURCE_GRADIENTS.get(src, _DEFAULT_GRADIENT)
        # 마지막 시각
        src_today = today_df[today_df["source"] == src]
        last_time = ""
        for col in ("collected_at", "published_at"):
            if col in src_today.columns:
                try:
                    ts = src_today[col].dropna().astype(str).max()
                    if ts:
                        if "T" in ts:
                            last_time = ts.split("T")[1][:5]
                        elif " " in ts:
                            last_time = ts.split(" ")[1][:5]
                        break
                except Exception:
                    pass
        parts.append(
            f'<li class="dm-job dm-job-done">'
            f'<span class="dm-job-mark" style="background:{gradient};"></span>'
            f'<div class="dm-job-body">'
            f'<div class="dm-job-name">{_html.escape(src)} '
            f'<span class="dm-job-meta">{cnt}건</span></div>'
            f'<div class="dm-job-sub">본문 enrich 완료</div>'
            f'</div>'
            f'<span class="dm-job-time">{_html.escape(last_time)}</span>'
            f'</li>'
        )
    return "\n".join(parts)


@st.cache_data(ttl=60)
def _hist_html() -> dict[str, str]:
    """14일 수집량 sparkline + head/foot 라벨 HTML.

    SVG 는 img src='data:image/svg+xml,...' 형식이라 큰따옴표 escape 필요 →
    src 내부는 모두 단일 따옴표.
    """
    try:
        hist_df = _news_db.load_news_for_days(days=14)
    except Exception:
        hist_df = None

    # daily volume
    daily_counts: list[int] = [0] * 14
    today_count = 0
    avg_daily = 0
    if hist_df is not None and not hist_df.empty:
        try:
            from datetime import datetime, timezone, timedelta
            today = datetime.now(timezone.utc).date()
            # bucket per day
            for col in ("collected_at", "published_at", "fetched_at"):
                if col in hist_df.columns:
                    for ts_str in hist_df[col].dropna().astype(str):
                        try:
                            d = datetime.fromisoformat(ts_str.replace("Z","+00:00")).date()
                            delta = (today - d).days
                            if 0 <= delta < 14:
                                daily_counts[13 - delta] += 1
                        except Exception:
                            pass
                    break
            today_count = daily_counts[-1]
            non_zero = [c for c in daily_counts if c > 0]
            if non_zero:
                avg_daily = sum(non_zero) // len(non_zero)
        except Exception:
            pass

    max_val = max(daily_counts) if any(daily_counts) else 1

    # Build SVG bars — 14 bars at x=2,22,42,...,262 (20px stride, 16px wide), bar h max 56
    bars = []
    for i, count in enumerate(daily_counts):
        x = 2 + i * 20
        h = max(round(count / max_val * 56), 2) if count > 0 else 2
        y = 60 - h
        is_today = (i == 13)
        fill = "#2563EB" if is_today else "#CBD5E1"
        bars.append(f"<rect x='{x}' y='{y}' width='16' height='{h}' fill='{fill}' rx='2'/>")

    svg_inner = (
        "<line x1='0' y1='50' x2='280' y2='50' stroke='#E5E7EB' stroke-dasharray='2 3'/>"
        + "".join(bars)
    )
    svg_full = (
        "<svg xmlns='http://www.w3.org/2000/svg' "
        "class='dm-hist-chart' viewBox='0 0 280 70' "
        "preserveAspectRatio='none'>"
        f"{svg_inner}"
        "</svg>"
    )
    svg_img = f'<img src="data:image/svg+xml;utf8,{svg_full}" width="280" height="70" alt="14일 수집량 차트" />'

    head_html = (
        '<div class="dm-hist-head">'
        '<span class="dm-hist-t">14일 수집량</span>'
        f'<span class="dm-hist-meta">평균 {avg_daily}건/일</span>'
        '</div>'
    )
    foot_html = (
        '<div class="dm-hist-x">'
        '<span>−14d</span>'
        f'<span>오늘 {today_count}</span>'
        '</div>'
    )
    return {"head": head_html, "svg": svg_img, "foot": foot_html}


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


def chat_context_block(persona: Persona) -> str:
    """데이터 관리 화면이 보여주는 모든 데이터를 LLM 컨텍스트로 packaging.

    헤더 4 stats + 14일 sparkline 일별 수집량 + 뉴스 라이브러리 6 + 수집잡 요약.
    캐시된 helper 들이 같은 데이터를 계산해두므로 재호출은 캐시 hit.
    """
    parts: list[str] = ["--- 현재 화면: 데이터 관리 (🧱) ---"]

    # 헤더 4 stats
    try:
        s = _dm_stats()
        parts.append(
            f"수집 현황: 활성 출처 {s.get('active_sources','—')}개 · "
            f"오늘 수집 {s.get('today_count','—')}건 · "
            f"30일 누적 {s.get('total_chunks','—')} · "
            f"최근 업데이트 {s.get('last_update','—')}"
        )
    except Exception:
        pass

    # 14일 일별 수집 추이 (sparkline 원본)
    try:
        week = _news_db.load_news_for_days(days=14)
        if not week.empty and "collected_at" in week.columns:
            import pandas as _pd
            dt = _pd.to_datetime(week["collected_at"], errors="coerce", utc=True).dt.strftime("%m/%d")
            by_day = dt.value_counts().sort_index().tail(14)
            parts.append("14일 일별 수집 추이:")
            parts.append("  " + " · ".join(f"{d}: {int(c)}건" for d, c in by_day.items()))
    except Exception:
        pass

    # 출처별 분포 (수집잡 5행)
    try:
        week = _news_db.load_news_for_days(days=7)
        if not week.empty and "source" in week.columns:
            top_src = week["source"].value_counts().head(5)
            parts.append("출처별 7일 수집량 top 5:")
            for src, cnt in top_src.items():
                parts.append(f"  - {src}: {int(cnt)}건")
    except Exception:
        pass

    # 뉴스 라이브러리 — 최근 6건
    try:
        today_df = _news_db.load_all_today()
        recent = today_df if today_df is not None and not today_df.empty else \
                 _news_db.load_news_for_days(days=3)
        if not recent.empty:
            if "collected_at" in recent.columns:
                recent = recent.sort_values("collected_at", ascending=False)
            parts.append("뉴스 라이브러리 (최근 6건):")
            for _, r in recent.head(6).iterrows():
                t = str(r.get("title", ""))[:100]
                s = str(r.get("source", ""))
                summary = str(r.get("summary_llm", "") or r.get("summary", ""))[:120]
                parts.append(f"  - {t} ({s})")
                if summary:
                    parts.append(f"    요약: {summary}")
    except Exception:
        pass

    return "\n".join(parts)


def render() -> None:
    """데이터 관리 v2 — topbar + app-side + main + app-sola 풀 셸 렌더.

    `?refresh=now` 가 들어오면 첫 단계에서 1회 소비 → 캐시 invalidate + 토스트.
    """
    inject_screen_css("data_management")

    _consume_refresh_if_any()

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

    app_shell.render_setup_banner_if_needed()
    _render_refresh_toast_if_needed()

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


def _refresh_cta_html() -> str:
    """수집잡 헤더의 "지금 실행" CTA — 캐시 무효화 + 안내 배너 트리거 링크."""
    from urllib.parse import quote

    href = (
        "?app_area=" + quote("🧱 데이터 관리")
        + "&refresh=now"
    )
    return (
        f'<a class="dm-btn-primary" href="{href}" target="_self" '
        f'title="캐시를 즉시 무효화해 새 데이터로 다시 그립니다 (실제 수집은 스케줄러가 06:00 에 실행)">'
        '<img src="data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'11\' '
        'height=\'11\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'#fff\' stroke-width=\'2.4\' '
        'stroke-linecap=\'round\' stroke-linejoin=\'round\'><polyline points=\'23 4 23 10 17 10\'/>'
        '<path d=\'M3.51 9a9 9 0 0114.85-3.36L23 10\'/></svg>" width="11" height="11" alt="" />'
        '지금 새로고침'
        '</a>'
    )


def _consume_refresh_if_any() -> bool:
    """`?refresh=now` 1회 소비 — 데이터 관리 캐시 무효화 + 토스트 플래그 set."""
    if st.query_params.get("refresh") != "now":
        return False
    # 모든 dm 관련 캐시 무효화
    for fn in (_dm_stats, _ingest_jobs_html, _hist_html, _news_cards_html, _archive_stats_dm):
        if hasattr(fn, "clear"):
            fn.clear()
    st.session_state["_dm_refresh_toast"] = True
    if "refresh" in st.query_params:
        del st.query_params["refresh"]
    return True


def _render_refresh_toast_if_needed() -> None:
    """직전 새로고침 직후 한 번만 노출되는 inline toast (sticky 안 함)."""
    if not st.session_state.pop("_dm_refresh_toast", False):
        return
    st.html(
        """
        <style>
          body:has(.db-topbar) .dm-refresh-toast {
            margin: 0 24px 14px; padding: 10px 14px;
            background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px;
            font-size: 13px; color: #064E3B; font-weight: 600;
          }
        </style>
        <div class="dm-refresh-toast">
          ✓ 캐시를 새로 그렸어요 — 카운터/뉴스 카드/14일 sparkline 이 갱신됐습니다.
          <span style="font-weight:500;color:#065F46;">(실제 수집은 매일 06:00 KST 스케줄러가 실행)</span>
        </div>
        """
    )


def _render_main(dm_stats: dict[str, str | int]) -> None:
    """data_management_main.html 템플릿 로드 + placeholder 치환."""
    template = _DM_TEMPLATE.read_text(encoding="utf-8")
    hist = _hist_html()
    html_out = (
        template
        .replace("{{LAST_UPDATE}}", _html.escape(str(dm_stats["last_update"])))
        .replace("{{ACTIVE_SOURCES}}", _html.escape(str(dm_stats["active_sources"])))
        .replace("{{TODAY_COUNT}}", _html.escape(str(dm_stats["today_count"])))
        .replace("{{TOTAL_CHUNKS}}", _html.escape(str(dm_stats["total_chunks"])))
        .replace("{{NEWS_CARDS}}", _news_cards_html())
        .replace("{{INGEST_JOBS}}", _ingest_jobs_html())
        .replace("{{INGEST_REFRESH_CTA}}", _refresh_cta_html())
        .replace("{{HIST_HEAD}}", hist["head"])
        .replace("{{HIST_SVG}}", hist["svg"])
        .replace("{{HIST_X}}", hist["foot"])
    )
    st.html(html_out)
