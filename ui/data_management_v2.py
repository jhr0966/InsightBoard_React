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
# 순수 프레젠테이션 빌더(부작용 없음)는 data_management_render 로 분리(오버사이즈 완화).
# re-import 로 기존 참조(테스트 포함)를 그대로 유지한다.
from ui.data_management_render import (  # noqa: F401 — re-export
    _SOURCE_GRADIENTS,
    _DEFAULT_GRADIENT,
    _DM_TABS,
    _DM_TAB_LABEL,
    _DM_GROUPS,
    _DM_GROUP_LABEL,
    _DM_GROUP_TABS,
    _DM_GROUP_DEFAULT_TAB,
    _DM_TAB_ICON_SVG,
    _news_age_label,
    _news_card_html,
    _news_empty_html,
    _dm_group_of,
    _dm_resolve_group_and_tab,
    _dm_tab_href,
    _dm_group_href,
    _dm_groups_html,
    _dm_tabs_html,
    _src_action_href,
)


# 뉴스 라이브러리에 노출할 카드 수
_MAX_NEWS_CARDS = 6


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


# 뉴스 라이브러리 검색 세션 키 — 검색어는 _news_cards_html 에 인자로 전달(캐시키 분리).
_NEWS_SEARCH_KEY = "_news_search_q"
_NEWS_SEARCH_COLS = ("title", "content", "summary", "keywords")
_MAX_SEARCH_CARDS = 24  # 검색 모드에선 더 많이 노출

# 뉴스 라이브러리 필터(출처·기간·정렬) — st.form 위젯 키. 폼은 '적용' 제출 시에만
# 값을 커밋하므로 이 키들의 세션 값 = '마지막으로 적용된' 필터다(타이핑/선택 중엔
# rerun 없음 → '적용' 눌렀을 때만 라이브러리 갱신).
_NEWS_F_SRC_KEY = "_news_f_src_widget"
_NEWS_F_PERIOD_KEY = "_news_f_period_widget"
_NEWS_F_SORT_KEY = "_news_f_sort_widget"
# 기간 라벨 → 일수, 정렬 라벨 → 키 (dict 삽입순 = 셀렉트박스 표시순, 첫 항목이 기본값).
_NEWS_PERIOD_OPTS: dict[str, int] = {"최근 3일": 3, "최근 7일": 7, "최근 30일": 30}
_NEWS_SORT_OPTS: dict[str, str] = {"최신순": "newest", "오래된순": "oldest"}


def _filter_news_by_query(news, q: str):
    """제목·본문·요약·키워드에 `q`(대소문자 무시)가 포함된 뉴스만. 순수 함수(테스트용)."""
    ql = (q or "").strip().lower()
    if not ql or news is None or news.empty:
        return news
    cols = [c for c in _NEWS_SEARCH_COLS if c in news.columns]
    if not cols:
        return news.iloc[0:0]
    hay = news[cols[0]].fillna("").astype(str)
    for c in cols[1:]:
        hay = hay.str.cat(news[c].fillna("").astype(str), sep=" ")
    return news[hay.str.lower().str.contains(ql, regex=False, na=False)]


def _news_search_banner_html(q: str, n: int) -> str:
    """검색 활성 시 결과 칩 + 해제(×) 링크. 해제는 `?dm_clear_q=1`."""
    from urllib.parse import quote as _q
    q_safe = _html.escape(q)
    clear_href = "?app_area=" + _q("🗞 뉴스 수집") + "&dm_clear_q=1"
    return (
        '<div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; '
        'margin:0 0 12px; padding:10px 14px; background:var(--accent-ring,rgba(37,99,235,.10)); '
        'border:1px solid var(--surface-divider); border-radius:10px;">'
        f'<span style="font-size:13px; color:var(--text-primary);">🔎 '
        f'<b>“{q_safe}”</b> 검색 결과 <b>{n}건</b></span>'
        f'<a href="{clear_href}" target="_self" style="margin-left:auto; font-size:12.5px; '
        'font-weight:600; color:var(--accent-primary); text-decoration:none;">✕ 검색 해제</a>'
        '</div>'
    )


