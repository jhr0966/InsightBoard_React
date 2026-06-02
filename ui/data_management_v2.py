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
from roadmap.query import load_latest as _load_tasks
from roadmap import ingest as _ingest
from store import bookmarks as bookmarks_store
from store import news_db as _news_db
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


def _strip_dm_mockups(html: str) -> str:
    """정적 목업 블록 제거 (Phase C-3) — 실데이터/실위젯이 대체하는 시안 잔재.

    - 죽은 필터바(검색 input·필터칩·출처/기간/정렬 셀렉트 — 핸들러 없음)
    - 죽은 페이저(1–6 / 1,247 … 208 — 핸들러 없음)
    - 가짜 서브카드 3종(키워드 매니저/작업 정의/출처 설정 — 실제 탭이 대체하는 가짜 통계)
    뉴스 카드 그리드·수집 잡·헤더 통계 등 실데이터는 보존. 마커 슬라이스라 div 균형 비의존.
    """
    # dm-filters: 필터바 시작 ~ 기사 그리드 직전
    i = html.find('<div class="dm-filters">')
    if i != -1:
        j = html.find("<!-- Article grid -->", i)
        if j == -1:
            j = html.find('<ul class="dm-art-grid">', i)
        if j != -1:
            html = html[:i] + html[j:]
    # dm-pager: 페이저 시작 ~ 섹션 닫힘
    i = html.find('<div class="dm-pager">')
    if i != -1:
        j = html.find("</section>", i)
        if j != -1:
            html = html[:i] + html[j:]
    # dm-sub-grid: 가짜 서브카드 ~ 끝 (dm-shell 닫는 </div> 보존)
    i = html.find('<div class="dm-sub-grid">')
    if i != -1:
        end = html.rfind("</div>")
        if end != -1 and end > i:
            html = html[:i] + html[end:]
    return html


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
    """app-side 좌측 카운트 — 보드와 동일 소스 재사용 (`_archive_stats` 60초 캐시 위임)."""
    from ui import board_v2  # lazy

    try:
        return board_v2._archive_stats()
    except Exception:
        summary = bookmarks_store.summary_counts()
        pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
        return {"match_today": 0, "opportunities": 0, "pending_adopt": pending}


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

    persona = app_shell.get_persona()
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

    # 업로드/액션 송신 처리 (위젯 인스턴스화 이전, 최상단)
    _consume_task_def_upload_if_any()
    _consume_src_action_if_any()
    _consume_src_add_if_any()
    # PR-6: 작업 정의 관리 액션/저장 — toast 는 manage 본문에서 직접 노출
    from ui import task_def_manage as _tdm
    _tdm.consume_td_action_if_any()
    _tdm.consume_td_save_if_any()

    app_shell.render_setup_banner_if_needed()
    _render_refresh_toast_if_needed()
    _render_task_def_toast_if_needed()
    _render_src_action_toast_if_needed()

    # 활성 그룹·탭 — `?dm_grp=news|tasks&dm_tab=jobs|kw|task|src` (기본 news/jobs).
    # 기존 `?dm_tab=` 만 있는 북마크 URL 도 정상 동작 (그룹 자동 추론).
    selected_grp, selected_tab = _dm_resolve_group_and_tab(
        st.query_params.get("dm_grp"), st.query_params.get("dm_tab"),
    )

    # ── 3) 본문 main 템플릿 ──
    _render_main(dm_stats, selected_tab=selected_tab, persona=persona)

    # ── 3.5) 탭 전용 Streamlit 위젯 ──
    if selected_tab == "task":
        _render_task_def_upload()
    elif selected_tab == "manage":
        from ui import task_def_manage as tdm
        tdm.render(st.query_params)
    elif selected_tab == "src":
        _render_src_add_form()

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
    """수집잡 헤더의 "지금 실행" CTA — collect_batch 동기 호출 + 캐시 무효화."""
    from urllib.parse import quote

    href = (
        "?app_area=" + quote("🧱 데이터 관리")
        + "&refresh=now"
    )
    return (
        f'<a class="dm-btn-primary" href="{href}" target="_self" '
        f'title="페르소나 관심사 키워드로 지금 수집을 실행하고 캐시를 새로 그립니다.">'
        '<img src="data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'11\' '
        'height=\'11\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'#fff\' stroke-width=\'2.4\' '
        'stroke-linecap=\'round\' stroke-linejoin=\'round\'><polyline points=\'23 4 23 10 17 10\'/>'
        '<path d=\'M3.51 9a9 9 0 0114.85-3.36L23 10\'/></svg>" width="11" height="11" alt="" />'
        '지금 새로고침'
        '</a>'
    )


