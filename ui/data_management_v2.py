"""데이터 관리 — v2 디자인 적용.

헤더 4 stats + 뉴스 라이브러리 카드 (최근 6건) 실데이터 바인딩.
수집잡 5행과 14일 sparkline 은 별도 PR (ingest job tracking + SVG 동적 빌드 필요).
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from roadmap.query import load_latest as _load_tasks
from roadmap import ingest as _ingest
from store import bookmarks as bookmarks_store
from store import news_db as _news_db
from ui import app_shell
from ui import components as _components
from ui._safe import guard
from ui.styles import inject_screen_css
# 순수 프레젠테이션 헬퍼(부작용 없음)는 data_management_render 로 분리.
from ui.data_management_render import (  # noqa: F401 — re-export
    _SOURCE_GRADIENTS,
    _DEFAULT_GRADIENT,
    _news_age_label,
)


_DM_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "data_management_main.html"


@st.cache_data(ttl=60)
def _dm_stats() -> dict[str, str | int]:
    """헤더 4 stats 실데이터.

    Returns dict with str values (formatted for direct template substitution):
      active_sources: '4' — 최근 7일 동안 적어도 1건 수집한 unique source 수
      today_count:    '125' — 오늘 수집 뉴스 row 수
      total_chunks:   '8.4k' — 30일 누적 뉴스 row 수 (human-friendly)
      last_update:    '08:24' — 가장 최근 수집 시각 (없으면 현재 시각)
    """
    today_df = week_df = month_df = None
    with guard("데이터 관리 통계 — 오늘자 로드"):
        today_df = _news_db.load_all_today()
    with guard("데이터 관리 통계 — 주간(7d) 로드"):
        week_df = _news_db.load_news_for_days(days=7)
    with guard("데이터 관리 통계 — 월간(30d) 로드"):
        month_df = _news_db.load_news_for_days(days=30)

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


def _collect_health_li() -> str:
    """최근 수집 런 헬스 — `run_log.latest_run()` 요약 1행 (dm-job li). 런 없으면 빈 문자열.

    cron/수동/보드 어느 경로로 수집했든 마지막 런의 성공·건수·시각·트리거·오류 소스를
    노출 → 매일 수집이 조용히 실패해도 데이터 관리 화면에서 바로 드러난다 (Phase F).
    """
    try:
        from store import run_log
        run = run_log.latest_run()
    except Exception:  # noqa: BLE001
        run = None
    if not run:
        return ""

    ok = bool(run.get("ok"))
    color = "#15803D" if ok else "#B45309"
    badge = "정상" if ok else "오류"
    ts = str(run.get("ts", ""))
    when = ts.split("T")[1][:5] if "T" in ts else (ts[:16] or "—")
    trig_map = {"cron": "자동(cron)", "manual": "수동 수집", "board": "보드 수집"}
    trig = trig_map.get(str(run.get("trigger", "")), str(run.get("trigger", "")) or "—")
    total = int(run.get("total_articles", 0) or 0)
    files = int(run.get("total_files", 0) or 0)
    dur = run.get("duration_s")
    dur_txt = f" · {float(dur):.1f}s" if isinstance(dur, (int, float)) else ""
    err_srcs = [str(s) for s in (run.get("error_sources") or []) if s]
    err_html = (
        f'<div class="dm-job-sub" style="color:#B45309;">⚠ 오류 소스: '
        f'{_html.escape(", ".join(err_srcs))}</div>'
        if err_srcs else ""
    )
    return (
        f'<li class="dm-job" style="border:1px solid var(--surface-divider); '
        f'background:var(--surface-soft);">'
        f'<span class="dm-job-mark" style="background:{color};"></span>'
        f'<div class="dm-job-body">'
        f'<div class="dm-job-name">최근 수집 · '
        f'<span style="color:{color}; font-weight:700;">{badge}</span> '
        f'<span class="dm-job-meta">{total}건 / {files}파일{dur_txt}</span></div>'
        f'<div class="dm-job-sub">{_html.escape(trig)} · {_html.escape(when)} 기준</div>'
        f'{err_html}'
        f'</div>'
        f'<span class="dm-job-time">{_html.escape(when)}</span>'
        f'</li>'
    )


_RUN_TIMELINE_N = 12  # 최근 N회 런
_STALE_HOURS = 24     # 이 시간 넘게 갱신 없으면 'stale' 경고


def _collect_alert_html() -> str:
    """수집이 degraded(최근 런 실패 OR `_STALE_HOURS`+ 갱신 없음)면 상단 경고 배너.

    '수집 헬스' 1행은 조용한 readout 이라 실패/정체를 놓치기 쉬움(개선 백로그 #1).
    런 기록이 없으면(빈 상태) 알림 없음 — 그건 '수집을 시작하세요' 안내가 담당.
    """
    try:
        from store import run_log
        run = run_log.latest_run()
    except Exception:  # noqa: BLE001
        run = None
    if not run:
        return ""

    from datetime import datetime, timezone
    ts = str(run.get("ts", ""))
    ok = bool(run.get("ok"))
    hours = None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except (ValueError, TypeError):
        pass
    stale = hours is not None and hours > _STALE_HOURS

    if ok and not stale:
        return ""  # 정상 + 최근 → 경고 없음

    if not ok:
        errs = [str(s) for s in (run.get("error_sources") or []) if s]
        body = ("최근 수집에 오류가 있었습니다"
                + (f" — 오류 소스: {_html.escape(', '.join(errs))}" if errs else ""))
        color, bg, icon = "var(--semantic-danger)", "rgba(185,28,28,0.10)", "⛔"
    else:  # stale
        body = f"수집이 {int(hours)}시간째 갱신되지 않았습니다 — 자동 수집(cron) 점검이 필요합니다"
        color, bg, icon = "var(--semantic-warning)", "rgba(180,83,9,0.12)", "⚠"

    when = ts.split("T")[1][:5] if "T" in ts else (ts[:16] or "—")
    return (
        f'<div class="dm-collect-alert" style="display:flex; align-items:center; gap:10px; '
        f'margin:0 0 14px; padding:11px 16px; background:{bg}; '
        f'border:1px solid {color}; border-radius:10px;">'
        f'<span style="font-size:16px; flex-shrink:0;">{icon}</span>'
        f'<div style="flex:1; font-size:13.5px; color:{color}; font-weight:600; line-height:1.45;">'
        f'{body}.<span style="color:var(--text-muted); font-weight:500;"> · 마지막 런 {_html.escape(when)}</span>'
        f'</div></div>'
    )


def _run_when_parts(ts: str) -> tuple[str, str]:
    """ISO ts → (MM-DD, HH:MM). 잘린 문자열도 안전하게."""
    ts = str(ts or "")
    date = ts[5:10] if len(ts) >= 10 else (ts or "—")
    time = ts[11:16] if len(ts) >= 16 and ts[10:11] == "T" else ""
    return date, time


def _run_timeline_html() -> str:
    """최근 N회 수집 런 미니 타임라인 — `run_log` 기반 (왼쪽=과거, 오른쪽=최신).

    각 셀 높이=기사량(상대), 색=성공(초록)/오류(주황). 헬스 1행이 '마지막 런'만
    보여주는 것을 보완해 런 cadence·연속 실패 패턴을 한눈에 드러낸다 (Phase F 고도화).
    런 기록이 없으면 빈 문자열(기존 동작 무변경).
    """
    try:
        from store import run_log
        runs = run_log.load_runs(limit=_RUN_TIMELINE_N)
    except Exception:  # noqa: BLE001
        runs = []
    if not runs:
        return ""

    runs = list(reversed(runs))  # load_runs 는 최신 우선 → 시간순(과거→최신)으로
    counts = [int(r.get("total_articles", 0) or 0) for r in runs]
    max_val = max(counts) if any(counts) else 1
    ok_count = sum(1 for r in runs if r.get("ok"))
    trig_map = {"cron": "자동", "manual": "수동", "board": "보드"}

    cells: list[str] = []
    for r in runs:
        cnt = int(r.get("total_articles", 0) or 0)
        ok = bool(r.get("ok"))
        color = "var(--semantic-success)" if ok else "var(--semantic-warning)"
        # 막대 높이 %: 기사량 비례, 0건이어도 '런은 있었음'을 보이도록 최소 8%.
        pct = max(round(cnt / max_val * 100), 8) if cnt > 0 else 8
        date, time = _run_when_parts(r.get("ts", ""))
        trig = trig_map.get(str(r.get("trigger", "")), str(r.get("trigger", "")) or "—")
        title = f"{trig} · {date} {time} · {cnt}건 · {'정상' if ok else '오류'}"
        cells.append(
            f'<span class="dm-run-cell" title="{_html.escape(title)}">'
            f'<span class="dm-run-fill" style="height:{pct}%; background:{color};"></span>'
            f'</span>'
        )

    old_date, _ = _run_when_parts(runs[0].get("ts", ""))
    new_date, new_time = _run_when_parts(runs[-1].get("ts", ""))
    latest_label = f"최신 {new_date} {new_time}".strip()
    return (
        '<div class="dm-runs">'
        '<div class="dm-hist-head">'
        '<span class="dm-hist-t">최근 수집 런</span>'
        f'<span class="dm-hist-meta">{ok_count}/{len(runs)} 정상</span>'
        '</div>'
        f'<div class="dm-run-track">{"".join(cells)}</div>'
        '<div class="dm-hist-x">'
        f'<span>{_html.escape(old_date)}</span>'
        f'<span>{_html.escape(latest_label)}</span>'
        '</div>'
        '</div>'
    )


@st.cache_data(ttl=60)
def _ingest_jobs_html() -> str:
    """오늘의 수집잡 — 최근 런 헬스 + source 별 카운트 → dm-job 행 빌드.

    헬스 1행은 `run_log.latest_run()`(실제 수집 런 기록), 그 아래 행들은 news_db 의
    source 별 그룹 카운트(오늘자). 실시간 진행 상태 트래킹은 후속.
    """
    health = _collect_health_li()
    today_df = None
    with guard("수집잡 — 오늘자 로드"):
        today_df = _news_db.load_all_today()

    if today_df is None or today_df.empty:
        # display:block 로 .dm-job 의 grid(5px 1fr auto) 를 무력화 — 안 그러면 빈 문구가
        # 5px 첫 칸에 갇혀 글자마다 줄바꿈됨. word-break:keep-all 로 단어 단위 줄바꿈.
        return health + ('<li class="dm-job" style="display:block; word-break:keep-all; '
                'border:1px dashed var(--surface-divider); '
                'padding:18px 14px; text-align:center; color: var(--text-muted); '
                'font-size: 14px; line-height:1.6;">'
                '오늘 실행된 수집잡이 없습니다.<br>'
                '<span style="font-size:12.5px;">우측 상단 [지금 뉴스 수집] 으로 수집을 시작하세요</span>'
                '</li>')

    if "source" not in today_df.columns:
        return health

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
    return health + "\n".join(parts)


def _runstatus_strip_html(days: int = 14) -> str:
    """14일 sparkline 아래 일별 수집 런 성공/실패 스트립 — run_log 기반.

    각 칸: 성공(초록)/실패(주황)/런 없음(divider). 런 기록이 하나도 없으면 빈
    문자열(기존 화면 무변경). hover 로 날짜·상태.
    """
    try:
        from store import run_log
        statuses = run_log.daily_status(days=days)
    except Exception:  # noqa: BLE001
        statuses = [None] * days
    if not any(statuses):
        return ""  # 아직 런 기록 없음 → 스트립 숨김

    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone.utc).date()
    color = {"ok": "var(--semantic-success)", "fail": "var(--semantic-warning)"}
    label = {"ok": "정상", "fail": "오류"}
    cells = []
    for i, sstat in enumerate(statuses):
        day = today - timedelta(days=days - 1 - i)  # i=0 가장 오래, 마지막=오늘
        title = f"{day:%m-%d}: {label.get(sstat, '런 없음')}"
        bg = color.get(sstat, "var(--surface-divider)")
        cells.append(
            f'<span class="dm-runstatus-cell" style="background:{bg};" '
            f'title="{_html.escape(title)}"></span>'
        )
    return f'<div class="dm-runstatus">{"".join(cells)}</div>'


@st.cache_data(ttl=60)
def _hist_html(dark: bool = False) -> dict[str, str]:
    """14일 수집량 sparkline + head/foot 라벨 HTML.

    SVG 는 img src='data:image/svg+xml,...' 형식이라 큰따옴표 escape 필요 →
    src 내부는 모두 단일 따옴표.
    """
    hist_df = None
    with guard("14일 sparkline — 로드"):
        hist_df = _news_db.load_news_for_days(days=14)

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
        # SVG 는 data-URI img 라 CSS 변수를 못 쓴다 → 테마별 색을 직접 분기.
        if is_today:
            fill = "#60A5FA" if dark else "#2563EB"
        else:
            fill = "#475569" if dark else "#CBD5E1"
        bars.append(f"<rect x='{x}' y='{y}' width='16' height='{h}' fill='{fill}' rx='2'/>")

    baseline = "#334155" if dark else "#E5E7EB"
    svg_inner = (
        f"<line x1='0' y1='50' x2='280' y2='50' stroke='{baseline}' stroke-dasharray='2 3'/>"
        + "".join(bars)
    )
    # st.html 은 인라인 <svg> 를 sanitize 로 제거하므로 <img> 로 렌더한다. 단,
    # `;utf8,` 비인코딩 data-URI 는 색상값의 '#'(#2563EB) 가 fragment 로 잘려 깨졌다
    # → URL 인코딩(quote)된 data-URI 로 '#'→%23 등 처리해 정상 표시.
    from urllib.parse import quote as _q
    svg_doc = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 280 70' "
        f"preserveAspectRatio='none'>{svg_inner}</svg>"
    )
    svg_img = (
        f'<img src="data:image/svg+xml,{_q(svg_doc)}" class="dm-hist-chart" '
        'style="width:100%; height:60px; display:block;" alt="14일 수집량 차트" />'
    )

    # 볼륨 바 아래 일별 '수집 런 성공/실패' 스트립을 겹친다 (run_log 기반).
    # 볼륨(news_db)은 "몇 건 쌓였나", 이 스트립은 "그날 런이 돌았고 성공했나" →
    # cron 이 조용히 실패한 날(볼륨 0 이면서 fail/런없음)을 한 줄로 구분.
    svg_img += _runstatus_strip_html()

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
    return {"head": head_html, "svg": svg_img, "foot": foot_html, "runs": _run_timeline_html()}


# 상단 토픽 검색 세션 키 + 카드/표 검색 대상 컬럼(카드 브라우저가 사용).
_NEWS_SEARCH_KEY = "_news_search_q"
_NEWS_SEARCH_COLS = ("title", "content", "summary", "keywords")


def _consume_news_search_clear_if_any() -> None:
    """`?dm_clear_q=1` → 상단 검색 해제: `_news_search_q`·입력 위젯(`_topbar_q`) 비우고 rerun.

    입력 위젯 값은 위젯 인스턴스화 **전**에만 세팅 가능하므로 render_topbar 호출 전에 실행.
    """
    if not st.query_params.get("dm_clear_q"):
        return
    st.session_state[_NEWS_SEARCH_KEY] = ""
    st.session_state["_topbar_q"] = ""
    st.session_state["_topbar_q_seen"] = ""   # 변화감지 시드도 리셋(해제 후 재제출 방지)
    if "dm_clear_q" in st.query_params:
        del st.query_params["dm_clear_q"]
    st.rerun()


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


def chat_context_block_collect(persona: Persona) -> str:
    """뉴스 수집 화면이 보여주는 모든 데이터를 LLM 컨텍스트로 packaging.

    페르소나 비의존(헤더 stats·추이·출처 분포·최근 기사) → 본문은 60s 캐시
    (`_chat_context_collect_cached`). 직전엔 매 rerun 뉴스 윈도우 4회 로드였다.
    """
    return _chat_context_collect_cached()


@st.cache_data(ttl=60)
def _chat_context_collect_cached() -> str:
    """뉴스 수집 채팅 컨텍스트 본문 — 헤더 4 stats + 14일 추이 + 최근 6건 + 출처 분포."""
    parts: list[str] = ["--- 현재 화면: 뉴스 수집 (🗞) ---"]

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


def chat_context_block_taskdef(persona: Persona) -> str:
    """작업 정의 화면 컨텍스트 — 등록 정의 수·부서 분포·최근 정의 목록."""
    parts: list[str] = ["--- 현재 화면: 작업 정의 (📋) ---"]
    try:
        from collections import Counter
        from store import task_defs_db
        rows = task_defs_db.list_all()
        s = _taskdef_stats()
        parts.append(
            f"작업 정의 현황: 등록 {s['defs']}건 · 부서 {s['depts']}개 · "
            f"마지막 갱신 {s['last_update']}"
        )
        dept_counts = Counter(
            ((r.get("dept") or "").strip() or "미지정") for r in rows
        )
        if dept_counts:
            parts.append("부서별 작업 정의 수:")
            for d, c in dept_counts.most_common(8):
                parts.append(f"  - {d}: {int(c)}건")
        if rows:
            parts.append("최근 작업 정의 (최대 6건):")
            for r in rows[:6]:
                chain = " · ".join(
                    p for p in (r.get("dept"), r.get("process"), r.get("task")) if p
                )
                if chain:
                    parts.append(f"  - {chain}")
    except Exception:
        pass
    return "\n".join(parts)


# ════════════════════════════════════════════════════════════
#  뉴스 수집 개편 — 카테고리 카드 브라우저 + 기사 모달 + 설정 서브뷰
# ════════════════════════════════════════════════════════════
#
# 메인(카드뷰): 수집 현황 요약(헤더) → 액션바([🔄 지금 수집][⚙ 수집 설정]) →
#   대분류 탭(키워드/포탈) + 출처칩 + 사진 카드(제목·본문 일부). 카드 클릭 →
#   ?news=<link> → 기사 모달(본문 전체 + 원본 링크).
# 설정(서브뷰): 키워드 관리 + 포탈(출처) 관리 + 수집 실행·이력 상세.
# (구 뉴스 라이브러리 필터 폼·3탭 레이아웃은 #133 재설계로 제거됨 — 상단 검색이 대체.)

# 대분류 — 키워드(검색 기반: naver/google) vs 포탈(사이트 피드: tech + 커스텀 RSS)
_SC_KEYWORD_SOURCES: frozenset[str] = frozenset({"naver", "google"})
_SC_SOURCE_LABEL: dict[str, str] = {"naver": "네이버", "google": "구글"}
_SC_CATS: tuple[str, ...] = ("keyword", "portal")
_SC_CAT_LABEL: dict[str, str] = {"keyword": "🔑 키워드 뉴스", "portal": "🏛 포탈 뉴스"}
_SC_BROWSE_DAYS = 30      # 카드 브라우저가 훑는 기간
_SC_MAX_CARDS = 24        # 카테고리/채널당 최대 카드 수(카드별 위젯이라 과도 방지)
_SC_ALL_CHANNEL = "전체"


def _news_category_of(source: str) -> str:
    """source 값 → 대분류('keyword'|'portal'). naver/google=키워드, 그 외=포탈."""
    return "keyword" if str(source or "").strip() in _SC_KEYWORD_SOURCES else "portal"


def _news_channel_of(source: str, press: str = "") -> str:
    """출처칩 라벨 — 키워드는 네이버/구글, 포탈은 매체명(press) 또는 source(커스텀)."""
    s = str(source or "").strip()
    if s in _SC_SOURCE_LABEL:
        return _SC_SOURCE_LABEL[s]
    p = str(press or "").strip()
    return p or s or "기타"


@st.cache_data(ttl=60)
def _sc_browse_records() -> list[dict]:
    """최근 N일 뉴스 → 대분류(_cat)·출처칩(_chan) 주석 + 최신순 record 리스트(캐시).

    카드 그리드·출처칩·모달이 공유한다. 수집/업로드 시 `.clear()` 로 무효화.
    """
    try:
        df = _news_db.load_news_for_days(days=_SC_BROWSE_DAYS)
    except Exception:
        df = None
    if df is None or df.empty:
        return []
    sort_col = ("collected_at" if "collected_at" in df.columns
                else "published_at" if "published_at" in df.columns else None)
    if sort_col:
        df = df.sort_values(sort_col, ascending=False)
    recs = df.to_dict("records")
    for r in recs:
        r["_cat"] = _news_category_of(r.get("source", ""))
        r["_chan"] = _news_channel_of(r.get("source", ""), r.get("press", ""))
    return recs


def _sc_channels(cat: str) -> list[str]:
    """해당 대분류에 실제로 수집된 출처칩 목록(등장순, 중복 제외)."""
    out: list[str] = []
    for r in _sc_browse_records():
        if r.get("_cat") == cat:
            ch = r.get("_chan")
            if ch and ch not in out:
                out.append(ch)
    return out


def _sc_filtered_records(cat: str, channel: str, q: str) -> list[dict]:
    """대분류·출처칩·상단 검색어로 좁힌 record 리스트(순수). 카드 그리드·표 공용."""
    recs = [r for r in _sc_browse_records() if r.get("_cat") == cat]
    if channel and channel != _SC_ALL_CHANNEL:
        recs = [r for r in recs if r.get("_chan") == channel]
    q = (q or "").strip().lower()
    if q:
        recs = [
            r for r in recs
            if any(q in str(r.get(c, "") or "").lower() for c in _NEWS_SEARCH_COLS)
        ]
    return recs


def _news_body_src(row: dict, keys: tuple[str, ...]) -> str:
    """본문 노출용 텍스트 — `keys` 순서로 고르되 '제목 반복뿐'인 값은 건너뛴다.

    구글 RSS description(=summary)은 태그를 벗기면 '제목(·언론사)'만 남아, 카드/표/
    모달 본문 자리에 제목이 두 번 보이던 문제 방어. 신규 수집은 google.search 가
    소스에서 비우지만, 이미 DB 에 저장된 과거 데이터를 위해 렌더에서도 거른다.
    """
    title = " ".join(str(row.get("title") or "").split())
    for key in keys:
        # 과거 수집분 content 는 '제목\n본문' 형태가 있어 라인 단위로 제목 라인을 제거.
        lines = [" ".join(ln.split()) for ln in str(row.get(key) or "").splitlines()]
        val = " ".join(ln for ln in lines if ln and ln != title)
        if not val:
            continue
        if title and title in val and len(val) <= len(title) + 40:
            continue  # '제목 (+언론사)' 한 줄 반복뿐 — 본문 가치 없음
        return val
    return ""


def _https_img(url: str) -> str:
    """렌더용 이미지 URL — http:// 는 https 로 승격(https 앱에서 혼합콘텐츠 차단 방지)."""
    u = (url or "").strip()
    return "https://" + u[7:] if u[:7].lower() == "http://" else u


def _sc_card_visual_html(row: dict) -> str:
    """카드 시각(사진+메타+제목+본문 일부). 클릭은 위에 겹친 투명 버튼이 처리 → 앵커 없음."""
    title = _html.escape(str(row.get("title") or "(제목 없음)"))
    img = _https_img(str(row.get("image_url", "") or ""))
    body_src = _news_body_src(row, ("summary_llm", "summary", "content"))
    excerpt = (_html.escape(body_src[:110] + ("…" if len(body_src) > 110 else ""))
               if body_src else "")
    source = str(row.get("source", "") or "")
    chan = _html.escape(_news_channel_of(source, row.get("press", "")))
    grad = _SOURCE_GRADIENTS.get(source, _DEFAULT_GRADIENT)
    when = str(row.get("collected_at") or row.get("published_at") or "")
    age = _html.escape(_news_age_label(when))
    # 이미지: http(s) 스킴만 허용(XSS/data: 방어), 없으면 그라데이션 플레이스홀더.
    if img[:4].lower() == "http":
        img_block = (
            f'<div class="sc-card-img" style="background:{grad};">'
            f'<img src="{_html.escape(img, quote=True)}" loading="lazy" '
            f'referrerpolicy="no-referrer" alt=""></div>'
        )
    else:
        img_block = f'<div class="sc-card-img sc-card-img-ph" style="background:{grad};"></div>'
    return (
        f'<div class="sc-card">{img_block}'
        f'<div class="sc-card-body">'
        f'<div class="sc-card-meta">'
        f'<span class="sc-card-src"><span class="sc-card-dot" style="background:{grad};"></span>{chan}</span>'
        f'<span class="sc-card-age">{age}</span></div>'
        f'<div class="sc-card-h">{title}</div>'
        + (f'<div class="sc-card-p">{excerpt}</div>' if excerpt else "")
        + '</div></div>'
    )


def _sc_empty_html(q: str = "") -> str:
    msg = (f'“{_html.escape(q)}” 검색 결과가 없어요.' if q
           else "이 카테고리에 수집된 뉴스가 아직 없어요.")
    return (
        f'<div class="sc-empty">{msg}<br>'
        '<span class="sc-empty-sub">상단 [🔄 지금 뉴스 수집]으로 수집을 시작하거나 '
        '다른 탭/출처를 선택하세요.</span></div>'
    )


def _render_card_grid(cat: str, channel: str, q: str) -> None:
    """사진 카드 그리드 — 카드마다 컨테이너(시각 HTML) + 투명 오버레이 버튼.

    카드 클릭은 오버레이 st.button(소켓 rerun)이 받아 `_sc_open_news` 를 세팅 → 기사
    모달이 뜬다. **문서 전체 reload(흰 깜빡임) 없이** 모달이 열린다(앵커 제거).
    """
    recs = _sc_filtered_records(cat, channel, q)[:_SC_MAX_CARDS]
    if not recs:
        st.html(_components.prepare_screen_html(_sc_empty_html(q)))
        return
    for base in range(0, len(recs), 3):
        cols = st.columns(3, gap="small")
        for j, rec in enumerate(recs[base:base + 3]):
            i = base + j
            with cols[j]:
                with st.container(key=f"sc_card_{i}"):
                    st.html(_components.prepare_screen_html(_sc_card_visual_html(rec)))
                    if st.button(
                        "기사 보기", key=f"sc_open_{i}", use_container_width=True,
                    ):
                        st.session_state["_sc_open_news"] = str(rec.get("link") or "")
                        st.rerun()


def _render_news_table(q: str) -> None:
    """📋 데이터 표 — 수집한 모든 뉴스를 표로(사진·제목·본문·링크). 행 클릭 시 기사 모달.

    `st.dataframe(on_select="rerun", selection_mode="single-row")` 로 행을 선택하면
    해당 기사 모달이 뜬다(reload 없는 소켓 rerun). 닫은 직후 같은 선택이 남아 모달이
    재오픈되는 루프는 `_sc_table_sel`(직전 처리한 link) 가드로 막는다.
    """
    import pandas as _pd
    recs = _sc_browse_records()
    ql = (q or "").strip().lower()
    if ql:
        recs = [
            r for r in recs
            if any(ql in str(r.get(c, "") or "").lower() for c in _NEWS_SEARCH_COLS)
        ]
    if not recs:
        st.html(_components.prepare_screen_html(_sc_empty_html(q)))
        return
    rows = []
    for r in recs:
        when = str(r.get("collected_at") or r.get("published_at") or "")
        body = _news_body_src(r, ("content", "summary_llm", "summary"))
        rows.append({
            "사진": _https_img(str(r.get("image_url", "") or "")),
            "제목": str(r.get("title", "") or ""),
            "본문": (body[:280] + "…") if len(body) > 280 else body,
            "대분류": _SC_CAT_LABEL.get(str(r.get("_cat", "")), ""),
            "출처": str(r.get("_chan", "") or ""),
            "수집": _news_age_label(when) or when[:16],
            "키워드": str(r.get("keywords_llm") or r.get("keywords") or ""),
            "링크": str(r.get("link", "") or ""),
        })
    df = _pd.DataFrame(rows)
    with st.container(key="sc_table"):
        st.caption(
            f"수집한 뉴스 전체 {len(df)}건 · **행을 클릭하면 전체 내용을 모달로** 봅니다 "
            "(상단 검색으로 좁힘)."
        )
        event = st.dataframe(
            df, use_container_width=True, hide_index=True, height=560,
            key="sc_table_df", on_select="rerun", selection_mode="single-row",
            column_config={
                "사진": st.column_config.ImageColumn("사진", width="small"),
                "제목": st.column_config.TextColumn("제목", width="medium"),
                "본문": st.column_config.TextColumn("본문", width="large"),
                "키워드": st.column_config.TextColumn("키워드", width="small"),
                "링크": st.column_config.LinkColumn("링크", display_text="원문 ↗", width="small"),
            },
        )
    # 행 선택 → 기사 모달(직전 처리한 link 와 다를 때만 → 닫은 뒤 재오픈 루프 방지)
    try:
        sel_rows = list(event.selection.rows) if (event and event.selection) else []
    except Exception:  # noqa: BLE001
        sel_rows = []
    if sel_rows:
        idx = sel_rows[0]
        if 0 <= idx < len(recs):
            link = str(recs[idx].get("link") or "")
            if link and st.session_state.get("_sc_table_sel") != link:
                st.session_state["_sc_table_sel"] = link
                st.session_state["_sc_open_news"] = link
                st.rerun()


_SC_MODES: tuple[str, ...] = ("cards", "table")
_SC_MODE_LABEL: dict[str, str] = {"cards": "🃏 카드", "table": "📋 데이터 표"}


def _render_news_browser(persona) -> None:
    """보기 전환(카드/표) + 카드뷰(대분류 탭 + 출처칩 + 사진 카드 그리드).

    카드 클릭은 오버레이 버튼(소켓 rerun)이라 reload 없이 기사 모달이 뜬다. 데이터
    표는 수집한 모든 뉴스를 표로 본다. 상단 검색어가 있으면 둘 다 함께 좁힌다.
    """
    q = str(st.session_state.get(_NEWS_SEARCH_KEY, "") or "").strip()

    # 보기 모드 — 카드 / 데이터 표
    if st.session_state.get("sc_browse_mode") not in _SC_MODES:
        st.session_state["sc_browse_mode"] = _SC_MODES[0]
    with st.container(key="sc_mode_tabs"):
        mode = st.segmented_control(
            "보기", list(_SC_MODES), format_func=lambda m: _SC_MODE_LABEL[m],
            key="sc_browse_mode", label_visibility="collapsed",
        ) or st.session_state["sc_browse_mode"]
    if mode == "table":
        _render_news_table(q)
        return

    # 카드뷰 — 대분류 탭
    if st.session_state.get("sc_news_cat") not in _SC_CATS:
        st.session_state["sc_news_cat"] = _SC_CATS[0]
    with st.container(key="sc_cat_tabs"):
        cat = st.segmented_control(
            "뉴스 카테고리", list(_SC_CATS),
            format_func=lambda c: _SC_CAT_LABEL[c],
            key="sc_news_cat", label_visibility="collapsed",
        ) or st.session_state["sc_news_cat"]
    if cat not in _SC_CATS:
        cat = _SC_CATS[0]

    # 출처칩 — 대분류별로 따로 기억(키에 cat 포함). 채널이 없으면 칩 생략.
    channels = _sc_channels(cat)
    chan = _SC_ALL_CHANNEL
    if channels:
        chan_opts = [_SC_ALL_CHANNEL] + channels
        chan_key = f"sc_chan_{cat}"
        if st.session_state.get(chan_key) not in chan_opts:
            st.session_state[chan_key] = _SC_ALL_CHANNEL
        with st.container(key="sc_chan_chips"):
            chan = st.segmented_control(
                "출처", chan_opts, key=chan_key, label_visibility="collapsed",
            ) or st.session_state[chan_key]
        if chan not in chan_opts:
            chan = _SC_ALL_CHANNEL

    _render_card_grid(cat, chan, q)


@st.fragment
def _render_browse_zone(persona) -> None:
    """카드/표 브라우저 + 기사 모달 — 부분 rerun 경계(@st.fragment).

    보기 모드·대분류 탭·출처칩 전환, 카드 [기사 보기], 표 행 선택, 모달 ✕ 닫기가
    모두 이 fragment 안 위젯이라 **앱 전체 스크립트(topbar·사이드바·우측 채팅)를
    재실행하지 않고 이 구역만** 다시 그린다 → 클릭 반응이 즉각적. 상단 검색·수집
    실행·설정 토글은 fragment 밖이므로 기존대로 앱 전체 rerun.
    """
    _render_news_browser(persona)
    _render_news_modal_if_open()


def _render_collect_actionbar() -> None:
    """메인 카드뷰 액션바 — [🔄 지금 뉴스 수집] + [⚙ 수집 설정] (소켓 rerun).

    수집 버튼은 `_sc_collect_modal_pending` 플래그만 세팅 → 다음 run 에서
    수집 현황 모달(`_render_collect_modal_if_open`)이 떠서 진행·결과를 보여준다.
    """
    with st.container(key="sc_actionbar"):
        c1, c2, _sp = st.columns([1.3, 1, 3])
        with c1:
            if st.button(
                "🔄 지금 뉴스 수집", key="_dm_collect_btn", type="primary",
                use_container_width=True,
                help="페르소나 관심사 키워드(없으면 자동화·AI)로 지금 뉴스를 수집하고 화면을 새로 그립니다.",
            ):
                st.session_state["_sc_collect_modal_pending"] = True
                st.rerun()
        with c2:
            if st.button(
                "⚙ 수집 설정", key="_sc_settings_btn", use_container_width=True,
                help="키워드·포탈(출처) 설정과 수집 이력 상세를 봅니다.",
            ):
                st.session_state["sc_collect_view"] = "settings"
                st.rerun()


def _sc_history_html() -> str:
    """설정 서브뷰 하단 — 오늘의 수집잡 + 14일 추이 + 런 타임라인(기존 빌더 재사용)."""
    from store import ui_prefs as _uiprefs
    hist = _hist_html(_uiprefs.load().get("theme") == "dark")
    jobs = _ingest_jobs_html()
    return (
        '<div class="dm-shell"><section class="dm-jobs">'
        '<div class="dm-jobs-head"><div>'
        '<div class="dm-sec-eye">수집 이력</div>'
        '<h2 class="dm-sec-t">오늘의 수집잡 · 14일 추이</h2>'
        '</div></div>'
        f'<ul class="dm-job-list">{jobs}</ul>'
        '<div class="dm-history">'
        f'{hist["head"]}{hist["svg"]}{hist["foot"]}{hist["runs"]}'
        '</div></section></div>'
    )


def _render_collect_settings(dm_stats: dict[str, str | int], persona) -> None:
    """⚙ 수집 설정 서브뷰 — 키워드 + 포탈(출처) + 수집 실행·이력 + 기사 URL 진단."""
    _render_dm_header(dm_stats)
    with st.container(key="sc_settings_back"):
        if st.button("← 뉴스 목록", key="_sc_back_btn"):
            st.session_state["sc_collect_view"] = "cards"
            st.rerun()
    # TLS 위장 폴백(curl_cffi) 미설치 경고 — thebell 류 WAF 사이트 수집 막힘 안내
    _render_curl_cffi_banner()
    # 키워드 설정(현황 요약 + 페르소나 진입)
    st.html(_components.prepare_screen_html(_dm_kw_body_html(persona)))
    # 포탈/출처 설정 — 기본 토글 + 커스텀 RSS 추가
    _render_src_table(dm_stats)
    _render_src_add_form()
    # 수집 실행(설정에서도 가능) + 이력 상세 + 런 결과 재열람([보기] → 수집 현황 모달)
    _render_collect_button()
    st.html(_components.prepare_screen_html(_sc_history_html()))
    _render_run_history_view_buttons()
    # 🔬 기사 URL 진단 — 본문/사진 미수집 원인(차단 단계)을 앱 안에서 확인
    _render_diagnose_card()


# ── 🔬 기사 URL 진단 (수집 설정 서브뷰) ───────────────────────

def _render_curl_cffi_banner() -> None:
    """수집 설정 상단 안내 1줄 — curl_cffi(TLS 위장 폴백) 미설치 시에만 표시."""
    from scraping.diagnose import curl_cffi_available
    if not curl_cffi_available():
        st.warning("⚠ TLS 위장 폴백 비활성 — `curl_cffi` 미설치. thebell 등 WAF 차단 "
                   "사이트의 본문·사진 수집이 막힐 수 있습니다. requirements 재설치 필요.")


def _consume_diag_pending_if_any() -> bool:
    """`_sc_diag_pending` 1회 소비 → diagnose() 실행(실 네트워크 호출) →
    결과를 `sc_diag_result` 세션에 저장(rerun 에도 유지). 소비했으면 True."""
    if not st.session_state.pop("_sc_diag_pending", None):
        return False
    target = str(st.session_state.get("sc_diag_url") or "").strip()
    if not target.startswith("http"):
        st.session_state["sc_diag_result"] = {
            "error": "http(s):// 로 시작하는 기사 URL 을 입력하세요."}
        return True
    from scraping.diagnose import diagnose as _diagnose
    try:
        st.session_state["sc_diag_result"] = _diagnose(target)
    except Exception as e:  # noqa: BLE001 — 진단 실패도 카드에 그대로 보여준다
        st.session_state["sc_diag_result"] = {"error": f"{type(e).__name__}: {e}"}
    return True


def _diag_step_md(step: dict) -> str:
    """진단 단계 1줄 markdown — 성공 초록 / 차단·실패 빨강 / 생략 회색."""
    label = _html.escape(str(step.get("label", "")))
    if step.get("skipped"):
        return f"- {label} — :gray[생략 (이전 단계 성공)]"
    if step.get("error"):
        return f"- {label} — :red[**실패**] · {_html.escape(str(step['error']))}"
    status = step.get("status")
    if status is None:
        return f"- {label} — :gray[미실행]"
    color = "green" if step.get("ok") else "red"
    return (f"- {label} — :{color}[**HTTP {int(status)}**] · "
            f"{int(step.get('length') or 0):,}자")


def _diag_image_md(cand: dict, kind: str) -> str:
    """이미지 후보 1줄 markdown — junk 판정 + 출처(셀렉터/속성) + URL(escape)."""
    badge = ":orange[JUNK]" if cand.get("junk") else ":green[OK]"
    src = _html.escape(str(cand.get("selector") or cand.get("attr") or kind))
    url = _html.escape(str(cand.get("url") or "")[:90])
    return f"- {badge} `{src}` — {url}"


def _render_diag_result(rep: dict) -> None:
    """diagnose() 결과 dict → 단계별 표시. 실패 단계는 빨강으로 강조."""
    st.markdown("**요청 단계**")
    for step in rep.get("steps", []):
        st.markdown(_diag_step_md(step))
    if not rep.get("curl_cffi_available"):
        st.warning("⚠ TLS 위장 폴백 비활성 — requirements 재설치 필요 "
                   "(`pip install curl_cffi`)")
    if rep.get("all_blocked"):
        st.error("모든 요청 단계가 차단/실패 — IP 대역 차단 또는 서버 망 차단 가능성. "
                 "다른 회선/배포 환경에서 재시도가 필요합니다.")
        return
    if rep.get("soft_block_suspect"):
        st.error("⚠ 200 위장 차단 의심 — "
                 + " / ".join(_html.escape(str(r)) for r in rep.get("soft_block_reasons", [])))

    sel = rep.get("content_selector")
    if sel:
        st.markdown(f"**본문 셀렉터** — :green[`{_html.escape(str(sel['selector']))}`] · "
                    f"{int(sel['length']):,}자")
        st.code(str(sel.get("preview") or ""), language=None)
    else:
        st.markdown("**본문 셀렉터** — :red[미매칭] (문단/최대블록 폴백 경로 사용)")

    structured = rep.get("structured") or {}
    st.markdown(f"**구조화 데이터** — ld+json {int(structured.get('ldjson_len') or 0):,}자 · "
                f"Fusion {int(structured.get('fusion_len') or 0):,}자")

    st.markdown("**메타 이미지 후보**")
    for cand in rep.get("meta_images") or []:
        st.markdown(_diag_image_md(cand, "meta"))
    if not rep.get("meta_images"):
        st.markdown("- :gray[없음 — og:image 계열 메타 자체가 없음]")
    st.markdown("**본문 img 후보 (상위 5)**")
    for cand in rep.get("body_images") or []:
        st.markdown(_diag_image_md(cand, "img"))
    if not rep.get("body_images"):
        st.markdown("- :gray[img 태그에서 src/lazy 속성을 찾지 못함]")

    final = rep.get("final") or {}
    content_len = int(final.get("content_len") or 0)
    color = "green" if content_len else "red"
    img = _html.escape(str(final.get("image_url") or "(없음)")[:90])
    st.markdown(f"**최종 fetch_article** — :{color}[본문 {content_len:,}자] · 이미지: {img}")
    if final.get("content_preview"):
        st.code(str(final["content_preview"]), language=None)


def _render_diagnose_card() -> None:
    """🔬 기사 URL 진단 카드 — 실 네트워크 호출이므로 [진단 실행] 버튼으로만 트리거.

    버튼은 `_sc_diag_pending` 플래그 + `st.rerun()` (on_click 금지), 다음 run 에서
    `_consume_diag_pending_if_any` 가 diagnose() 를 실행해 결과를 세션에 보관한다.
    """
    with st.container(key="sc_diag_card"):
        st.markdown("#### 🔬 기사 URL 진단")
        st.caption("본문·사진이 안 긁히는 기사 URL 을 넣으면 요청 3단계(기본 → 워밍업 → "
                   "TLS 위장)와 이미지·본문 셀렉터·최종 파이프라인 결과를 단계별로 보여줍니다. "
                   "실제 네트워크 요청을 보내므로 버튼을 눌렀을 때만 실행됩니다.")
        st.text_input(
            "기사 URL", key="sc_diag_url",
            placeholder="https://www.thebell.co.kr/free/content/ArticleView.asp?key=...")
        if st.button("🔬 진단 실행", key="_sc_diag_btn"):
            st.session_state["_sc_diag_pending"] = True
            st.rerun()
        if st.session_state.get("_sc_diag_pending"):
            with st.spinner("진단 중 — 대상 사이트에 실제 요청을 보냅니다..."):
                _consume_diag_pending_if_any()
        rep = st.session_state.get("sc_diag_result")
        if rep:
            if rep.get("error"):
                st.error(_html.escape(str(rep["error"])))
            else:
                _render_diag_result(rep)


# ── 기사 모달 (카드 클릭 → ?news=<link> → st.dialog) ──────────

def _consume_news_modal_open_if_any() -> None:
    """`?news=<link>` 1회 소비 → 세션 플래그(`_sc_open_news`)로 옮기고 URL 정리.

    카드 앵커가 ?news 를 실어 문서를 다시 그리면 이 핸들러가 플래그로 옮긴다(쿼리는
    제거). 모달 닫기는 ✕ 버튼이 플래그를 비우는 소켓 rerun(문서 reload 없음).
    """
    nk = (st.query_params.get("news") or "").strip()
    if not nk:
        return
    st.session_state["_sc_open_news"] = nk
    if "news" in st.query_params:
        del st.query_params["news"]


def _find_news_record_by_link(link: str) -> dict | None:
    link = (link or "").strip()
    if not link:
        return None
    for r in _sc_browse_records():
        if str(r.get("link", "") or "").strip() == link:
            return r
    return None


def _news_modal_body(row: dict) -> None:
    """기사 모달 본문 — 사진·메타·제목·요약·본문 전체 + 원본 링크 + 닫기."""
    link = str(row.get("link", "") or "").strip()
    title = str(row.get("title") or "(제목 없음)")
    img = _https_img(str(row.get("image_url", "") or ""))
    chan = _news_channel_of(row.get("source", ""), row.get("press", ""))
    when = str(row.get("collected_at") or row.get("published_at") or "")
    age = _news_age_label(when)
    # 제목 반복뿐인 summary(구글 RSS description) 는 본문 폴백에서 제외.
    summary = _news_body_src(row, ("summary_llm", "summary"))
    content = str(row.get("content") or "").strip()
    title_norm = " ".join(title.split())

    parts: list[str] = ['<div class="sc-modal">']
    if img[:4].lower() == "http":
        parts.append(
            f'<img class="sc-modal-img" src="{_html.escape(img, quote=True)}" '
            f'referrerpolicy="no-referrer" alt="">'
        )
    meta = " · ".join(p for p in (_html.escape(chan), _html.escape(age)) if p)
    if meta:
        parts.append(f'<div class="sc-modal-meta">{meta}</div>')
    parts.append(f'<h2 class="sc-modal-h">{_html.escape(title)}</h2>')
    # 과거 수집분의 본문 첫 줄 제목 반복(이중 노출)은 렌더에서도 걸러낸다.
    paras = "".join(
        f"<p>{_html.escape(p.strip())}</p>" for p in content.splitlines()
        if p.strip() and " ".join(p.split()) != title_norm
    )
    if paras:
        parts.append(f'<div class="sc-modal-body">{paras}</div>')
    elif summary:
        # 본문 미수집 시에만 요약(검색 설명)을 본문 자리에 노출 — 중복 방지.
        parts.append(f'<div class="sc-modal-body"><p>{_html.escape(summary)}</p></div>')
    else:
        parts.append('<div class="sc-modal-body"><p>본문이 아직 수집되지 않았어요. '
                     '원본 기사에서 확인하세요.</p></div>')
    parts.append('</div>')
    st.html(_components.prepare_screen_html("".join(parts)))

    # 하단 액션 행 — 원본 링크와 ✕ 닫기를 같은 라인에 병렬 배치(링크 없으면 닫기만 전폭).
    close_col = None
    if link[:4].lower() == "http":
        c1, close_col = st.columns(2, vertical_alignment="center")
        with c1:
            st.html(_components.prepare_screen_html(
                f'<a class="sc-modal-link sc-modal-link--row" '
                f'href="{_html.escape(link, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">원본 기사 열기 ↗</a>'
            ))
    closed = (close_col.button if close_col else st.button)(
        "✕ 닫기", key="_sc_news_close", use_container_width=True)
    if closed:
        st.session_state.pop("_sc_open_news", None)
        st.rerun()


def _render_news_modal_if_open() -> None:
    """`_sc_open_news` 플래그가 있으면 기사 모달을 띄운다(dismissible=False — ✕ 로만 닫음)."""
    if st.session_state.get("_sc_collect_modal_pending"):
        return  # 수집 현황 모달이 우선 — st.dialog 는 run 당 1개만 허용
    link = st.session_state.get("_sc_open_news")
    if not link:
        return
    row = _find_news_record_by_link(link)
    if row is None:
        st.session_state.pop("_sc_open_news", None)
        return
    # 동적 인자 전달 위해 런타임 데코레이트(온보딩과 동일 패턴). dismissible=False 라
    # backdrop/ESC/X 로는 안 닫혀 '플래그 잔존 → 재오픈' 버그가 없다.
    dlg = st.dialog("📰 기사 보기", width="large", dismissible=False)
    dlg(_news_modal_body)(row)


def render_collect() -> None:
    """뉴스 수집 화면 — 수집 현황 요약 + 카테고리 카드 브라우저(+기사 모달).

    `?refresh=now`(또는 '지금 뉴스 수집' 버튼)는 첫 단계에서 1회 소비 → 수집 현황
    모달 플래그로 번역(모달이 수집 실행·진행·결과·캐시 invalidate 담당).
    메인은 카드뷰(수집 요약 → 액션바 → 대분류 탭/출처칩/카드),
    `⚙ 수집 설정` 토글 시 설정 서브뷰(키워드·포탈·이력). 카드 클릭(?news=link)은
    기사 모달로 본문 전체 + 원본 링크를 보여준다.
    """
    inject_screen_css("data_management")

    _consume_refresh_if_any()
    _consume_news_search_clear_if_any()  # ?dm_clear_q=1 → 검색 해제 (render_topbar 전: 입력 위젯 리셋)
    _consume_news_modal_open_if_any()    # ?news=<link> → 기사 모달 플래그

    persona = app_shell.get_persona()
    dm_stats = _dm_stats()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="뉴스 수집",
        eyebrow_current="뉴스 수집",
        refresh_label=refresh,
        fresh_kind="fresh",
    )

    # 수집 degraded 경고 — 최근 런 실패/정체 시 상단에 prominent 배너 (개선 백로그 #1).
    alert = _collect_alert_html()
    if alert:
        st.html(alert)

    # 출처 액션 송신 처리 (위젯 인스턴스화 이전, 최상단)
    _consume_src_action_if_any()
    _consume_src_add_if_any()

    app_shell.render_setup_banner_if_needed()
    _render_refresh_toast_if_needed()
    _render_src_action_toast_if_needed()

    # 레거시 핸드오프 query(?dm_grp/?dm_tab)는 더 이상 쓰지 않음 → 남으면 1회 정리.
    for _k in ("dm_grp", "dm_tab"):
        if _k in st.query_params:
            del st.query_params[_k]

    if st.session_state.get("sc_collect_view") == "settings":
        _render_collect_settings(dm_stats, persona)
        _render_news_modal_if_open()
    else:
        _render_dm_header(dm_stats)        # 수집 현황 요약(KPI 4)
        _render_collect_actionbar()         # [지금 수집][⚙ 수집 설정]
        _render_browse_zone(persona)        # 탭/칩/카드/표 + 기사 모달 (부분 rerun)

    _render_collect_modal_if_open()         # 수집 현황 모달 (진행/결과)