def _news_filter_banner_html(q: str, sources: tuple[str, ...], days: int,
                             sort: str, n: int) -> str:
    """활성 필터(검색어·출처·기간·정렬) 요약 칩 + 결과 건수 + 전체 해제(✕) 배너.

    해제(✕)는 `?dm_clear_filters=1` → `_consume_news_filter_clear_if_any` 가 검색어와
    폼 위젯을 기본값으로 되돌린다.
    """
    from urllib.parse import quote as _q
    chips: list[str] = []
    if q:
        chips.append(f'🔎 “{_html.escape(q)}”')
    if sources:
        chips.append(
            " · ".join(_html.escape(s) for s in sources)
            if len(sources) <= 2 else f"출처 {len(sources)}개"
        )
    if days >= 7:
        period_label = next((k for k, v in _NEWS_PERIOD_OPTS.items() if v == days), "")
        if period_label:
            chips.append(_html.escape(period_label))
    if sort != "newest":
        sort_label = next((k for k, v in _NEWS_SORT_OPTS.items() if v == sort), "")
        if sort_label:
            chips.append(_html.escape(sort_label))
    chips_html = " ".join(
        '<span style="display:inline-block; padding:2px 9px; border-radius:999px; '
        'background:var(--surface-card); border:1px solid var(--surface-divider); '
        f'font-size:12px; font-weight:700; color:var(--text-primary);">{c}</span>'
        for c in chips
    )
    clear_href = "?app_area=" + _q("🗞 뉴스 수집") + "&dm_clear_filters=1"
    # 배너는 <ul class=dm-art-grid> 안에 들어가므로 grid-column:1/-1 로 전체 폭을 차지해야
    # 한 칸에 끼이지 않는다(그리드 아이템).
    return (
        '<div style="grid-column:1/-1; display:flex; align-items:center; gap:8px; flex-wrap:wrap; '
        'margin:0 0 12px; padding:10px 14px; background:var(--accent-ring,rgba(37,99,235,.10)); '
        'border:1px solid var(--surface-divider); border-radius:10px;">'
        f'{chips_html}'
        f'<span style="font-size:13px; color:var(--text-primary);">결과 <b>{n}건</b></span>'
        f'<a href="{clear_href}" target="_self" style="margin-left:auto; font-size:12.5px; '
        'font-weight:600; color:var(--accent-primary); text-decoration:none;">✕ 필터 해제</a>'
        '</div>'
    )


def _news_no_match_html(q: str = "") -> str:
    q = (q or "").strip()
    head = f'“{_html.escape(q)}” 와 일치하는' if q else "선택한 필터에 해당하는"
    return (
        '<li class="dm-art" style="grid-column:1/-1; padding:28px 18px; text-align:center; '
        'color:var(--text-muted); font-size:14px; border:1px dashed var(--surface-divider); '
        'border-radius:12px;">'
        f'{head} 뉴스가 없어요.<br>'
        '<span style="font-size:12.5px;">조건을 바꾸거나 ✕ 로 필터를 해제하세요.</span>'
        '</li>'
    )


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


def _consume_news_filter_clear_if_any() -> None:
    """`?dm_clear_filters=1` → 뉴스 필터 전체 해제: 검색어(`_news_search_q`/`_topbar_q`)와
    폼 위젯(출처·기간·정렬)을 기본값으로 되돌리고 rerun.

    폼/입력 위젯 값은 위젯 인스턴스화 **전**(=탭 fragment·topbar 렌더 전)에만 세팅
    가능하므로 render() 최상단에서 실행한다.
    """
    if not st.query_params.get("dm_clear_filters"):
        return
    st.session_state[_NEWS_SEARCH_KEY] = ""
    st.session_state["_topbar_q"] = ""
    st.session_state["_topbar_q_seen"] = ""
    st.session_state[_NEWS_F_SRC_KEY] = []
    st.session_state[_NEWS_F_PERIOD_KEY] = next(iter(_NEWS_PERIOD_OPTS))   # "최근 3일"
    st.session_state[_NEWS_F_SORT_KEY] = next(iter(_NEWS_SORT_OPTS))       # "최신순"
    if "dm_clear_filters" in st.query_params:
        del st.query_params["dm_clear_filters"]
    st.rerun()