def _consume_refresh_if_any() -> bool:
    """`?refresh=now` 1회 소비 — collect_batch 동기 호출 + 캐시 무효화 + 토스트.

    수집 키워드는 페르소나 관심사(interest_tasks + interest_lv3).
    키워드가 없으면 수집은 스킵하고 캐시만 무효화한다.
    수집 실패 시 error 토스트(캐시는 안전하게 무효화 — 다음 렌더가 최신).
    """
    if st.query_params.get("refresh") != "now":
        return False

    # 모든 dm 관련 캐시 무효화 — `_archive_stats_dm` 는 이제 `board_v2._archive_stats()`
    # 위임이므로 그 내부의 `_board_kpis` 60초 캐시도 함께 비워야 좌측 nav 카운트가
    # 즉시 새 수집 결과로 갱신된다 (Phase 2 dedup 회귀 방지).
    from ui import board_v2 as _bv2  # lazy

    for fn in (_dm_stats, _ingest_jobs_html, _hist_html, _news_cards_html, _archive_stats_dm, _bv2._board_kpis):
        if hasattr(fn, "clear"):
            fn.clear()

    # 수집 실행 — 페르소나 관심사 키워드 + 등록된 커스텀 RSS 출처
    try:
        from ui.board_v2 import _collect_keywords_for_persona, _collect_extra_feeds
        from scraping.run_daily import collect_batch
        persona = app_shell.get_persona()
        kws = _collect_keywords_for_persona(persona)
        extra_feeds = _collect_extra_feeds()
        if not kws and not extra_feeds:
            st.session_state["_dm_refresh_toast"] = (
                "warn",
                "ℹ️ 페르소나 관심사가 비어 있어 수집은 건너뛰었어요 — 캐시만 새로 그렸습니다.",
            )
        else:
            report = collect_batch(kws, max_results=10, extra_feeds=extra_feeds)
            n_articles = report.total_articles
            n_files = report.total_files
            n_err = len(report.errors)
            if n_err and n_articles == 0:
                st.session_state["_dm_refresh_toast"] = (
                    "error",
                    f"⚠️ 수집 실패 — 첫 오류: {report.errors[0].get('error','unknown')}",
                )
            else:
                feeds_label = (
                    f", RSS {len(extra_feeds)}건" if extra_feeds else ""
                )
                err_tail = f", 일부 오류 {n_err}건" if n_err else ""
                st.session_state["_dm_refresh_toast"] = (
                    "ok",
                    f"✓ {len(kws)}개 키워드{feeds_label}로 {n_articles}건 수집 "
                    f"({n_files}개 파일){err_tail}.",
                )
    except Exception as exc:
        st.session_state["_dm_refresh_toast"] = (
            "error", f"⚠️ 수집 처리 실패: {type(exc).__name__}: {exc}",
        )

    if "refresh" in st.query_params:
        del st.query_params["refresh"]
    return True


def _render_refresh_toast_if_needed() -> None:
    """직전 새로고침 직후 한 번만 노출되는 inline toast (sticky 안 함).

    payload 는 (kind, message) 튜플 — kind in {"ok","warn","error"}.
    """
    payload = st.session_state.pop("_dm_refresh_toast", None)
    if not payload:
        return
    # 구버전 호환 — True 면 기본 ok 토스트
    if payload is True:
        kind, message = ("ok", "✓ 캐시를 새로 그렸어요.")
    else:
        kind, message = payload
    bg, border, color = {
        "ok":    ("#ECFDF5", "#A7F3D0", "#064E3B"),
        "warn":  ("#FFFBEB", "#FDE68A", "#92400E"),
        "error": ("#FEF2F2", "#FECACA", "#991B1B"),
    }.get(kind, ("#F1F5F9", "#CBD5E1", "#0F172A"))
    safe = _html.escape(message)
    st.html(
        f'<div style="margin: 0 24px 14px; padding: 10px 14px; '
        f'background: {bg}; border: 1px solid {border}; border-radius: 8px; '
        f'font-size: 13px; color: {color}; font-weight: 600;">{safe}</div>'
    )


def _consume_task_def_upload_if_any() -> None:
    """`_do_task_def_ingest` pending → 업로드된 파일로 ingest 실행 → 결과 toast.

    pending 페이로드:
      (filename: str, sheet_name: str | int, bytes_data: bytes)
    """
    payload = st.session_state.pop("_do_task_def_ingest", None)
    if not payload:
        return
    filename, sheet_name, data = payload
    import io
    bio = io.BytesIO(data)
    try:
        result = _ingest.ingest_excel(bio, sheet_name=sheet_name, save_raw=True)
    except Exception as exc:
        st.session_state["_task_def_toast"] = ("error", f"업로드 실패: {type(exc).__name__}: {exc}")
        st.rerun()
        return

    if not result.ok:
        st.session_state["_task_def_toast"] = ("error", " · ".join(result.errors)[:300])
    else:
        # 데이터 관리 캐시 + 보드/인사이트의 _load_tasks 캐시도 invalidate.
        # `_archive_stats_dm` 는 `board_v2._archive_stats()` 위임이라 board 의 _board_kpis 도 비움.
        from ui import board_v2 as _bv2  # lazy
        for fn in (_dm_stats, _ingest_jobs_html, _hist_html, _news_cards_html, _archive_stats_dm, _bv2._board_kpis):
            if hasattr(fn, "clear"):
                fn.clear()
        try:
            from roadmap.query import load_latest as _ll
            if hasattr(_ll, "clear"):
                _ll.clear()
        except Exception:
            pass
        st.session_state["_task_def_toast"] = (
            "ok",
            f"✅ '{filename}' 업로드 완료 — {result.row_count}건 작업 정의 저장됨. 보드·인사이트가 곧 갱신됩니다.",
        )
    st.rerun()