def render_taskdef() -> None:
    """작업 정의 화면 — 엑셀 업로드 + 작업 정의 관리 (구 '데이터 관리'의 작업 그룹).

    탭 없이 세로 배치(사용자 결정): 헤더(작업정의 KPI) → 엑셀 업로드 섹션 →
    작업 정의 관리(검색·리스트·편집). 업로드/관리 액션은 위젯 인스턴스화 전에 1회 소비.
    """
    inject_screen_css("data_management")

    # 업로드/관리 액션 송신 처리 (위젯 인스턴스화 이전, 최상단)
    _consume_task_def_upload_if_any()
    from ui import task_def_manage as _tdm
    _tdm.consume_td_action_if_any()
    _tdm.consume_td_save_if_any()

    persona = app_shell.get_persona()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="작업 정의",
        eyebrow_current="작업 정의",
        refresh_label=refresh,
        fresh_kind="fresh",
    )

    app_shell.render_setup_banner_if_needed()
    _render_task_def_toast_if_needed()

    # 헤더(작업정의 KPI 3종) — 1회
    _render_taskdef_header(_taskdef_stats())
    # 엑셀 업로드 (구 task 탭 본문 + 업로더 위젯)
    st.html(_components.prepare_screen_html(
        _dm_tab_body_html("task", persona=persona, dm_stats={})))
    _render_task_def_upload()
    # 작업 정의 관리 (구 manage 탭 — 검색·리스트·편집·이력)
    _tdm.render(st.query_params)