@st.cache_data(ttl=120)
def _news_source_options() -> list[str]:
    """필터 드롭다운 옵션 — 최근 30일 수집 뉴스의 distinct 출처(가나다순).

    실제로 수집된 출처만 노출 → 빈 선택지·없는 출처 필터를 방지. 수집/업로드 시
    `.clear()` 로 무효화된다.
    """
    try:
        df = _news_db.load_news_for_days(days=30)
    except Exception:
        df = None
    if df is None or df.empty or "source" not in df.columns:
        return []
    return sorted({str(s).strip() for s in df["source"].dropna() if str(s).strip()})


@st.cache_data(ttl=60)
def _news_cards_html(q: str = "", sources: tuple[str, ...] = (),
                     days: int = 0, sort: str = "newest") -> str:
    """뉴스 카드 — 상단 검색어 `q` + 필터(출처·기간·정렬)를 적용해 렌더.

    필터·검색이 모두 기본값이면 기존 동작(최근 3일 6장, 첫 장 강조)을 그대로 유지하고,
    하나라도 활성이면 선택 기간(검색만 있고 기간 미선택이면 30일) 안에서 출처·검색어로
    좁힌 뒤 정렬해 최대 24장 + 활성 필터 배너를 보여준다.

    검색어·필터는 **인자**로 받는다(세션 직접 참조 X) — `st.cache_data` 가 조합별 캐시
    키를 잡아 결과가 올바르게 분리/갱신되고 `.clear()` 도 유지된다. `days` 는 0/3=기본
    (검색 시 30일로 자동 확대), 7·30=명시.
    """
    q = (q or "").strip()
    sources = tuple(sources or ())
    filters_active = bool(q or sources or days >= 7 or sort != "newest")
    load_days = days if days >= 7 else (30 if q else 3)
    try:
        news = _news_db.load_news_for_days(days=load_days)
    except Exception:
        news = None
    if news is None or news.empty:
        banner = _news_filter_banner_html(q, sources, days, sort, 0) if filters_active else ""
        return banner + _news_empty_html()

    # 정렬 — collected_at(없으면 published_at) 기준. oldest 면 오름차순.
    sort_col = ("collected_at" if "collected_at" in news.columns
                else "published_at" if "published_at" in news.columns else None)
    if sort_col:
        news = news.sort_values(sort_col, ascending=(sort == "oldest"))

    # 출처 필터 → 검색어 필터 (좁히는 순서)
    if sources and "source" in news.columns:
        news = news[news["source"].astype(str).isin(list(sources))]
    if q:
        news = _filter_news_by_query(news, q)

    if filters_active:
        if news is None or news.empty:
            return _news_filter_banner_html(q, sources, days, sort, 0) + _news_no_match_html(q)
        cards = "\n".join(
            _news_card_html(row, is_strong=False)
            for _, row in news.head(_MAX_SEARCH_CARDS).iterrows()
        )
        return _news_filter_banner_html(q, sources, days, sort, int(len(news))) + cards

    # 기본 — 최근 6장, 첫 장 강조 (기존 동작 유지)
    top = news.head(_MAX_NEWS_CARDS)
    return "\n".join(
        _news_card_html(row, is_strong=(i == 0))
        for i, (_, row) in enumerate(top.iterrows())
    )