def _render_task_def_toast_if_needed() -> None:
    """업로드 직후 한 번만 노출되는 inline toast."""
    payload = st.session_state.pop("_task_def_toast", None)
    if not payload:
        return
    kind, message = payload
    bg, border, color = {
        "ok":    ("#ECFDF5", "#A7F3D0", "#064E3B"),
        "error": ("#FEF2F2", "#FECACA", "#991B1B"),
    }.get(kind, ("#F1F5F9", "#CBD5E1", "#0F172A"))
    safe = _html.escape(message)
    st.html(
        f"""
        <div style="margin: 0 24px 14px; padding: 10px 14px;
                    background: {bg}; border: 1px solid {border}; border-radius: 8px;
                    font-size: 13px; color: {color}; font-weight: 600;">
          {safe}
        </div>
        """
    )


def _render_task_def_upload() -> None:
    """본문 끝에 추가되는 "📂 작업 정의 데이터 업로드" 섹션.

    파일 업로드 + 시트 선택 + 미리보기 + 업로드 버튼.
    """
    st.html(
        '<div style="margin: 24px 24px 4px; padding: 14px 18px; '
        'background: #fff; border: 1px solid var(--surface-divider); border-radius: 12px;">'
        '<div style="font-size: 18px; font-weight: 800; color: #0F172A; '
        'letter-spacing: -0.01em; margin-bottom: 4px;">📂 작업 정의 데이터 업로드</div>'
        '<div style="font-size: 13px; color: #64748B; line-height: 1.5;">'
        '엑셀(.xlsx) 파일을 올리면 자동으로 정규화 + 검증 후 Parquet 으로 저장됩니다. '
        '컬럼: <b>팀 · 부서 · 분과 · 공정 · 작업 · 세부작업 · 공정정의서(줄글) · 공정정의서(JSON)</b>'
        '</div></div>'
    )

    cur_df = None
    try:
        cur_df = _load_tasks()
    except Exception:
        cur_df = None
    cur_count = int(len(cur_df)) if cur_df is not None and not cur_df.empty else 0
    if cur_count > 0:
        st.caption(f"📊 현재 저장된 작업 정의: **{cur_count}건** (가장 최근 업로드)")
    else:
        st.caption("📊 아직 업로드된 작업 정의가 없어요.")

    uploaded = st.file_uploader(
        "엑셀 파일 선택 (.xlsx)",
        type=["xlsx"],
        key="_task_def_uploader",
        help="신엑셀 형식(분과/공정/JSON) 또는 구엑셀(lv1/lv2/lv3) 모두 자동 인식.",
    )

    if uploaded is None:
        return

    # 시트 미리보기
    try:
        import pandas as _pd
        xl = _pd.ExcelFile(uploaded)
        sheets = xl.sheet_names
        col_a, col_b = st.columns([1, 3])
        with col_a:
            sheet = st.selectbox("시트", sheets, key="_task_def_sheet")
        # 미리보기 5행
        preview = _pd.read_excel(uploaded, sheet_name=sheet, nrows=5, dtype=str).fillna("")
        with col_b:
            st.caption(f"열: {len(preview.columns)}개 · 첫 5행 미리보기")
        st.dataframe(preview, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"엑셀 미리보기 실패: {exc}")
        return

    # PR-5: pending diff 미리보기 단계가 활성화돼있으면 그쪽을 우선 렌더.
    pending = st.session_state.get("_task_def_pending")
    if pending and pending.get("filename") == uploaded.name and pending.get("sheet") == sheet:
        _render_task_def_diff_preview(pending)
        return

    if st.button("📊 변경 사항 미리보기", type="primary", key="_task_def_diff_btn"):
        try:
            uploaded.seek(0)
            data = uploaded.read()
        except Exception as exc:
            st.error(f"파일 읽기 실패: {exc}")
            return
        st.session_state["_task_def_pending"] = {
            "filename": uploaded.name, "sheet": sheet, "data": data,
        }
        st.rerun()


def _compute_pending_diff(data: bytes, sheet: str | int):
    """업로드 바이트 → 정규화 DataFrame → DiffPreview. 모든 예외는 (None, msg)."""
    import io
    import pandas as _pd
    from roadmap.ingest import normalize_columns
    from roadmap.sqlite_sync import compute_diff

    try:
        df_raw = _pd.read_excel(io.BytesIO(data), sheet_name=sheet, dtype=str).fillna("")
    except Exception as exc:
        return None, f"엑셀 읽기 실패: {exc}"
    df = normalize_columns(df_raw)
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return compute_diff(df), None