def _fmt_taskdef_ts(ts: str) -> str:
    """작업 정의 updated_at(UTC ISO) → 'MM/DD'(오늘이면 'HH:MM') 한국시간. 실패 시 ''."""
    if not ts:
        return ""
    try:
        import pandas as _pd
        dt = _pd.to_datetime(ts, errors="coerce", utc=True)
        if _pd.isna(dt):
            return ""
        dt = dt.tz_convert("Asia/Seoul")
        now = _pd.Timestamp.now(tz="Asia/Seoul")
        return dt.strftime("%H:%M") if dt.date() == now.date() else dt.strftime("%m/%d")
    except Exception:  # noqa: BLE001
        return ""


def _taskdef_stats() -> dict[str, str | int]:
    """작업 정의 화면 KPI — 등록 정의 수 · 부서 수 · 마지막 갱신.

    `task_defs_db.list_all()` 은 updated_at 내림차순이라 [0] 이 최신.
    """
    rows: list[dict] = []
    with guard("작업 정의 통계 로드"):
        from store import task_defs_db
        rows = task_defs_db.list_all()
    defs = len(rows)
    depts = len({(r.get("dept") or "").strip() for r in rows if (r.get("dept") or "").strip()})
    last = _fmt_taskdef_ts(str(rows[0].get("updated_at") or "")) if rows else ""
    return {"defs": defs, "depts": depts, "last_update": last or "—"}


