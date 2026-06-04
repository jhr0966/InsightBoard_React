"""데이터 관리 — 순수 프레젠테이션 빌더 (HTML/라우팅, I/O·st 없음).

`ui/data_management_v2.py` 가 1.6k 로 비대해 토큰·가독성을 해쳐, **부작용 없는**
(Streamlit 호출·데이터 I/O 가 없는) 빌더/라우팅 헬퍼를 분리했다. 입력으로 받은
데이터·인자만으로 HTML 문자열이나 (group, tab) 같은 순수 값을 만든다.

`data_management_v2` 가 이 심볼들을 re-import 해 기존 참조(테스트 포함)는 그대로
동작한다(`from ui.data_management_render import ...`). 데이터를 읽거나 `st.*` 를
호출하는 빌더(수집 헬스·타임라인·탭 본문 등)는 화면 모듈에 남는다.
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone
from urllib.parse import quote


# ── 출처별 그라데이션 — 시안과 일관성 유지 ──────────────────────
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


# ── 탭/그룹 정의 ────────────────────────────────────────────
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


# ── 뉴스 카드 프레젠테이션 ──────────────────────────────────

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


def _news_card_html(row, *, is_strong: bool = False) -> str:
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


# ── 탭/그룹 라우팅 + 네비 HTML ──────────────────────────────

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


def _dm_tab_href(tab: str) -> str:
    """탭 선택 URL — `?app_area=🧱+데이터+관리&dm_grp=<grp>&dm_tab=<tab>`.

    그룹 기본 탭 (`jobs`/`task`) 은 `dm_tab` 생략, 그 외에는 명시.
    `dm_grp` 는 항상 명시 (혼동 방지). 단 news 그룹 + jobs 탭은 둘 다 생략 (깨끗한 URL).
    """
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


def _src_action_href(action: str, src_name: str) -> str:
    """출처 설정 액션 URL — `?dm_tab=src&src_action=toggle|remove&src_name=`."""
    parts = [
        f"app_area={quote('🧱 데이터 관리')}",
        "dm_tab=src",
        f"src_action={quote(action)}",
        f"src_name={quote(src_name)}",
    ]
    return "?" + "&".join(parts)