def _render_task_def_diff_preview(pending: dict) -> None:
    """업로드 적용 전 변경 사항 미리보기 카드 (PR-5).

    pending 구조: {"filename": str, "sheet": str|int, "data": bytes}.
    [취소] / [✅ N건 적용] 버튼 노출. 적용 시 기존 _do_task_def_ingest 경로 재사용.
    """
    diff, err = _compute_pending_diff(pending["data"], pending["sheet"])
    if err:
        st.error(err)
        if st.button("← 다시 선택", key="_task_def_diff_back_btn"):
            st.session_state.pop("_task_def_pending", None)
            st.rerun()
        return

    n_add = len(diff.added)
    n_upd = len(diff.updated)
    n_keep = len(diff.kept)
    n_skip = diff.skipped
    n_apply = diff.total_apply

    # 헤더 카드 — 카운트 요약
    summary_html = (
        '<div style="margin: 18px 24px 8px; padding: 14px 18px; background: #fff; '
        'border: 1px solid var(--surface-divider); border-radius: 12px;">'
        '<div style="font-size: 16px; font-weight: 800; color: #0F172A; '
        'letter-spacing: -0.01em; margin-bottom: 8px;">📊 업로드 미리보기 — 변경 사항</div>'
        f'<div style="font-size: 14px; color: #334155; line-height: 1.8;">'
        f'✅ <b>추가:</b> {n_add}건 &nbsp;·&nbsp; '
        f'⚠️ <b>수정:</b> {n_upd}건 &nbsp;·&nbsp; '
        f'ℹ️ <b>유지 (엑셀에 없는 기존):</b> {n_keep}건'
    )
    if n_skip:
        summary_html += f' &nbsp;·&nbsp; ⛔ <b>제외:</b> {n_skip}건 (공정ID 없음)'
    summary_html += '</div></div>'
    st.html(summary_html)

    # 상세 expand — 적용 대상만 (추가/수정)
    if n_add:
        with st.expander(f"➕ 추가 {n_add}건 보기", expanded=False):
            for pid, name in diff.added[:200]:
                st.markdown(f"- `{_html.escape(pid)}` — {_html.escape(name)}")
            if n_add > 200:
                st.caption(f"… (외 {n_add - 200}건)")
    if n_upd:
        with st.expander(f"✏️ 수정 {n_upd}건 보기", expanded=False):
            for pid, name in diff.updated[:200]:
                st.markdown(f"- `{_html.escape(pid)}` — {_html.escape(name)}")
            if n_upd > 200:
                st.caption(f"… (외 {n_upd - 200}건)")
    if n_keep:
        with st.expander(f"📦 유지될 기존 {n_keep}건 보기", expanded=False):
            st.caption("이번 엑셀에 없지만 그대로 유지됩니다. 삭제하려면 UI 에서 개별 삭제하세요.")
            for pid, name in diff.kept[:200]:
                st.markdown(f"- `{_html.escape(pid)}` — {_html.escape(name)}")
            if n_keep > 200:
                st.caption(f"… (외 {n_keep - 200}건)")

    # 액션 버튼 — 취소 / 적용
    col_a, col_b = st.columns([1, 2])
    with col_a:
        if st.button("← 취소", key="_task_def_diff_cancel_btn"):
            st.session_state.pop("_task_def_pending", None)
            st.rerun()
    with col_b:
        label = f"✅ {n_apply}건 적용" if n_apply else "변경 사항 없음"
        if st.button(label, type="primary", key="_task_def_diff_apply_btn",
                     disabled=(n_apply == 0)):
            st.session_state["_do_task_def_ingest"] = (
                pending["filename"], pending["sheet"], pending["data"],
            )
            st.session_state.pop("_task_def_pending", None)
            st.rerun()


# ── B.5 데이터관리 4 탭 wire (jobs / kw / task / src) ────────────
# PR-A: 2 그룹 × sub-탭 재편. 그룹은 segmented control, sub-탭은 그룹 내부에서만 렌더.
# PR-6: tasks 그룹에 manage sub-탭 추가 (작업 정의 관리 UI).
_DM_TABS = ("jobs", "kw", "task", "manage", "src")
_DM_TAB_LABEL = {
    "jobs": "수집잡 · 뉴스 라이브러리",
    "kw": "키워드",
    "task": "📊 엑셀 업로드",
    "manage": "✏️ 작업 정의 관리",
    "src": "출처 설정",
}

# 2 그룹 정의 — PR-A.
_DM_GROUPS = ("news", "tasks")
_DM_GROUP_LABEL = {"news": "📰 뉴스 데이터", "tasks": "📋 작업 데이터"}
_DM_GROUP_TABS: dict[str, tuple[str, ...]] = {
    "news":  ("jobs", "kw", "src"),
    "tasks": ("task", "manage"),  # PR-6 — manage 신규
}
_DM_GROUP_DEFAULT_TAB = {"news": "jobs", "tasks": "manage"}


def _dm_group_of(tab: str) -> str:
    """sub-탭 → 속한 그룹. 알 수 없으면 'news'."""
    for grp, tabs in _DM_GROUP_TABS.items():
        if tab in tabs:
            return grp
    return "news"


def _dm_resolve_group_and_tab(grp: str | None, tab: str | None) -> tuple[str, str]:
    """URL query → (group, tab) 정규화.

    호환성:
      - tab 만 있고 grp 없으면 → tab 에서 grp 추론 (기존 URL 호환)
      - grp 만 있고 tab 없으면 → 그룹 기본 탭
      - 둘 다 없으면 → ('news', 'jobs')
      - tab 이 grp 와 맞지 않으면 → tab 의 그룹으로 정정
    """
    tab = (tab or "").strip()
    grp = (grp or "").strip()
    if tab and tab not in _DM_TABS:
        tab = ""
    if grp and grp not in _DM_GROUPS:
        grp = ""

    if not tab and not grp:
        return ("news", "jobs")
    if tab and not grp:
        return (_dm_group_of(tab), tab)
    if grp and not tab:
        return (grp, _DM_GROUP_DEFAULT_TAB[grp])
    # 둘 다 있음 — tab 의 그룹이 진실 (사용자가 다른 그룹의 탭을 직접 명시한 경우)
    return (_dm_group_of(tab), tab)