def _render_taskdef_header(td_stats: dict[str, str | int]) -> None:
    """작업 정의 화면 상단 헤더 — 브레드크럼·설명 + KPI 3종(.dm-head 룩 재사용)."""
    def _v(k: str) -> str:
        return _html.escape(str(td_stats.get(k, "—")))
    html_out = (
        '<div class="dm-shell">'
        '<header class="dm-head">'
        '<div>'
        '<div class="dm-bc"><span>워크플로</span><span class="dm-bc-sep">›</span>'
        '<span class="dm-bc-cur">작업 정의</span></div>'
        '<p class="dm-desc">조선소 작업 정의를 엑셀로 올리고 SOLA 가 이해하는 구조로 '
        '관리합니다. 뉴스↔작업 매칭과 자동화 기회 판단의 기준이 됩니다.</p>'
        '</div>'
        '<div class="dm-head-stats">'
        f'<div class="dm-stat"><div class="dm-stat-v">{_v("defs")}</div>'
        '<div class="dm-stat-k">등록 정의</div></div>'
        '<div class="dm-stat-sep"></div>'
        f'<div class="dm-stat"><div class="dm-stat-v">{_v("depts")}</div>'
        '<div class="dm-stat-k">부서</div></div>'
        '<div class="dm-stat-sep"></div>'
        f'<div class="dm-stat"><div class="dm-stat-v">{_v("last_update")}</div>'
        '<div class="dm-stat-k">마지막 갱신</div></div>'
        '</div>'
        '</header>'
        '</div>'
    )
    st.html(_components.prepare_screen_html(html_out))