def _render_news_filter_form() -> tuple[tuple[str, ...], int, str]:
    """뉴스 라이브러리 필터 — st.form(출처·기간·정렬 + 적용).

    폼 위젯은 '적용' 제출 전까지 rerun 을 일으키지 않으므로 **'적용' 눌렀을 때만**
    라이브러리가 갱신된다(요청 방법론). 반환: (선택 출처 tuple, 기간 일수, 정렬 키) —
    폼이 제출 시에만 값을 커밋하므로 여기서 읽는 값은 곧 '마지막으로 적용된' 필터다.

    `with st.form(...)` 단일 블록(열고 submit 버튼까지 한 번에 닫음)이라 chat_panel 의
    입력 폼과 동일하게 bare 모드 'active form' 누수가 없다. 단, `_render_jobs_split` 의
    bare 단위 테스트는 이 함수를 patch 해 폼 위젯을 타지 않는다.
    """
    options = _news_source_options()
    with st.container(key="dm_news_filter"):
        st.html(
            '<div class="dm-nf-head">🔎 뉴스 라이브러리 필터'
            '<span class="dm-nf-hint">출처·기간·정렬 선택 후 [적용]</span></div>'
        )
        with st.form(key="_dm_news_filter_form", clear_on_submit=False, border=False):
            c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1.1], vertical_alignment="bottom")
            with c1:
                src = st.multiselect(
                    "출처", options, key=_NEWS_F_SRC_KEY,
                    placeholder="전체 출처", help="선택한 출처만 보기(미선택=전체 출처).",
                )
            with c2:
                period = st.selectbox("기간", list(_NEWS_PERIOD_OPTS), key=_NEWS_F_PERIOD_KEY)
            with c3:
                sort = st.selectbox("정렬", list(_NEWS_SORT_OPTS), key=_NEWS_F_SORT_KEY)
            with c4:
                st.form_submit_button("적용", type="primary", use_container_width=True)
    return (
        tuple(src or ()),
        _NEWS_PERIOD_OPTS.get(period, 3),
        _NEWS_SORT_OPTS.get(sort, "newest"),
    )


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

    헤더 4 stats + 14일 sparkline 일별 수집량 + 뉴스 라이브러리 6 + 수집잡 요약.
    캐시된 helper 들이 같은 데이터를 계산해두므로 재호출은 캐시 hit.
    """
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
# 뉴스 라이브러리 필터 폼은 더 이상 렌더하지 않는다(상단 검색이 대체). 레거시
# 빌더(_render_news_filter_form/_render_jobs_split/_render_dm_tabs/_news_cards_html)
# 는 호환·테스트용으로 유지하되 화면 흐름에서는 호출하지 않는다.

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


def _sc_card_visual_html(row: dict) -> str:
    """카드 시각(사진+메타+제목+본문 일부). 클릭은 위에 겹친 투명 버튼이 처리 → 앵커 없음."""
    title = _html.escape(str(row.get("title") or "(제목 없음)"))
    img = str(row.get("image_url", "") or "").strip()
    body_src = " ".join(
        str(row.get("summary_llm") or row.get("summary") or row.get("content") or "").split()
    )
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
    """📋 데이터 표 — 수집한 모든 뉴스를 표로(사진 썸네일·링크 포함). 상단 검색 적용."""
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
        rows.append({
            "사진": str(r.get("image_url", "") or ""),
            "제목": str(r.get("title", "") or ""),
            "대분류": _SC_CAT_LABEL.get(str(r.get("_cat", "")), ""),
            "출처": str(r.get("_chan", "") or ""),
            "수집": _news_age_label(when) or when[:16],
            "키워드": str(r.get("keywords_llm") or r.get("keywords") or ""),
            "링크": str(r.get("link", "") or ""),
        })
    df = _pd.DataFrame(rows)
    with st.container(key="sc_table"):
        st.caption(f"수집한 뉴스 전체 {len(df)}건 — 상단 검색으로 좁힐 수 있어요.")
        st.dataframe(
            df, use_container_width=True, hide_index=True, height=560,
            column_config={
                "사진": st.column_config.ImageColumn("사진", width="small"),
                "제목": st.column_config.TextColumn("제목", width="large"),
                "키워드": st.column_config.TextColumn("키워드", width="medium"),
                "링크": st.column_config.LinkColumn("링크", display_text="원문 ↗", width="small"),
            },
        )


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


def _render_collect_actionbar() -> None:
    """메인 카드뷰 액션바 — [🔄 지금 뉴스 수집] + [⚙ 수집 설정] (소켓 rerun)."""
    with st.container(key="sc_actionbar"):
        c1, c2, _sp = st.columns([1.3, 1, 3])
        with c1:
            if st.button(
                "🔄 지금 뉴스 수집", key="_dm_collect_btn", type="primary",
                use_container_width=True,
                help="페르소나 관심사 키워드(없으면 자동화·AI)로 지금 뉴스를 수집하고 화면을 새로 그립니다.",
            ):
                st.session_state["_do_dm_collect"] = True
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
    """⚙ 수집 설정 서브뷰 — 키워드 + 포탈(출처) + 수집 실행·이력."""
    _render_dm_header(dm_stats)
    with st.container(key="sc_settings_back"):
        if st.button("← 뉴스 목록", key="_sc_back_btn"):
            st.session_state["sc_collect_view"] = "cards"
            st.rerun()
    # 키워드 설정(현황 요약 + 페르소나 진입)
    st.html(_components.prepare_screen_html(_dm_kw_body_html(persona)))
    # 포탈/출처 설정 — 기본 토글 + 커스텀 RSS 추가
    _render_src_table(dm_stats)
    _render_src_add_form()
    # 수집 실행(설정에서도 가능) + 이력 상세
    _render_collect_button()
    st.html(_components.prepare_screen_html(_sc_history_html()))


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
    img = str(row.get("image_url", "") or "").strip()
    chan = _news_channel_of(row.get("source", ""), row.get("press", ""))
    when = str(row.get("collected_at") or row.get("published_at") or "")
    age = _news_age_label(when)
    summary = str(row.get("summary_llm") or row.get("summary") or "").strip()
    content = str(row.get("content") or "").strip()

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
    if summary:
        parts.append(f'<div class="sc-modal-summary">{_html.escape(summary)}</div>')
    if content:
        paras = "".join(
            f"<p>{_html.escape(p.strip())}</p>" for p in content.splitlines() if p.strip()
        )
        parts.append(f'<div class="sc-modal-body">{paras}</div>')
    elif not summary:
        parts.append('<div class="sc-modal-body"><p>본문이 아직 수집되지 않았어요. '
                     '원본 기사에서 확인하세요.</p></div>')
    if link[:4].lower() == "http":
        parts.append(
            f'<a class="sc-modal-link" href="{_html.escape(link, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">원본 기사 열기 ↗</a>'
        )
    parts.append('</div>')
    st.html(_components.prepare_screen_html("".join(parts)))

    if st.button("✕ 닫기", key="_sc_news_close", use_container_width=True):
        st.session_state.pop("_sc_open_news", None)
        st.rerun()


def _render_news_modal_if_open() -> None:
    """`_sc_open_news` 플래그가 있으면 기사 모달을 띄운다(dismissible=False — ✕ 로만 닫음)."""
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

    `?refresh=now`(또는 '지금 뉴스 수집' 버튼)는 첫 단계에서 1회 소비 → 캐시
    invalidate + 토스트. 메인은 카드뷰(수집 요약 → 액션바 → 대분류 탭/출처칩/카드),
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
    else:
        _render_dm_header(dm_stats)        # 수집 현황 요약(KPI 4)
        _render_collect_actionbar()         # [지금 수집][⚙ 수집 설정]
        _render_news_browser(persona)       # 대분류 탭 + 출처칩 + 사진 카드

    _render_news_modal_if_open()             # 카드 클릭 시 기사 모달


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


# 탭 표시 순서 — 뉴스 그룹(jobs·kw·src) 다음 작업 그룹(task·manage).
_DM_DISPLAY_TABS: tuple[str, ...] = ("jobs", "kw", "src", "task", "manage")
# 뉴스 수집 화면의 탭(구 데이터 관리 '뉴스' 그룹). '작업 정의' 화면(task·manage)은
# 탭 없이 세로 배치(render_taskdef)라 여기 포함하지 않는다.
_DM_COLLECT_TABS: tuple[str, ...] = ("jobs", "kw", "src")


def _render_dm_header(dm_stats: dict[str, str | int]) -> None:
    """상단 고정 헤더(브레드크럼·설명·KPI 4종) — 탭 바 위에 1회만.

    탭 전환은 _render_dm_tabs fragment 안에서만 일어나므로 이 헤더는 다시 그려지지
    않는다 (탭마다 KPI 가 깜빡이던 monolithic st.html 문제 제거)."""
    template = _DM_TEMPLATE.read_text(encoding="utf-8")
    head = template.split("{{DM_TABS}}", 1)[0]  # <div class=dm-shell>…<header>…</header>
    head_html = (
        head
        .replace("{{ACTIVE_SOURCES}}", _html.escape(str(dm_stats["active_sources"])))
        .replace("{{TODAY_COUNT}}", _html.escape(str(dm_stats["today_count"])))
        .replace("{{TOTAL_CHUNKS}}", _html.escape(str(dm_stats["total_chunks"])))
        .replace("{{LAST_UPDATE}}", _html.escape(str(dm_stats["last_update"])))
    ) + "</div>"  # split 로 잘려나간 dm-shell 닫기 보강
    st.html(_components.prepare_screen_html(head_html))


def _render_jobs_split(dm_stats: dict[str, str | int]) -> None:
    """jobs 탭 본문 — 수집잡 + 뉴스 라이브러리(.dm-split). 헤더는 _render_dm_header 가
    이미 그렸으므로 여기선 {{DM_TABS}} 이후 본문만."""
    # '지금 뉴스 수집' — 앵커(?refresh=now)였던 CTA 를 st.button 위젯으로(소켓 rerun,
    # 문서 reload·흰 깜빡임 없음). 본문(.dm-split) 위 우측에 핀. {{INGEST_REFRESH_CTA}}
    # 자리는 비운다.
    _render_collect_button()
    # 뉴스 라이브러리 필터(출처·기간·정렬) — 폼 '적용' 시에만 커밋. 반환값을 카드 빌더 인자로.
    f_sources, f_days, f_sort = _render_news_filter_form()
    q = str(st.session_state.get(_NEWS_SEARCH_KEY, "") or "").strip()
    template = _DM_TEMPLATE.read_text(encoding="utf-8")
    body = template.split("{{DM_TABS}}", 1)[1]
    from store import ui_prefs as _uiprefs
    hist = _hist_html(_uiprefs.load().get("theme") == "dark")
    html_out = (
        '<div class="dm-shell">' + body
        .replace("{{NEWS_CARDS}}", _news_cards_html(q, f_sources, f_days, f_sort))
        .replace("{{INGEST_JOBS}}", _ingest_jobs_html())
        .replace("{{INGEST_REFRESH_CTA}}", "")
        .replace("{{HIST_HEAD}}", hist["head"])
        .replace("{{HIST_SVG}}", hist["svg"])
        .replace("{{HIST_X}}", hist["foot"])
        .replace("{{HIST_RUNS}}", hist["runs"])
        .replace("{{DM_MAIN_BODY_OPEN}}", "")
        .replace("{{DM_MAIN_BODY_CLOSE}}", "")
    )
    html_out = _strip_dm_mockups(html_out)
    st.html(_components.prepare_screen_html(html_out))


# 세그먼트 탭 바용 짧은 라벨(+아이콘) — 좁은 본문 컬럼에 5개가 안 넘치게.
_DM_TAB_SHORT: dict[str, str] = {
    "jobs": "🗞 수집잡", "kw": "🔑 키워드", "src": "⚙️ 출처",
    "task": "📊 엑셀 업로드", "manage": "✏️ 작업 정의",
}


@st.fragment
def _render_dm_tabs(dm_stats: dict[str, str | int], persona,
                    tabs: tuple[str, ...] = _DM_COLLECT_TABS) -> None:
    """탭 바(segmented_control) + 활성 탭 본문만 조건부 렌더 — fragment 스코프.

    탭 전환은 이 fragment 만 rerun → 헤더·사이드바·우측 채팅은 그대로, 활성 탭
    본문만 부분 갱신. 비활성 탭 본문은 계산하지 않는다(조건부 렌더 — st.tabs 의
    eager 렌더 비용 제거). 활성 탭은 session_state(`_dm_active_tab`)에 보존 →
    출처 토글·수집 등 앵커 리로드 후에도 같은 탭 유지.

    `tabs` 는 화면별 탭 부분집합(뉴스 수집=jobs·kw·src). 작업 정의는 탭이 없어
    이 함수를 쓰지 않는다."""
    default = tabs[0]
    if st.session_state.get("_dm_active_tab") not in tabs:
        st.session_state["_dm_active_tab"] = default
    with st.container(key="dm_tabbar"):
        active = st.segmented_control(
            "뉴스 수집 탭", list(tabs),
            format_func=lambda t: _DM_TAB_SHORT[t],
            key="_dm_active_tab", label_visibility="collapsed",
        ) or st.session_state["_dm_active_tab"]
    if active not in tabs:
        active = default
    _render_dm_tab_panel(active, dm_stats, persona)


def _render_dm_tab_panel(tab_key: str, dm_stats: dict[str, str | int], persona) -> None:
    """활성 탭 본문만 렌더(조건부). 무거운 jobs/manage 도 활성일 때만 계산."""
    if tab_key == "jobs":
        _render_jobs_split(dm_stats)
    elif tab_key == "manage":
        from ui import task_def_manage as tdm
        tdm.render(st.query_params)
    elif tab_key == "src":
        # 출처 표(토글/제거)는 위젯이라 HTML 단일 블록이 아니다 → 전용 렌더.
        _render_src_table(dm_stats)
        _render_src_add_form()
    else:
        st.html(_components.prepare_screen_html(
            _dm_tab_body_html(tab_key, persona=persona, dm_stats=dm_stats)))
        if tab_key == "task":
            _render_task_def_upload()


def _render_collect_button() -> None:
    """'지금 뉴스 수집' — 구 앵커(`?refresh=now`) 대체 위젯.

    앵커는 클릭 시 문서 전체 reload(흰 깜빡임)였다. st.button 은 소켓 rerun → 클릭 시
    `_do_dm_collect` pending 세팅 후 `st.rerun()`(on_click 미사용), 다음 run 의
    `_consume_refresh_if_any` 가 collect_batch 를 실행한다. 룩은 `.st-key-dm_collect_cta`
    스코프(우측 정렬 + accent 채움)로 구 `.dm-btn-primary` 에 맞춘다.
    """
    with st.container(key="dm_collect_cta"):
        if st.button(
            "🔄 지금 뉴스 수집", key="_dm_collect_btn", type="primary",
            help="페르소나 관심사 키워드(없으면 자동화·AI)로 지금 뉴스를 수집하고 화면을 새로 그립니다.",
        ):
            st.session_state["_do_dm_collect"] = True
            st.rerun()


def _consume_refresh_if_any() -> bool:
    """수집 트리거 1회 소비 — collect_batch 동기 호출 + 캐시 무효화 + 토스트.

    트리거는 둘 중 하나: '지금 뉴스 수집' 버튼이 세팅한 `_do_dm_collect` pending(신규,
    문서 reload 없음) 또는 레거시 `?refresh=now` 쿼리(북마크/딥링크 호환). 수집 키워드는
    페르소나 관심사(interest_tasks + interest_lv3). 비어 있으면 기본 키워드(자동화·AI)로
    폴백하고, tech 사이트·커스텀 RSS 는 키워드 무관하게 항상 함께 수집한다 — 빈
    페르소나에서도 실제로 수집을 실행한다. 수집 실패 시 error 토스트(캐시는 안전하게
    무효화 — 다음 렌더가 최신).
    """
    triggered = bool(st.session_state.pop("_do_dm_collect", False))
    if not triggered and st.query_params.get("refresh") != "now":
        return False

    # 모든 dm 관련 캐시 무효화 — `_archive_stats_dm` 는 이제 `board_v2._archive_stats()`
    # 위임이므로 그 내부의 `_board_kpis` 60초 캐시도 함께 비워야 좌측 nav 카운트가
    # 즉시 새 수집 결과로 갱신된다 (Phase 2 dedup 회귀 방지).
    from ui import board_v2 as _bv2  # lazy

    for fn in (_dm_stats, _ingest_jobs_html, _hist_html, _news_cards_html,
               _news_source_options, _sc_browse_records,
               _archive_stats_dm, _bv2._board_kpis):
        if hasattr(fn, "clear"):
            fn.clear()

    # 수집 실행 — 페르소나 관심사 키워드(없으면 자동화·AI 폴백) + 등록된 커스텀 RSS.
    # tech 사이트·RSS 는 키워드 무관하게 수집되므로 빈 페르소나에서도 건너뛰지 않는다.
    try:
        from ui.board_v2 import _collect_keywords_with_default, _collect_extra_feeds
        from scraping.run_daily import collect_batch
        persona = app_shell.get_persona()
        kws, used_default = _collect_keywords_with_default(persona)
        extra_feeds = _collect_extra_feeds()
        report = collect_batch(kws, max_results=10, extra_feeds=extra_feeds)
        try:  # 런 로그 기록 — '수집 헬스' 가 읽음. 로깅 실패가 수집을 깨면 안 됨.
            from store import run_log
            run_log.record_run(report, trigger="manual")
        except Exception:  # noqa: BLE001
            pass
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
            kw_label = (
                "관심사가 비어 기본 키워드(자동화·AI)" if used_default
                else f"{len(kws)}개 키워드"
            )
            st.session_state["_dm_refresh_toast"] = (
                "ok",
                f"✓ {kw_label}{feeds_label}로 {n_articles}건 수집 "
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
        for fn in (_dm_stats, _ingest_jobs_html, _hist_html, _news_cards_html,
                   _news_source_options, _archive_stats_dm, _bv2._board_kpis):
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