_DM_TAB_ICON_SVG = {
    # 24x24 stroke=#475569 패스 본문(<svg>는 _dm_tabs_html 에서 wrap)
    "jobs": "<polyline points='23 4 23 10 17 10'/><path d='M3.51 9a9 9 0 0114.85-3.36L23 10'/>",
    "kw": "<circle cx='11' cy='11' r='8'/><path d='M21 21l-4.35-4.35'/>",
    "task": "<path d='M9 11l3 3L22 4'/><path d='M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11'/>",
    "manage": "<path d='M12 20h9'/><path d='M16.5 3.5a2.121 2.121 0 113 3L7 19l-4 1 1-4L16.5 3.5z'/>",
    "src": (
        "<circle cx='12' cy='12' r='3'/><path d='M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 008 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.6 15 1.65 1.65 0 003.09 14H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 008 4.6 1.65 1.65 0 009 3.09V3a2 2 0 014 0v.09A1.65 1.65 0 0014 4.6a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9c.16.5.66.91 1.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z'/>"
    ),
}


def _dm_tab_href(tab: str) -> str:
    """탭 선택 URL — `?app_area=🧱+데이터+관리&dm_grp=<grp>&dm_tab=<tab>`.

    그룹 기본 탭 (`jobs`/`task`) 은 `dm_tab` 생략, 그 외에는 명시.
    `dm_grp` 는 항상 명시 (혼동 방지). 단 news 그룹 + jobs 탭은 둘 다 생략 (깨끗한 URL).
    """
    from urllib.parse import quote
    grp = _dm_group_of(tab)
    parts = [f"app_area={quote('🧱 데이터 관리')}"]
    is_default = (grp == "news" and tab == "jobs")
    if not is_default:
        parts.append(f"dm_grp={quote(grp)}")
        if tab != _DM_GROUP_DEFAULT_TAB[grp]:
            parts.append(f"dm_tab={quote(tab)}")
    return "?" + "&".join(parts)


def _dm_group_href(grp: str) -> str:
    """그룹 segmented 선택 URL — 그룹 기본 탭으로 이동."""
    return _dm_tab_href(_DM_GROUP_DEFAULT_TAB.get(grp, "jobs"))


def _dm_groups_html(selected_grp: str) -> str:
    """2 그룹 segmented control — <a> 2개."""
    parts = ['<div class="dm-groups" role="tablist" aria-label="데이터 그룹">']
    for grp in _DM_GROUPS:
        active = " dm-group-active" if grp == selected_grp else ""
        href = _dm_group_href(grp)
        label = _DM_GROUP_LABEL[grp]
        aria_cur = "true" if grp == selected_grp else "false"
        parts.append(
            f'<a class="dm-group{active}" href="{href}" target="_self" '
            f'role="tab" aria-selected="{aria_cur}">{label}</a>'
        )
    parts.append("</div>")
    return "".join(parts)


def _dm_tabs_html(selected_tab: str, dm_stats: dict[str, str | int]) -> str:
    """현재 그룹의 sub-탭만 렌더. 활성 탭에 dm-tab-active."""
    selected_tab = selected_tab if selected_tab in _DM_TABS else "jobs"
    grp = _dm_group_of(selected_tab)
    visible_tabs = _DM_GROUP_TABS[grp]

    parts = ['<div class="dm-tabs">']
    for tab in visible_tabs:
        active = " dm-tab-active" if tab == selected_tab else ""
        href = _dm_tab_href(tab)
        label = _DM_TAB_LABEL[tab]
        icon = _DM_TAB_ICON_SVG[tab]
        # 탭별 count 카운트(jobs 만 동적; 나머지는 비워둠)
        if tab == "jobs":
            cnt_html = (
                f'<span class="dm-tab-cnt">'
                f'{int(dm_stats.get("active_sources", 0) or 0)} 출처 · '
                f'{int(dm_stats.get("today_count", 0) or 0)} 건/일'
                f'</span>'
            )
        else:
            cnt_html = ""
        parts.append(
            f'<a class="dm-tab{active}" href="{href}" target="_self" '
            f'aria-current="{"true" if tab == selected_tab else "false"}">'
            f'<span class="dm-tab-i">'
            f"<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' "
            f"viewBox='0 0 24 24' fill='none' stroke='#475569' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round'>{icon}</svg>"
            f'</span>{label}{cnt_html}</a>'
        )
    parts.append("</div>")
    return "".join(parts)


def _dm_tab_body_html(tab: str, *, persona: Persona | None,
                      dm_stats: dict[str, str | int]) -> str:
    """jobs 가 아닌 탭의 본문 HTML.

    - kw: 페르소나 관심사 + 자동 추출 안내(보드 ⑦ 인계).
    - task: 작업 정의 데이터 안내 카드(실 업로드 위젯은 외부에서 렌더).
    - src: 출처 7일 수집 카운트 + 상태 표.
    """
    if tab == "kw":
        return _dm_kw_body_html(persona)
    if tab == "task":
        return _dm_task_body_html()
    if tab == "manage":
        # PR-6: 본문은 Streamlit 위젯(검색·리스트·폼)으로 render 단계에서 채워짐.
        # 여기서는 헤더 영역만 비워둠 (placeholder div).
        return '<div class="td-manage-placeholder" style="margin: 0 24px;"></div>'
    if tab == "src":
        return _dm_src_body_html(dm_stats)
    return ""