def _render_dm_header(dm_stats: dict[str, str | int]) -> None:
    """수집 현황 요약 헤더(브레드크럼·설명·KPI 4종) — 카드뷰/설정뷰 상단에 1회.

    `_DM_TEMPLATE` 의 헤더 부분({{DM_TABS}} 앞)만 잘라 KPI 를 끼워 렌더한다."""
    template = _components.read_asset_text(_DM_TEMPLATE)
    head = template.split("{{DM_TABS}}", 1)[0]  # <div class=dm-shell>…<header>…</header>
    head_html = (
        head
        .replace("{{ACTIVE_SOURCES}}", _html.escape(str(dm_stats["active_sources"])))
        .replace("{{TODAY_COUNT}}", _html.escape(str(dm_stats["today_count"])))
        .replace("{{TOTAL_CHUNKS}}", _html.escape(str(dm_stats["total_chunks"])))
        .replace("{{LAST_UPDATE}}", _html.escape(str(dm_stats["last_update"])))
    ) + "</div>"  # split 로 잘려나간 dm-shell 닫기 보강
    st.html(_components.prepare_screen_html(head_html))


def _render_collect_button() -> None:
    """'지금 뉴스 수집' — 구 앵커(`?refresh=now`) 대체 위젯.

    앵커는 클릭 시 문서 전체 reload(흰 깜빡임)였다. st.button 은 소켓 rerun → 클릭 시
    `_sc_collect_modal_pending` 플래그 세팅 후 `st.rerun()`(on_click 미사용), 다음 run 에서
    수집 현황 모달이 떠서 collect_batch 진행·결과를 보여준다. 룩은
    `.st-key-dm_collect_cta` 스코프(우측 정렬 + accent 채움)로 구 `.dm-btn-primary` 에 맞춘다.
    """
    with st.container(key="dm_collect_cta"):
        if st.button(
            "🔄 지금 뉴스 수집", key="_dm_collect_btn", type="primary",
            help="페르소나 관심사 키워드(없으면 자동화·AI)로 지금 뉴스를 수집하고 화면을 새로 그립니다.",
        ):
            st.session_state["_sc_collect_modal_pending"] = True
            st.rerun()


def _consume_refresh_if_any() -> bool:
    """수집 트리거 1회 소비 — 수집 현황 **모달 플래그**(`_sc_collect_modal_pending`)로 번역.

    트리거는 둘 중 하나: '지금 뉴스 수집' 버튼(구버전 호환 `_do_dm_collect` pending)
    또는 레거시 `?refresh=now` 쿼리(북마크/딥링크 호환). 과거엔 여기서 collect_batch 를
    render 도중 동기 실행했지만, 이제 실제 수집·진행 표시·결과 요약·캐시 무효화는
    모두 수집 현황 모달(`_collect_modal_body` → `_run_collect_for_modal`)이 담당한다.
    """
    triggered = bool(st.session_state.pop("_do_dm_collect", False))
    if not triggered and st.query_params.get("refresh") != "now":
        return False

    st.session_state["_sc_collect_modal_pending"] = True
    if "refresh" in st.query_params:
        del st.query_params["refresh"]
    return True


# ── 수집 현황 모달 ([🔄 지금 뉴스 수집] → st.dialog 진행/결과) ──────────

def _invalidate_collect_caches() -> None:
    """수집 직후 dm 관련 캐시 일괄 무효화.

    `_archive_stats_dm` 는 `board_v2._archive_stats()` 위임이므로 보드 캐시도
    함께 비워야 좌측 nav 카운트와 보드 전 섹션(브리핑/스토리/트렌드/기회/매트릭스/
    키워드)이 즉시 새 수집 결과로 갱신된다 (`board_v2.invalidate_board_caches`).
    """
    from ui import board_v2 as _bv2  # lazy

    for fn in (_dm_stats, _ingest_jobs_html, _hist_html, _sc_browse_records,
               _archive_stats_dm):
        if hasattr(fn, "clear"):
            fn.clear()
    _bv2.invalidate_board_caches()


def _collect_source_rows(saved: list, errors: list) -> list[dict]:
    """소스별 수집 건수 행 — saved(소스·건수) + 오류 소스 병합 (순수 변환).

    반환: `[{"source", "count", "ok"}, ...]` — saved 순서 유지, 오류만 나고
    저장이 없는 소스는 뒤에 0건·ok=False 로 추가(0건/오류 소스도 표에 보이게).
    saved 에 있어도 같은 소스에 오류가 있으면 ok=False (부분 오류 표시).
    라이브 수집(`CollectionReport.saved/errors`)과 런 로그(`sources/errors`)
    양쪽 스키마를 모두 수용한다 (둘 다 source/count 키 동형).
    """
    err_sources = {
        str(e.get("source", ""))
        for e in errors
        if isinstance(e, dict) and e.get("source")
    }
    rows: list[dict] = []
    seen: set[str] = set()
    for s in saved:
        if not isinstance(s, dict):
            continue
        name = str(s.get("source", "") or "?")
        rows.append({
            "source": name,
            "count": int(s.get("count", 0) or 0),
            "ok": name not in err_sources,
        })
        seen.add(name)
    for name in sorted(err_sources - seen):
        rows.append({"source": name, "count": 0, "ok": False})
    return rows


def _run_collect_for_modal(progress=None) -> dict:
    """collect_batch 동기 실행 → 모달 본문 표시용 결과 dict. 캐시 무효화 포함.

    수집 키워드는 페르소나 관심사(interest_tasks + interest_lv3), 비어 있으면 기본
    키워드(자동화·AI)로 폴백. tech 사이트·커스텀 RSS 는 키워드 무관하게 항상 함께
    수집한다. `progress` 가 주어지면(st.progress 핸들) collect_batch 의 `on_step`
    콜백으로 소스·키워드 단위 진행률을 갱신한다. 모든 예외는 dict 로 흡수 —
    네트워크 차단 환경에서도 모달이 오류 요약을 보여준다. 캐시 무효화는 성공/실패
    무관하게 finally 에서 수행(다음 렌더가 최신).
    """
    try:
        from ui.board_v2 import _collect_keywords_with_default, _collect_extra_feeds
        from scraping.run_daily import collect_batch
        persona = app_shell.get_persona()
        kws, used_default = _collect_keywords_with_default(persona)
        extra_feeds = _collect_extra_feeds()
        # 진행률 분모 — 키워드×(naver+google) + tech 1회 + RSS 피드 수
        total_steps = len(kws) * 2 + 1 + len(extra_feeds)
        done = {"n": 0}

        def _on_step(source: str, keyword: str, found: int) -> None:
            done["n"] += 1
            if progress is None:
                return
            label = str(source) + (f" · {keyword}" if keyword else "") + f" — {found}건"
            try:
                progress.progress(min(done["n"] / max(total_steps, 1), 1.0), text=label)
            except Exception:  # noqa: BLE001 — 진행 표시 실패가 수집을 깨면 안 됨
                pass

        import time as _time
        _t0 = _time.monotonic()
        report = collect_batch(
            kws, max_results=10, extra_feeds=extra_feeds, on_step=_on_step,
        )
        _dur = _time.monotonic() - _t0
        try:  # 런 로그 기록 — '수집 헬스'·[보기] 재열람이 읽음. 로깅 실패가 수집을 깨면 안 됨.
            from store import run_log
            run_log.record_run(report, trigger="manual", duration_s=_dur)
        except Exception:  # noqa: BLE001
            pass

        n_articles = report.total_articles
        n_files = report.total_files
        n_err = len(report.errors)
        errors = [
            str(e.get("source", "?"))
            + (f" · {e.get('keyword')}" if e.get("keyword") else "")
            + f": {e.get('error', '')}"
            for e in report.errors
        ]
        if n_err and n_articles == 0:
            ok = False
            message = f"⚠️ 수집 실패 — 첫 오류: {report.errors[0].get('error', 'unknown')}"
        else:
            ok = True
            feeds_label = f", RSS {len(extra_feeds)}건" if extra_feeds else ""
            err_tail = f", 일부 오류 {n_err}건" if n_err else ""
            kw_label = (
                "관심사가 비어 기본 키워드(자동화·AI)" if used_default
                else f"{len(kws)}개 키워드"
            )
            message = (
                f"✓ {kw_label}{feeds_label}로 {n_articles}건 수집 "
                f"({n_files}개 파일){err_tail}."
            )
        return {
            "ok": ok, "message": message,
            "total_articles": n_articles, "total_files": n_files,
            "n_keywords": len(kws), "used_default": used_default,
            "n_feeds": len(extra_feeds), "errors": errors,
            "sources": _collect_source_rows(
                list(report.saved or []), list(report.errors or []),
            ),
        }
    except Exception as exc:  # noqa: BLE001 — 모달이 오류 요약을 표시
        return {
            "ok": False,
            "message": f"⚠️ 수집 처리 실패: {type(exc).__name__}: {exc}",
            "total_articles": 0, "total_files": 0,
            "n_keywords": 0, "used_default": False, "n_feeds": 0,
            "errors": [f"{type(exc).__name__}: {exc}"], "sources": [],
        }
    finally:
        _invalidate_collect_caches()