def _dm_kw_body_html(persona: Persona | None) -> str:
    """키워드 탭 본문 — 페르소나 관심사 + 자동 추출 요약 + 보드 ⑦ 인계."""
    from urllib.parse import quote
    persona = persona or Persona()
    user_terms = [
        t for t in (list(persona.interest_tasks or []) + list(persona.interest_lv3 or []))
        if t
    ]
    muted = [m for m in (persona.muted_keywords or []) if m]

    # 자동 추출 top 6 (30일 빈도)
    auto_chips: list[str] = []
    try:
        news_30 = _news_db.load_news_for_days(days=30)
    except Exception:
        news_30 = None
    if news_30 is not None and not news_30.empty:
        try:
            from store import trends as _t
            top_df = _t.top_keywords(news_30, top_n=6 + len(muted))
            rows = [r for _, r in top_df.iterrows() if str(r["keyword"]) not in muted][:6]
            for r in rows:
                kw = str(r["keyword"])
                c = int(r["count"])
                auto_chips.append(
                    f'<span class="dm-kw-chip">'
                    f'<span class="dm-kw-chip-dot"></span>'
                    f'{_html.escape(kw)}'
                    f'<span class="dm-kw-chip-hits">{c}</span>'
                    f'</span>'
                )
        except Exception:
            pass

    user_chips_html = (
        "".join(
            f'<span class="dm-kw-chip dm-kw-chip-user">{_html.escape(t)}</span>'
            for t in user_terms
        )
        if user_terms
        else '<span class="dm-kw-empty">페르소나 관심사가 비어 있어요. 설정에서 추가해 주세요.</span>'
    )
    muted_chips_html = (
        "".join(
            f'<span class="dm-kw-chip dm-kw-chip-muted">{_html.escape(t)}</span>'
            for t in muted
        )
        if muted
        else '<span class="dm-kw-empty">숨김 키워드 없음.</span>'
    )
    auto_chips_html = (
        "".join(auto_chips) if auto_chips
        else '<span class="dm-kw-empty">30일분 수집 후 자동 추출됩니다.</span>'
    )

    board_href = "?app_area=" + quote("📊 오늘의 보드")
    persona_href = "?persona_editor=1"
    return f"""<section class="dm-tab-body dm-kw-body">
      <div class="dm-tb-head">
        <div>
          <div class="dm-sec-eye">키워드 관리</div>
          <h2 class="dm-sec-t">자동 추출 + 페르소나 관심사 + 숨김</h2>
          <p class="dm-tb-desc">
            상세 편집(× 삭제, 즉시 수집)은
            <a class="dm-tb-link" href="{board_href}" target="_self">오늘의 보드 ⑦ 카드</a>에서.
            여기는 현황 요약 + 페르소나 진입.
          </p>
        </div>
      </div>
      <div class="dm-kw-section">
        <div class="dm-kw-section-h">
          ★ SOLA 자동 추출
          <span class="dm-kw-section-meta">최근 30일 빈도 상위</span>
        </div>
        <div class="dm-kw-chips">{auto_chips_html}</div>
      </div>
      <div class="dm-kw-section">
        <div class="dm-kw-section-h">
          ◉ 내가 추가
          <span class="dm-kw-section-meta">페르소나 관심사 기반</span>
        </div>
        <div class="dm-kw-chips">{user_chips_html}</div>
        <a class="dm-tb-cta" href="{persona_href}" target="_self">관심사 편집 →</a>
      </div>
      <div class="dm-kw-section">
        <div class="dm-kw-section-h">
          🔕 숨김 키워드
          <span class="dm-kw-section-meta">자동 추출에서 제외 — 보드 ⑦ × 로 추가</span>
        </div>
        <div class="dm-kw-chips">{muted_chips_html}</div>
      </div>
    </section>"""


def _dm_task_body_html() -> str:
    """작업 정의 탭 본문 — 안내 카드 (실 업로드 위젯은 _render_task_def_upload 가 렌더)."""
    cur_count = 0
    try:
        cur_df = _load_tasks()
        cur_count = int(len(cur_df)) if cur_df is not None and not cur_df.empty else 0
    except Exception:
        pass
    cur_label = f"{cur_count}건" if cur_count else "아직 없음"
    return f"""<section class="dm-tab-body dm-task-body">
      <div class="dm-tb-head">
        <div>
          <div class="dm-sec-eye">작업 정의 데이터</div>
          <h2 class="dm-sec-t">엑셀 업로드 + 검증 + Parquet 저장</h2>
          <p class="dm-tb-desc">
            엑셀(.xlsx)을 올리면 정규화·검증 후 저장됩니다.
            현재 저장: <b>{_html.escape(cur_label)}</b>.
            업로드는 아래 섹션에서 진행해 주세요.
          </p>
        </div>
      </div>
    </section>"""