_RUN_LOG_TRIG_LABEL: dict[str, str] = {
    "cron": "자동(cron)", "manual": "수동 수집", "board": "보드 수집",
}


def _run_log_to_modal_result(run: dict) -> dict:
    """런 로그 엔트리(`store.run_log` 스키마) → 수집 현황 모달 결과 dict (순수 변환).

    ⚙ 수집 설정의 [📡 마지막 수집 결과 보기]/[보기] 가 과거 런을 모달 결과 요약
    모드로 재열람할 때 쓴다. 과거 로그의 필드 누락(ok/sources/errors 등)에 방어:
    - ok 누락 → errors 유무로 유추
    - n_keywords → sources[].keywords 합집합 크기
    - n_feeds → 키워드 검색(naver/google)·tech 가 아닌 소스 수(커스텀 RSS 근사)
    결과 dict 에 `from_log=True` 마커 → 모달이 재수집 없이 요약만 보여준다
    (기존 '결과 존재 시 collect 스킵' 가드 활용).
    """
    run = run if isinstance(run, dict) else {}
    sources = [s for s in (run.get("sources") or []) if isinstance(s, dict)]

    kws: list[str] = []
    for s in sources:
        for k in (s.get("keywords") or []):
            k = str(k)
            if k and k not in kws:
                kws.append(k)
    n_feeds = sum(
        1 for s in sources
        if str(s.get("source", "")) not in (*_SC_KEYWORD_SOURCES, "tech")
    )

    errors: list[str] = []
    for e in (run.get("errors") or []):
        if isinstance(e, dict):
            errors.append(
                str(e.get("source", "?"))
                + (f" · {e.get('keyword')}" if e.get("keyword") else "")
                + f": {e.get('error', '')}"
            )
        elif e:
            errors.append(str(e))

    ok = bool(run.get("ok")) if "ok" in run else not errors
    total = int(run.get("total_articles", 0) or 0)
    files = int(run.get("total_files", 0) or 0)
    date, time = _run_when_parts(run.get("ts", ""))
    when = f"{date} {time}".strip()
    trig_raw = str(run.get("trigger", "") or "")
    trig = _RUN_LOG_TRIG_LABEL.get(trig_raw, trig_raw or "—")
    status = "정상" if ok else (f"오류 {len(errors)}건" if errors else "오류")
    err_tail = f", 일부 오류 {len(errors)}건" if (ok and errors) else ""
    message = (
        f"📜 지난 수집 결과 ({trig} · {when}) — "
        f"{total}건 수집 ({files}개 파일), {status}{err_tail}."
    )
    return {
        "ok": ok, "message": message,
        "total_articles": total, "total_files": files,
        "n_keywords": len(kws), "used_default": False,
        "n_feeds": n_feeds, "errors": errors,
        "sources": _collect_source_rows(sources, run.get("errors") or []),
        "from_log": True, "run_id": str(run.get("run_id", "") or ""),
    }


def _open_run_result_modal(run: dict) -> None:
    """런 로그 1건 → 모달 결과 세션 주입 + 수집 현황 모달 오픈(재수집 없음) + rerun."""
    st.session_state["_sc_collect_modal_result"] = _run_log_to_modal_result(run)
    st.session_state["_sc_collect_modal_pending"] = True
    st.rerun()


_RUN_HISTORY_VIEW_N = 5  # ⚙ 수집 설정 이력에서 [보기] 버튼을 붙일 최근 런 수


def _render_run_history_view_buttons() -> None:
    """⚙ 수집 설정 이력 영역 — [📡 마지막 수집 결과 보기] + 최근 런별 [보기] 버튼.

    클릭 시 `_open_run_result_modal` 이 런 로그를 모달 결과 dict 로 변환해 세션에
    넣고 수집 현황 모달을 연다. 결과가 이미 있으므로 모달은 재수집하지 않는다.
    런 로그가 없으면 안내 caption 만 (버튼 없음).
    """
    try:
        from store import run_log
        runs = run_log.load_runs(limit=_RUN_HISTORY_VIEW_N)
    except Exception:  # noqa: BLE001
        runs = []
    with st.container(key="sc_runlog_views"):
        if not runs:
            st.caption("아직 수집 런 기록이 없어요 — [🔄 지금 뉴스 수집]으로 시작하세요.")
            return
        if st.button(
            "📡 마지막 수집 결과 보기", key="_sc_runlog_last_btn",
            use_container_width=True,
            help="가장 최근 수집 런의 결과 요약을 수집 현황 모달로 다시 봅니다 (재수집 없음).",
        ):
            _open_run_result_modal(runs[0])
        for i, run in enumerate(runs):
            date, time = _run_when_parts(run.get("ts", ""))
            trig_raw = str(run.get("trigger", "") or "")
            trig = _RUN_LOG_TRIG_LABEL.get(trig_raw, trig_raw or "—")
            ok = bool(run.get("ok")) if "ok" in run else not (run.get("errors") or [])
            total = int(run.get("total_articles", 0) or 0)
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            with c1:
                st.caption(
                    f"{date} {time} · {trig} · {total}건 · "
                    f"{'정상' if ok else '⚠ 오류'}"
                )
            with c2:
                if st.button("보기", key=f"_sc_runlog_view_{i}",
                             use_container_width=True):
                    _open_run_result_modal(run)


def _collect_result_summary_html(result: dict) -> str:
    """수집 결과 요약 HTML — 배지 + 메시지 + KPI 4 + 소스별 건수 표 + 오류 목록(전부 escape)."""
    ok = bool(result.get("ok"))
    badge = ('<span class="sc-cm-badge sc-cm-ok">정상</span>' if ok
             else '<span class="sc-cm-badge sc-cm-fail">오류</span>')
    msg = _html.escape(str(result.get("message", "")))
    stats = (
        ("수집 기사", f"{int(result.get('total_articles', 0) or 0)}건"),
        ("저장 파일", f"{int(result.get('total_files', 0) or 0)}개"),
        ("키워드", f"{int(result.get('n_keywords', 0) or 0)}개"),
        ("RSS 출처", f"{int(result.get('n_feeds', 0) or 0)}건"),
    )
    cells = "".join(
        f'<div class="sc-cm-stat"><div class="sc-cm-v">{_html.escape(v)}</div>'
        f'<div class="sc-cm-k">{_html.escape(k)}</div></div>'
        for k, v in stats
    )
    # 소스별 수집 건수 표 — KPI 아래. 0건·오류 소스도 행으로 노출(어디서 안 왔는지).
    src_rows = [s for s in (result.get("sources") or []) if isinstance(s, dict)]
    src_html = ""
    if src_rows:
        trs = "".join(
            '<tr class="{cls}"><td class="sc-cm-src-n">{name}</td>'
            '<td class="sc-cm-src-c">{count}건</td>'
            '<td class="sc-cm-src-s">{status}</td></tr>'.format(
                cls="sc-cm-src-err" if not r.get("ok") else "",
                name=_html.escape(str(r.get("source", "?") or "?")),
                count=int(r.get("count", 0) or 0),
                status="정상" if r.get("ok") else "⚠ 오류",
            )
            for r in src_rows
        )
        src_html = (
            '<div class="sc-cm-srcs"><div class="sc-cm-srcs-t">소스별 수집 건수</div>'
            '<table class="sc-cm-src-table">'
            "<thead><tr><th>소스</th><th>건수</th><th>상태</th></tr></thead>"
            f"<tbody>{trs}</tbody></table></div>"
        )
    errors = [str(e) for e in (result.get("errors") or []) if e]
    err_html = ""
    if errors:
        shown = errors[:8]
        items = "".join(f"<li>{_html.escape(e)}</li>" for e in shown)
        more = (f"<li>… 외 {len(errors) - len(shown)}건</li>"
                if len(errors) > len(shown) else "")
        err_html = (
            f'<div class="sc-cm-errs"><div class="sc-cm-errs-t">⚠ 오류 {len(errors)}건</div>'
            f"<ul>{items}{more}</ul></div>"
        )
    return (
        '<div class="sc-collect-modal">'
        f'<div class="sc-cm-msg">{badge}<span>{msg}</span></div>'
        f'<div class="sc-cm-stats">{cells}</div>{src_html}{err_html}</div>'
    )


def _collect_modal_body() -> None:
    """수집 현황 모달 본문 — 미수집이면 1회 수집 실행(진행 표시), 결과 요약 + [✕ 닫기].

    결과는 `_sc_collect_modal_result` 세션에 저장 → rerun 에도 유지되고 재수집을
    가드한다(결과 존재 시 collect_batch 재실행 금지). [✕ 닫기]가 플래그·결과를
    비우고 rerun — 캐시 무효화는 수집 직후(`_run_collect_for_modal`) 이미 끝났으므로
    닫힌 화면은 최신 데이터로 그려진다.
    """
    result = st.session_state.get("_sc_collect_modal_result")
    if result is None:
        with st.status("📡 뉴스 수집 중… 기사 본문·이미지를 가져오는 중이에요.",
                       expanded=True) as _stat:
            prog = st.progress(0.0, text="수집 준비 중…")
            result = _run_collect_for_modal(prog)
            st.session_state["_sc_collect_modal_result"] = result
            _stat.update(
                label="수집 완료" if result.get("ok") else "수집 중 오류 발생",
                state="complete" if result.get("ok") else "error",
                expanded=False,
            )
    st.html(_components.prepare_screen_html(_collect_result_summary_html(result)))
    if st.button("✕ 닫기", key="_sc_collect_modal_close", type="primary",
                 use_container_width=True):
        st.session_state.pop("_sc_collect_modal_pending", None)
        st.session_state.pop("_sc_collect_modal_result", None)
        st.rerun()


def _render_collect_modal_if_open() -> None:
    """`_sc_collect_modal_pending` 플래그가 있으면 수집 현황 모달을 띄운다.

    dismissible=False — [✕ 닫기] 버튼으로만 닫는다(기사 모달과 동일 패턴 →
    backdrop/ESC 로 닫혀 '플래그 잔존 → 재오픈' 버그가 없다).
    """
    if not st.session_state.get("_sc_collect_modal_pending"):
        return
    dlg = st.dialog("📡 뉴스 수집 현황", width="large", dismissible=False)
    dlg(_collect_modal_body)()


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
        for fn in (_dm_stats, _ingest_jobs_html, _hist_html, _sc_browse_records,
                   _archive_stats_dm, _bv2._board_kpis):
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
        'background: var(--surface-card); border: 1px solid var(--surface-divider); border-radius: 12px;">'
        '<div style="font-size: 18px; font-weight: 800; color: #0F172A; '
        'letter-spacing: -0.01em; margin-bottom: 4px;">📂 작업 정의 데이터 업로드</div>'
        '<div style="font-size: 13px; color: #64748B; line-height: 1.5;">'
        '엑셀(.xlsx) 파일을 올리면 자동으로 정규화 + 검증 후 Parquet 으로 저장됩니다. '
        '<b>flat 형식</b>(JSON 열 없음): 분과 · 팀 · 부서 · 공정 · 작업 · 세부작업 · '
        'Process_ID · 공정설명 · 작업흐름 · 주요확인사항 · 안전주의사항 · 주요사용장비 · '
        '품질리스크 · 자동화가능영역 · 이전공정 · 다음공정 — 개별 컬럼이 자동으로 구조화 '
        'JSON 으로 조립됩니다. <b>구 형식</b>(…·공정정의서(JSON))도 그대로 인식.'
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
        help="flat 형식(분과/공정/Process_ID/개별 컬럼) · JSON 열 형식 · 구엑셀(lv1/lv2/lv3) 모두 자동 인식.",
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
        '<div style="margin: 18px 24px 8px; padding: 14px 18px; background: var(--surface-card); '
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
    # src 탭은 위젯 렌더(_render_src_table)라 HTML 경로를 타지 않는다.
    return ""


def _dm_kw_body_html(persona: Persona | None) -> str:
    """키워드 탭 본문 — 페르소나 관심사 + 자동 추출 요약 + 보드 ⑦ 인계."""
    from urllib.parse import quote
    persona = persona or Persona()
    user_terms = [
        t for t in (
            list(persona.interest_keywords or [])
            + list(persona.interest_tasks or [])
            + list(persona.interest_lv3 or [])
        )
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


# 출처 탭 표시명(store.sources.DEFAULT_SOURCES) ↔ 저장 뉴스의 source/press 값 매칭.
#   - source: 그 표시명으로 인정할 저장 source 값들(수집 ID + legacy 표시명 직접 저장 호환).
#   - tech_press: source="tech"(AI Times·오토메이션월드 공용) 일 때 press 로 구분할 site 명.
_DEFAULT_SOURCE_MATCH: dict[str, dict[str, tuple[str, ...]]] = {
    "AI Times":     {"source": ("AI Times", "aitimes"),               "tech_press": ("AI Times",)},
    "오토메이션월드":  {"source": ("오토메이션월드", "automationworld"),   "tech_press": ("오토메이션월드",)},
    "Google RSS":   {"source": ("google", "Google RSS")},
    "네이버 기술":    {"source": ("naver", "네이버 기술")},
}


def _src_count_map() -> dict[str, tuple[int, str]]:
    """최근 7일 출처별 (수집 건수, 최신 ISO) — 출처 행/상태 공통 데이터.

    키는 **출처 탭 표시명**이다(`store.sources.DEFAULT_SOURCES`). 수집기는 source 를
    naver/google/tech 로 저장하고 tech 는 AI Times·오토메이션월드를 모두 source="tech"
    로 묶어 site 명을 `press` 에 둔다. 표시명으로 곧장 group 하면 전부 0건(무수집)으로
    보이던 버그를, 아래 매칭으로 환산해 고친다(legacy 로 source 에 표시명이 직접 들어간
    데이터도 함께 인식). 매칭에 안 잡힌 나머지 source 값(커스텀 RSS=source=name 등)은
    그 값 그대로 키로 둔다(커스텀/기타 행용).
    """
    try:
        week = _news_db.load_news_for_days(days=7)
    except Exception:
        week = None
    cnt_map: dict[str, tuple[int, str]] = {}
    if week is None or week.empty or "source" not in week.columns:
        return cnt_map

    src_col = week["source"].astype(str)
    press_col = week["press"].astype(str) if "press" in week.columns else None

    def _last_iso(sub) -> str:
        for col in ("collected_at", "published_at"):
            if col in sub.columns:
                iso = str(sub[col].dropna().max() or "")
                if iso:
                    return iso
        return ""

    consumed: set[str] = {"tech"}  # tech 는 press 로 분기되므로 항상 소비됨
    for disp, rule in _DEFAULT_SOURCE_MATCH.items():
        consumed |= set(rule["source"])
        mask = src_col.isin(rule["source"])  # legacy: source 에 표시명/ID 직접
        tp = rule.get("tech_press")
        if tp and press_col is not None:     # 신규: source=tech + press=site 명
            mask = mask | (src_col.eq("tech") & press_col.isin(tp))
        sub = week[mask]
        cnt_map[disp] = (int(len(sub)), _last_iso(sub) if len(sub) else "")

    rest = week[~src_col.isin(consumed)]
    if not rest.empty:
        for src, sub in rest.groupby("source"):
            cnt_map[str(src)] = (int(len(sub)), _last_iso(sub))
    return cnt_map


def _src_status_html(cnt: int, is_enabled: bool) -> str:
    if not is_enabled:
        return '<span class="dm-src-st dm-src-st-off">비활성</span>'
    if cnt > 0:
        return '<span class="dm-src-st dm-src-st-ok">OK</span>'
    return '<span class="dm-src-st dm-src-st-warn">7일 무수집</span>'


def _src_row_pill_html(name: str, cnt: int, last_iso: str, *,
                       is_enabled: bool, kind: str, url: str = "") -> str:
    """출처 1행의 시각 부분(마크/이름/건수/최신/상태) — 액션 제외.

    토글/제거 액션은 `_render_src_row` 가 옆 칸 st.button 으로 그린다(앵커 제거).
    행 테두리/배경은 컨테이너(.st-key-_src_row_*)가, 내부 셀 격자는 .dm-src-rowp 가 담당.
    """
    grad = _SOURCE_GRADIENTS.get(name, _DEFAULT_GRADIENT)
    name_html = _html.escape(name)
    if url:
        name_html += f'<span class="dm-src-url-mini">{_html.escape(url[:60])}</span>'
    elif kind == "other":
        name_html += '<span class="dm-src-url-mini">기타 — 토글 불가</span>'
    cls = "dm-src-rowp"
    if not is_enabled:
        cls += " dm-src-rowp-off"
    elif kind == "custom":
        cls += " dm-src-rowp-custom"
    return (
        f'<div class="{cls}">'
        f'<span class="dm-src-mark" style="background:{grad};"></span>'
        f'<span class="dm-src-name">{name_html}</span>'
        f'<span class="dm-src-cnt">{cnt}건/7일</span>'
        f'<span class="dm-src-last">{_html.escape(last_iso[:16] if last_iso else "—")}</span>'
        f'{_src_status_html(cnt, is_enabled)}'
        '</div>'
    )


def _src_header_html(n_active: int) -> str:
    """출처 설정 탭 헤더(상호작용 없음)."""
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
    </section>"""


def _render_src_row(idx: int, name: str, cnt: int, last_iso: str, *,
                    is_enabled: bool, kind: str, url: str = "") -> None:
    """출처 1행 — [시각 pill | 토글/제거 버튼] (st.columns). 클릭은 소켓 rerun.

    토글/제거는 `_do_src_action`=(action, name) pending → `_consume_src_action_if_any`
    가 처리(on_click 미사용). 'other'(내부 ID) 행은 토글 불가라 '—' 표시.
    """
    with st.container(key=f"_src_row_{idx}"):
        c1, c2 = st.columns([6, 1.3], vertical_alignment="center")
        with c1:
            st.html(_src_row_pill_html(
                name, cnt, last_iso, is_enabled=is_enabled, kind=kind, url=url))
        with c2:
            if kind == "default":
                label = "비활성화" if is_enabled else "활성화"
                if st.button(label, key=f"_src_act_{idx}", use_container_width=True):
                    st.session_state["_do_src_action"] = ("toggle", name)
                    st.rerun()
            elif kind == "custom":
                if st.button("제거", key=f"_src_act_{idx}", use_container_width=True):
                    st.session_state["_do_src_action"] = ("remove", name)
                    st.rerun()
            else:
                st.html('<div class="dm-src-act-noop">—</div>')


def _render_src_table(dm_stats: dict[str, str | int]) -> None:
    """출처 설정 탭 본문 — 헤더 HTML + 출처 행별 위젯(토글/제거).

    구 `_dm_src_body_html` 의 토글/제거 `<a href="?src_action=…">`(문서 reload=흰
    깜빡임)를 위젯화. 기본 4 출처(토글) + 커스텀(제거) + 기타(내부 ID, 토글 불가).
    """
    from store import sources as src_store

    cnt_map = _src_count_map()
    disabled = src_store.disabled_set()
    customs = src_store.custom_sources()
    n_active = len([s for s in src_store.DEFAULT_SOURCES if s not in disabled]) + len(customs)
    st.html(_components.prepare_screen_html(_src_header_html(n_active)))

    idx = 0
    for src in src_store.DEFAULT_SOURCES:  # 기본 — 토글
        cnt, last_iso = cnt_map.get(src, (0, ""))
        _render_src_row(idx, src, cnt, last_iso,
                        is_enabled=src not in disabled, kind="default")
        idx += 1
    for cs in customs:  # 커스텀 — 제거
        cnt, last_iso = cnt_map.get(cs.name, (0, ""))
        _render_src_row(idx, cs.name, cnt, last_iso,
                        is_enabled=True, kind="custom", url=cs.url)
        idx += 1
    known = set(src_store.DEFAULT_SOURCES) | {c.name for c in customs}
    for src in sorted(s for s in cnt_map if s not in known):  # 기타 — 토글 불가
        cnt, last_iso = cnt_map.get(src, (0, ""))
        _render_src_row(idx, src, cnt, last_iso, is_enabled=True, kind="other")
        idx += 1


_SRC_ACTIONS = {"toggle", "remove", "add"}


def _consume_src_action_if_any() -> tuple[str, str] | None:
    """출처 토글/제거 1회 소비.

    트리거는 둘 중 하나: 출처 행 버튼이 세팅한 `_do_src_action`=(action, name) pending
    (신규, 문서 reload 없음) 또는 레거시 `?src_action=toggle|remove&src_name=` 쿼리
    (북마크/딥링크 호환). toggle=기본 출처 활성/비활성, remove=커스텀 출처 제거.
    (add 는 `_do_src_add` 별 path.) 반환: 성공 시 (action, src_name), 아니면 None.
    """
    pend = st.session_state.pop("_do_src_action", None)
    if pend:
        action, name = pend[0], (pend[1] or "").strip()
    else:
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
        'background: var(--surface-card); border: 1px solid var(--surface-divider); border-radius: 12px;">'
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