def _dm_src_body_html(dm_stats: dict[str, str | int]) -> str:
    """출처 설정 탭 본문 — 기본 4 출처 + 커스텀 출처 × 7일 수집 + 활성 토글."""
    from store import sources as src_store

    # 최근 7일 수집 출처별 카운트
    try:
        week = _news_db.load_news_for_days(days=7)
    except Exception:
        week = None
    cnt_map: dict[str, tuple[int, str]] = {}  # source -> (count, last_iso)
    if week is not None and not week.empty and "source" in week.columns:
        grouped = week.groupby("source")
        for src in grouped.groups.keys():
            sub = grouped.get_group(src)
            cnt = int(len(sub))
            last_iso = ""
            for col in ("collected_at", "published_at"):
                if col in sub.columns:
                    last_iso = str(sub[col].dropna().max() or "")
                    if last_iso:
                        break
            cnt_map[str(src)] = (cnt, last_iso)

    disabled = src_store.disabled_set()
    customs = src_store.custom_sources()

    def _gradient(src: str) -> str:
        return _SOURCE_GRADIENTS.get(src, _DEFAULT_GRADIENT)

    def _status_html(cnt: int, is_enabled: bool) -> str:
        if not is_enabled:
            return '<span class="dm-src-st dm-src-st-off">비활성</span>'
        if cnt > 0:
            return '<span class="dm-src-st dm-src-st-ok">OK</span>'
        return '<span class="dm-src-st dm-src-st-warn">7일 무수집</span>'

    def _toggle_link(src: str, is_enabled: bool) -> str:
        href = _src_action_href("toggle", src)
        label = "비활성화" if is_enabled else "활성화"
        return f'<a class="dm-src-act" href="{href}" target="_self">{label}</a>'

    rows_html: list[str] = []
    # 기본 출처 — toggle 가능, 제거 불가
    for src in src_store.DEFAULT_SOURCES:
        is_enabled = src not in disabled
        cnt, last_iso = cnt_map.get(src, (0, ""))
        rows_html.append(
            f'<li class="dm-src-row{" dm-src-row-off" if not is_enabled else ""}">'
            f'<span class="dm-src-mark" style="background:{_gradient(src)};"></span>'
            f'<span class="dm-src-name">{_html.escape(src)}</span>'
            f'<span class="dm-src-cnt">{cnt}건/7일</span>'
            f'<span class="dm-src-last">{_html.escape(last_iso[:16] if last_iso else "—")}</span>'
            f'{_status_html(cnt, is_enabled)}'
            f'{_toggle_link(src, is_enabled)}'
            f'</li>'
        )

    # 커스텀 출처 — toggle 없음(등록=활성), 제거 가능
    for cs in customs:
        cnt, last_iso = cnt_map.get(cs.name, (0, ""))
        remove_href = _src_action_href("remove", cs.name)
        rows_html.append(
            f'<li class="dm-src-row dm-src-row-custom">'
            f'<span class="dm-src-mark" style="background:{_gradient(cs.name)};"></span>'
            f'<span class="dm-src-name">{_html.escape(cs.name)}'
            f'<span class="dm-src-url-mini">{_html.escape(cs.url[:60])}</span></span>'
            f'<span class="dm-src-cnt">{cnt}건/7일</span>'
            f'<span class="dm-src-last">{_html.escape(last_iso[:16] if last_iso else "—")}</span>'
            f'{_status_html(cnt, True)}'
            f'<a class="dm-src-act dm-src-act-rm" href="{remove_href}" target="_self">제거</a>'
            f'</li>'
        )

    # 기타 출처 — 뉴스에 source 로 등장했지만 default/custom 어디에도 없는 ID
    # (scraping 모듈이 'naver'/'google'/'tech' 내부 ID 로 저장한 경우 등).
    custom_names = {c.name for c in customs}
    known = set(src_store.DEFAULT_SOURCES) | custom_names
    others = sorted(s for s in cnt_map.keys() if s not in known)
    for src in others:
        cnt, last_iso = cnt_map.get(src, (0, ""))
        rows_html.append(
            f'<li class="dm-src-row dm-src-row-other">'
            f'<span class="dm-src-mark" style="background:{_gradient(src)};"></span>'
            f'<span class="dm-src-name">{_html.escape(src)}'
            f'<span class="dm-src-url-mini">기타 — 토글 불가</span></span>'
            f'<span class="dm-src-cnt">{cnt}건/7일</span>'
            f'<span class="dm-src-last">{_html.escape(last_iso[:16] if last_iso else "—")}</span>'
            f'{_status_html(cnt, True)}'
            f'<span class="dm-src-act dm-src-act-noop">—</span>'
            f'</li>'
        )

    n_active = len([s for s in src_store.DEFAULT_SOURCES if s not in disabled]) + len(customs)
    return f"""<section class="dm-tab-body dm-src-body">
      <div class="dm-tb-head">
        <div>
          <div class="dm-sec-eye">출처 설정</div>
          <h2 class="dm-sec-t">활성 출처 {n_active}개 · 최근 7일</h2>
          <p class="dm-tb-desc">
            기본 출처는 토글로 활성/비활성을 전환할 수 있어요.
            커스텀 RSS 출처는 아래 폼에서 추가하세요(실 수집 연결은 다음 PR).
          </p>
        </div>
      </div>
      <ul class="dm-src-table">{"".join(rows_html)}</ul>
    </section>"""


def _src_action_href(action: str, src_name: str) -> str:
    """출처 설정 액션 URL — `?dm_tab=src&src_action=toggle|remove&src_name=`."""
    from urllib.parse import quote
    parts = [
        f"app_area={quote('🧱 데이터 관리')}",
        "dm_tab=src",
        f"src_action={quote(action)}",
        f"src_name={quote(src_name)}",
    ]
    return "?" + "&".join(parts)


_SRC_ACTIONS = {"toggle", "remove", "add"}


def _consume_src_action_if_any() -> tuple[str, str] | None:
    """`?src_action=toggle|remove&src_name=` 1회 소비.

    - toggle: 기본 출처 활성/비활성 전환
    - remove: 커스텀 출처 제거
    - add: (Streamlit form 에서 set 한) pending 처리는 별도 path 로
    반환: 성공 시 (action, src_name), 아니면 None.
    """
    action = st.query_params.get("src_action")
    name = (st.query_params.get("src_name", "") or "").strip()
    if action not in _SRC_ACTIONS or not name:
        return None

    try:
        from store import sources as src_store
        if action == "toggle":
            enabled_after = src_store.toggle_disabled(name)
            verb = "활성화" if enabled_after else "비활성화"
            st.session_state["_src_action_toast"] = (
                "ok", f"✅ '{name}' 출처를 {verb}했어요."
            )
        elif action == "remove":
            ok = src_store.remove_custom(name)
            if ok:
                st.session_state["_src_action_toast"] = (
                    "ok", f"✅ '{name}' 커스텀 출처를 제거했어요."
                )
            else:
                st.session_state["_src_action_toast"] = (
                    "ok", f"ℹ️ '{name}' 출처는 등록되어 있지 않아요."
                )
    except Exception as exc:
        st.session_state["_src_action_toast"] = (
            "error", f"⚠️ 처리 실패: {type(exc).__name__}: {exc}",
        )

    for k in ("src_action", "src_name"):
        if k in st.query_params:
            del st.query_params[k]
    return (action, name)


def _render_src_action_toast_if_needed() -> None:
    """출처 액션 직후 한 번만 노출되는 inline toast."""
    payload = st.session_state.pop("_src_action_toast", None)
    if not payload:
        return
    kind, message = payload
    bg, border, color = {
        "ok":    ("#ECFDF5", "#A7F3D0", "#064E3B"),
        "error": ("#FEF2F2", "#FECACA", "#991B1B"),
    }.get(kind, ("#F1F5F9", "#CBD5E1", "#0F172A"))
    safe = _html.escape(message)
    st.html(
        f'<div style="margin: 0 24px 14px; padding: 10px 14px; '
        f'background: {bg}; border: 1px solid {border}; border-radius: 8px; '
        f'font-size: 13px; color: {color}; font-weight: 600;">{safe}</div>'
    )


def _consume_src_add_if_any() -> None:
    """Streamlit 폼 pending payload → 커스텀 출처 add."""
    payload = st.session_state.pop("_do_src_add", None)
    if not payload:
        return
    name, url = payload
    try:
        from store import sources as src_store
        src_store.add_custom(name, url)
        st.session_state["_src_action_toast"] = (
            "ok", f"✅ '{name}' RSS 출처를 등록했어요."
        )
    except ValueError as exc:
        st.session_state["_src_action_toast"] = ("error", f"⚠️ {exc}")
    except Exception as exc:
        st.session_state["_src_action_toast"] = (
            "error", f"⚠️ 처리 실패: {type(exc).__name__}: {exc}"
        )


def _render_src_add_form() -> None:
    """src 탭 전용 Streamlit 폼 — 커스텀 RSS 출처 추가.

    실 수집 wire 는 별도 PR(scraping 모듈 통합 필요).
    """
    st.html(
        '<div style="margin: 18px 24px 4px; padding: 14px 18px; '
        'background: #fff; border: 1px solid var(--surface-divider); border-radius: 12px;">'
        '<div style="font-size: 16px; font-weight: 800; color: #0F172A; '
        'margin-bottom: 4px;">＋ 커스텀 RSS 출처 추가</div>'
        '<div style="font-size: 13px; color: #64748B; line-height: 1.5;">'
        '저장만 됩니다. 실 수집은 후속 PR에서 scraper 통합.'
        '</div></div>'
    )
    col_a, col_b = st.columns([1, 2])
    with col_a:
        name = st.text_input("이름", key="_src_add_name", placeholder="예: 조선해양 e뉴스")
    with col_b:
        url = st.text_input("RSS URL", key="_src_add_url", placeholder="https://example.com/rss")
    if st.button("✅ 출처 등록", type="primary", key="_src_add_btn"):
        st.session_state["_do_src_add"] = (name or "", url or "")
        st.rerun()


def _render_main(dm_stats: dict[str, str | int], *, selected_tab: str = "jobs",
                 persona: Persona | None = None) -> None:
    """data_management_main.html 템플릿 로드 + placeholder 치환.

    Args:
        dm_stats: 헤더 4 stats 데이터.
        selected_tab: 현재 활성 탭 — "jobs" / "kw" / "task" / "src".
            "jobs" 가 아니면 기존 dm-split 은 display:none 으로 숨기고
            탭별 본문 HTML 을 그 자리에 렌더한다.
        persona: 키워드 탭 본문에서 사용 (관심사 chip).
    """
    template = _DM_TEMPLATE.read_text(encoding="utf-8")
    hist = _hist_html()

    if selected_tab == "jobs":
        body_open = ""
        body_close = ""
    else:
        # 기본 split 은 숨기고, 닫는 div 직후에 탭별 본문을 inline 으로 끼워넣는다.
        body_open = '<div style="display:none;" aria-hidden="true">'
        body_close = "</div>" + _dm_tab_body_html(selected_tab, persona=persona,
                                                  dm_stats=dm_stats)

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
        .replace(
            "{{DM_TABS}}",
            _dm_groups_html(_dm_group_of(selected_tab))
            + _dm_tabs_html(selected_tab, dm_stats),
        )
        .replace("{{DM_MAIN_BODY_OPEN}}", body_open)
        .replace("{{DM_MAIN_BODY_CLOSE}}", body_close)
    )
    html_out = _strip_dm_mockups(html_out)
    st.html(html_out)
