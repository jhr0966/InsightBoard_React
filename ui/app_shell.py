"""v2 디자인 시스템의 글로벌 크롬 — 모든 화면 공유.

3대 컴포넌트:
  - render_topbar()  : 풀폭 fixed 헤더 (60px) — WORKFLOW / 페이지명 + 검색 + 알림/아바타
  - render_app_side(): 좌측 고정 패널 (264px, 접으면 44px) — 브랜드 + 페르소나 + 5-nav
  - render_app_sola(): 우측 고정 패널 (344px, 접으면 60px) — SOLA 컨텍스트 + 빠른 질문

인터랙티브 동작(Ctrl+K 검색, SOLA 전송, 패널 접기 등)은 화면별 후속 PR에서 와이어업.
지금은 마크업/스타일만 — visual handoff 충실.
"""
from __future__ import annotations

import html as _html
from datetime import datetime
from urllib.parse import quote

import streamlit as st

from config import llm_backend, llm_model
from persona.schema import Persona
from sola.client import is_configured as llm_ready


def get_persona() -> Persona:
    """`session_state["persona"]` → 없으면 `persona.store.load()` → 캐시 후 반환.

    Phase 2 dedup: board/insights/archive/sola_workshop/data_management 의 동일
    구현(`_load_persona`)을 단일 진입점으로 통합. session_state 키 `persona` 는
    `app.py` 가 항상 갱신해두므로 통상 첫 분기에서 반환된다.
    """
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


# ── 패널 접기/펴기 — query-param 기반 상태 ────────────────────────────────
# `<a href>` 클릭이 full page reload 를 일으켜 session_state 가 유지 안 됨.
# URL 의 ?side=c / ?sola=c 를 단일 진실로 사용. 토글 링크는 현재 상태에서
# 반전된 URL 을 미리 계산해 hardcode.


def consume_panel_toggle() -> None:
    """현재는 noop — query-param 기반이라 별도 소비 불필요. 인터페이스 유지."""
    return None


def _side_collapsed() -> bool:
    return st.query_params.get("side") == "c"


def _sola_collapsed() -> bool:
    return st.query_params.get("sola") == "c"


def _toggle_href(panel: str) -> str:
    """현재 area + 다른 패널 상태는 보존, 지정 패널만 토글하는 URL 생성."""
    area = st.session_state.get("app_area", "📊 오늘의 보드")
    cur_side = _side_collapsed()
    cur_sola = _sola_collapsed()
    new_side = (not cur_side) if panel == "side" else cur_side
    new_sola = (not cur_sola) if panel == "sola" else cur_sola
    parts = [f"app_area={quote(area)}"]
    if new_side:
        parts.append("side=c")
    if new_sola:
        parts.append("sola=c")
    return "?" + "&".join(parts)


# ── 5-nav 정의 (sidebar.AREAS 와 1:1 대응) ─────────────────────
_NAV_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    # (area_key, title, subtitle, svg_d_path)
    (
        "📊 오늘의 보드",
        "오늘의 보드",
        "맞춤 인사이트",
        "<rect x='3' y='3' width='7' height='9' rx='1'/>"
        "<rect x='14' y='3' width='7' height='5' rx='1'/>"
        "<rect x='14' y='12' width='7' height='9' rx='1'/>"
        "<rect x='3' y='16' width='7' height='5' rx='1'/>",
    ),
    (
        "🧱 데이터 관리",
        "데이터 관리",
        "수집 · 둘러보기",
        "<ellipse cx='12' cy='5' rx='9' ry='3'/>"
        "<path d='M3 5v14a9 3 0 0018 0V5M3 12a9 3 0 0018 0'/>",
    ),
    (
        "🔎 인사이트 분석",
        "인사이트 분석",
        "트렌드 · 매트릭스",
        "<circle cx='11' cy='11' r='8'/><path d='M21 21l-4.35-4.35'/>",
    ),
    (
        "🤖 SOLA 작업실",
        "SOLA 작업실",
        "초안 · 대화",
        "<path d='M12 2L9.5 8.5 3 11l6.5 2.5L12 20l2.5-6.5L21 11l-6.5-2.5z'/>",
    ),
    (
        "📦 산출물 보관함",
        "산출물 보관함",
        "북마크 · 채택",
        "<path d='M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z'/>"
        "<path d='M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12'/>",
    ),
)


def _avatar_letter(persona: Persona) -> str:
    src = persona.name or persona.dept or "?"
    return _html.escape(src.strip()[:1] or "?")


def render_setup_banner_if_needed() -> bool:
    """LLM 키 미설정 시 본문 상단에 안내 배너 1줄.

    설정 완료(`llm_ready()`) 면 아무것도 그리지 않는다. 배너는 본문 안쪽에 inline
    sticky 로 들어가서 .app-side / .app-sola 사이 영역만 차지한다 (fixed 가 아님).

    Returns:
        배너를 실제로 렌더했으면 True. 뒤따르는 sticky 배너(예: SOLA handoff)가
        겹치지 않도록 stack offset 을 줄 때 사용.
    """
    if llm_ready():
        return False
    backend_safe = _html.escape(llm_backend())
    st.html(
        f"""
        <style>
          body:has(.db-topbar) .app-llm-banner {{
            position: sticky; top: 76px; z-index: 8;
            display: flex; align-items: center; gap: 10px;
            margin: 0 24px 14px; padding: 9px 14px;
            background: #FEF3C7; border: 1px solid #FCD34D; border-radius: 8px;
            font-size: 13px; color: #78350F; font-weight: 600;
          }}
          body:has(.db-topbar) .app-llm-banner b {{ color: #78350F; }}
          body:has(.db-topbar) .app-llm-banner .app-llm-banner-sub {{
            font-weight: 500; color: #92400E;
          }}
          body:has(.db-topbar) .app-llm-banner .app-llm-banner-dot {{
            width: 8px; height: 8px; border-radius: 50%; background: #F59E0B;
            box-shadow: 0 0 0 3px rgba(245,158,11,0.18);
          }}
        </style>
        <div class="app-llm-banner">
          <span class="app-llm-banner-dot"></span>
          <b>LLM 미설정</b>
          <span class="app-llm-banner-sub">
            현재 백엔드 <b>{backend_safe}</b> · API 키가 없어 요약·제안서·채팅 응답이 미리보기로만 표시됩니다. ⚙ 설정에서 키를 입력하세요.
          </span>
        </div>
        """
    )
    return True


def render_command_palette() -> None:
    """⌘K / Ctrl+K 커맨드 팔레트 (CSS-only, JS 없음).

    Streamlit 의 `st.html` 은 인라인 `<script>` 를 실행하지 않으므로, 키보드
    단축키 대신 checkbox 해킹으로 토글한다:
      - topbar 검색창(`<label for="v2-cmdk">`) 클릭 → 모달 open
      - 백드롭 클릭 → close
    모달 항목은 모두 `<a href="?app_area=...">` 라 선택 시 실제 네비게이션이
    동작한다 (query-param 단일 진실 패턴과 일치).

    `?app_area` 인코딩은 `_NAV_ITEMS` 와 동일 규칙(quote)을 사용. 호출은 페이지당
    1회 (app.py), `.db-topbar` 가 있는 v2 셸에서만 노출.
    """
    rows = []
    for area_key, title, subtitle, svg_d in _NAV_ITEMS:
        href = f"?app_area={quote(area_key)}"
        rows.append(
            f'<a class="v2-cmdk-row" href="{href}" target="_self">'
            f'<span class="v2-cmdk-ic">'
            f"<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' "
            f"fill='none' stroke='#475569' stroke-width='2' stroke-linecap='round' "
            f"stroke-linejoin='round'>{svg_d}</svg></span>"
            f'<span class="v2-cmdk-txt"><b>{_html.escape(title)}</b>'
            f'<small>{_html.escape(subtitle)}</small></span>'
            f'<span class="v2-cmdk-go">↵</span>'
            f'</a>'
        )
    # 페르소나 편집 바로가기
    rows.append(
        '<a class="v2-cmdk-row" href="?persona_editor=1" target="_self">'
        '<span class="v2-cmdk-ic">'
        "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' "
        "fill='none' stroke='#475569' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2'/><circle cx='12' cy='7' r='4'/></svg></span>"
        '<span class="v2-cmdk-txt"><b>프로필 / 페르소나 편집</b><small>관심 공정 · 부서 설정</small></span>'
        '<span class="v2-cmdk-go">↵</span>'
        '</a>'
    )
    rows_html = "\n".join(rows)

    st.html(
        f"""
        <style>
          body:has(.db-topbar) .v2-cmdk-toggle {{ display: none; }}
          body:has(.db-topbar) .v2-cmdk-backdrop {{
            display: none; position: fixed; inset: 0; z-index: 90;
            background: rgba(15,23,42,0.40); backdrop-filter: blur(2px);
          }}
          body:has(.db-topbar) .v2-cmdk-modal {{
            display: none; position: fixed; z-index: 91;
            top: 84px; left: 50%; transform: translateX(-50%);
            width: min(560px, calc(100vw - 48px));
            background: #fff; border: 1px solid var(--surface-divider, #E5E7EB);
            border-radius: 14px; box-shadow: 0 24px 60px rgba(15,23,42,0.28);
            overflow: hidden;
          }}
          body:has(.db-topbar) .v2-cmdk-toggle:checked ~ .v2-cmdk-backdrop {{ display: block; }}
          body:has(.db-topbar) .v2-cmdk-toggle:checked ~ .v2-cmdk-modal {{ display: block; }}
          body:has(.db-topbar) .v2-cmdk-head {{
            display: flex; align-items: center; gap: 8px;
            padding: 12px 16px; border-bottom: 1px solid var(--surface-divider, #E5E7EB);
            font-size: 13px; color: var(--text-muted, #6B7280);
          }}
          body:has(.db-topbar) .v2-cmdk-head b {{ color: var(--text-primary, #0F172A); }}
          body:has(.db-topbar) .v2-cmdk-kbd {{
            margin-left: auto; font-size: 11px; color: var(--text-muted, #9CA3AF);
            border: 1px solid var(--surface-divider, #E5E7EB); border-radius: 5px;
            padding: 1px 6px; font-family: var(--font-mono, monospace);
          }}
          body:has(.db-topbar) .v2-cmdk-list {{ padding: 6px; max-height: 60vh; overflow-y: auto; }}
          body:has(.db-topbar) .v2-cmdk-row {{
            display: flex; align-items: center; gap: 12px;
            padding: 10px 12px; border-radius: 9px; text-decoration: none;
            color: var(--text-primary, #0F172A);
          }}
          body:has(.db-topbar) .v2-cmdk-row:hover {{ background: var(--surface-soft, #F3F5F8); }}
          body:has(.db-topbar) .v2-cmdk-ic {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 30px; height: 30px; border-radius: 7px;
            background: var(--surface-soft, #F3F5F8); flex-shrink: 0;
          }}
          body:has(.db-topbar) .v2-cmdk-txt {{ display: flex; flex-direction: column; line-height: 1.3; }}
          body:has(.db-topbar) .v2-cmdk-txt b {{ font-size: 14px; font-weight: 700; }}
          body:has(.db-topbar) .v2-cmdk-txt small {{ font-size: 12px; color: var(--text-muted, #6B7280); }}
          body:has(.db-topbar) .v2-cmdk-go {{
            margin-left: auto; font-size: 13px; color: var(--text-muted, #9CA3AF);
          }}
        </style>
        <input type="checkbox" id="v2-cmdk" class="v2-cmdk-toggle" aria-hidden="true">
        <label class="v2-cmdk-backdrop" for="v2-cmdk" aria-label="팔레트 닫기"></label>
        <div class="v2-cmdk-modal" role="dialog" aria-label="빠른 이동">
          <div class="v2-cmdk-head">
            🔎 <b>빠른 이동</b> — 작업 화면으로 점프
            <label class="v2-cmdk-kbd" for="v2-cmdk" style="cursor:pointer;">닫기  esc</label>
          </div>
          <div class="v2-cmdk-list">
            {rows_html}
          </div>
        </div>
        """
    )


def _notif_count() -> int:
    """topbar 알림 배지 수 — 채택 대기(pending) 제안서 건수.

    현재 유일하게 "사용자가 처리할 거리"인 신호. 0 이면 배지/점을 숨겨
    빈 알림을 가짜로 표시하지 않는다(정직한 UI). 실패 시 0.
    """
    try:
        from store import bookmarks as _bm
        summary = _bm.summary_counts()
        return int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
    except Exception:
        return 0


def render_topbar(
    *,
    page_title: str,
    eyebrow_current: str | None = None,
    refresh_label: str = "",
    fresh_kind: str = "fresh",
) -> None:
    """`.db-topbar` 렌더 — 모든 v2 화면 상단.

    Args:
        page_title: 큰 타이틀 (예: "오늘의 보드").
        eyebrow_current: WORKFLOW / <이 부분>. 미지정 시 page_title 재사용.
        refresh_label: 우측 갱신 시각 라벨 (예: "06:24 갱신"). 빈 문자열이면 숨김.
        fresh_kind: "fresh"(녹) / "accent"(파랑) / "warn"(주황) / "" (배지 없음).

    알림/설정 버튼은 정직화되어 실제 동작을 가진다:
        - 🔔 알림 → 산출물 보관함. 채택 대기(pending) 건이 있을 때만 빨간 점 +
          개수 노출. 0 이면 점 없이 "새 알림 없음" 툴팁.
        - ⚙ 설정 → 프로필/페르소나 편집(`?persona_editor=1`).
    """
    page_title_safe = _html.escape(page_title)
    eyebrow_safe = _html.escape(eyebrow_current or page_title)
    refresh_safe = _html.escape(refresh_label) if refresh_label else ""

    fresh_html = ""
    if fresh_kind in {"fresh", "accent", "warn"}:
        cls = "db-topbar-fresh"
        if fresh_kind == "accent":
            cls += " db-topbar-fresh-accent"
        elif fresh_kind == "warn":
            cls += " db-topbar-fresh-warn"
        label = {"fresh": "FRESH", "accent": "LIVE", "warn": "STALE"}[fresh_kind]
        fresh_html = f'<span class="{cls}">{label}</span>'

    date_html = ""
    if refresh_safe:
        date_html = (
            '<span class="db-topbar-date">'
            '<span class="db-topbar-date-dot"></span>'
            f"{refresh_safe}"
            "</span>"
        )

    # ── 알림: 채택 대기 건이 있을 때만 점 + 개수 (정직한 신호) ──
    n_notif = _notif_count()
    archive_href = "?app_area=" + quote("📦 산출물 보관함")
    if n_notif > 0:
        notif_title = _html.escape(f"채택 대기 {n_notif}건 · 산출물 보관함에서 확인")
        notif_dot = (
            f'<span class="db-hdr-dot"></span>'
            f'<span class="db-hdr-badge">{n_notif if n_notif < 100 else "99+"}</span>'
        )
    else:
        notif_title = "새 알림 없음 · 산출물 보관함 열기"
        notif_dot = ""

    st.html(
        f"""
        <header class="db-topbar">
          <div class="db-topbar-l">
            <div class="db-topbar-eye">
              <span class="db-topbar-eye-k">WORKFLOW</span>
              <span class="db-topbar-eye-sep">/</span>
              <span class="db-topbar-eye-cur">{eyebrow_safe}</span>
            </div>
            <div class="db-topbar-title-row">
              <h1 class="db-topbar-title">{page_title_safe}</h1>
              {date_html}
              {fresh_html}
            </div>
          </div>

          <div class="db-topbar-c">
            <label class="db-hdr-search" for="v2-cmdk" style="cursor:pointer;" title="빠른 이동 (⌘K)">
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='15' height='15' viewBox='0 0 24 24' fill='none' stroke='#475475'
                   stroke-width='2' stroke-linecap='round' stroke-linejoin='round'
                   style='color:var(--text-muted);'>
                <circle cx='11' cy='11' r='8'/><path d='M21 21l-4.35-4.35'/>
              </svg>" width="15" height="15" alt="" />
              <span class="db-hdr-search-ph">뉴스 · 작업 · 키워드 검색</span>
              <span class="db-hdr-search-kbd">⌘K</span>
            </label>
          </div>

          <div class="db-topbar-r">
            <a class="db-hdr-btn" href="{archive_href}" title="{notif_title}" target="_self" aria-label="알림">
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='#475569'
                   stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                <path d='M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0'/>
              </svg>" width="16" height="16" alt="" />
              {notif_dot}
            </a>
            <a class="db-hdr-btn" href="?persona_editor=1" title="설정 · 프로필 / 페르소나" target="_self" aria-label="설정">
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='#475569'
                   stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                <circle cx='12' cy='12' r='3'/>
                <path d='M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 008 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.6 15 1.65 1.65 0 003.09 14H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 008 4.6 1.65 1.65 0 009 3.09V3a2 2 0 014 0v.09A1.65 1.65 0 0014 4.6a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9c.16.5.66.91 1.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z'/>
              </svg>" width="16" height="16" alt="" />
            </a>
            <div class="db-topbar-divider"></div>
            <a class="db-topbar-avatar" href="?persona_editor=1" title="프로필 / 페르소나 편집" target="_self">{_avatar_letter(_get_persona())}</a>
          </div>
        </header>
        <div class="v2-scroll-fade" aria-hidden="true"></div>
        """
    )


def render_app_side(*, active_area: str, persona: Persona, stats: dict[str, int]) -> None:
    """`.app-side` 렌더 — 브랜드 + 페르소나 카드 + 5-nav.

    Args:
        active_area: 현재 활성 area 키 (예: "📊 오늘의 보드").
        persona: Persona 객체.
        stats: {"match_today": int, "opportunities": int, "pending_adopt": int}.
    """
    # Phase A: 좌측 네비가 네이티브 st.sidebar(`sidebar.render`) 단일 소스로 이전됨.
    # 이 고정 HTML 패널(.app-side)은 더 이상 렌더하지 않는다 — 호출부 호환용 no-op.
    # (아래 본문은 Phase C 데드 코드 정리에서 함수째 삭제 예정.)
    return None
    avatar = _avatar_letter(persona)
    name = _html.escape(persona.name or "사용자")
    role = _html.escape(persona.dept or "부서 미설정")
    job = _html.escape(persona.job or "직무 미설정")
    interests = list(persona.interest_lv3 or [])

    interest_chips = ""
    for chip in interests[:2]:
        interest_chips += f'<span class="app-side-chip">{_html.escape(chip)}</span>'
    if len(interests) > 2:
        interest_chips += f'<span class="app-side-chip app-side-chip-more">+{len(interests) - 2}</span>'
    if not interest_chips:
        interest_chips = '<span class="app-side-chip app-side-chip-more">미설정</span>'

    match_today = int(stats.get("match_today", 0))
    opportunities = int(stats.get("opportunities", 0))
    pending = int(stats.get("pending_adopt", 0))

    nav_html = []
    for area_key, title, subtitle, svg_d in _NAV_ITEMS:
        is_active = area_key == active_area
        cls = "app-side-nav-item app-side-nav-active" if is_active else "app-side-nav-item"
        cnt_cls = "app-side-nav-cnt app-side-nav-cnt-active" if is_active else "app-side-nav-cnt"
        # 카운트 노출은 활성 + opportunities 둘만 (시안 매칭)
        if area_key == "📊 오늘의 보드":
            cnt = match_today
        elif area_key == "🔎 인사이트 분석":
            cnt = opportunities
        elif area_key == "📦 산출물 보관함":
            cnt = pending
        else:
            cnt = None
        cnt_html = f'<span class="{cnt_cls}">{cnt}</span>' if cnt is not None else ""
        href = f"?app_area={quote(area_key)}"
        nav_html.append(
            f"""<a class="{cls}" href="{href}" target="_self">
              <span class="app-side-nav-i">
                <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none'
                     stroke='#475569' stroke-width='2'
                     stroke-linecap='round' stroke-linejoin='round'>{svg_d}</svg>" width="14" height="14" alt="" />
              </span>
              <div>
                <div class="app-side-nav-t">{_html.escape(title)}</div>
                <div class="app-side-nav-s">{_html.escape(subtitle)}</div>
              </div>
              {cnt_html}
            </a>"""
        )

    backend_safe = _html.escape(llm_backend())
    model_safe = _html.escape(llm_model() or "미설정")
    foot_dot_cls = "app-side-foot-dot" if llm_ready() else "app-side-foot-dot app-side-foot-dot-warn"

    collapsed = _side_collapsed()
    side_cls = "app-side app-side-collapsed" if collapsed else "app-side"
    toggle_href = _toggle_href("side")
    # 접힘/펼침 양쪽 버튼 — CSS 가 collapsed 상태에 따라 한 쪽만 노출
    side_collapse_btn = (
        f'<a class="app-side-collapse" href="{toggle_href}" title="사이드바 접기" target="_self">'
        f'<img src="data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'14\' height=\'14\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'#475569\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><polyline points=\'15 18 9 12 15 6\'/></svg>" width="14" height="14" alt="" />'
        f'</a>'
    )
    side_rail_open_btn = (
        f'<a class="app-side-rail-open" href="{toggle_href}" title="사이드바 펴기" target="_self">'
        f'<img src="data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'13\' height=\'13\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'#475569\' stroke-width=\'2.4\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><polyline points=\'9 18 15 12 9 6\'/></svg>" width="13" height="13" alt="" />'
        f'</a>'
    )

    st.html(
        f"""
        <aside class="{side_cls}">
          <div class="app-side-brand">
            <div class="app-side-mark">
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none'
                   stroke='#475569' stroke-width='2.2'
                   stroke-linecap='round' stroke-linejoin='round'>
                <path d='M4 22h16M5 2h14a1 1 0 011 1v18H4V3a1 1 0 011-1zM9 7h10M9 11h10M9 15h7'/>
              </svg>" width="14" height="14" alt="" />
            </div>
            <span class="app-side-brand-t">인사이트<b>보드</b></span>
            {side_collapse_btn}
          </div>

          <div class="app-side-profile">
            <div class="app-side-tag">
              <span class="app-side-tag-dot"></span>
              인사이트 제공 기준 페르소나
            </div>
            <div class="app-side-profile-head">
              <div class="app-side-avatar">{avatar}</div>
              <div>
                <div class="app-side-pname">{name}</div>
                <div class="app-side-prole">{role} · {job}</div>
              </div>
            </div>
            <div class="app-side-interest">
              <span>관심</span>
              {interest_chips}
            </div>
            <div class="app-side-stats">
              <div><b>{match_today}</b><span>오늘 매칭</span></div>
              <div class="app-side-stat-sep"></div>
              <div><b>{opportunities}</b><span>자동화 기회</span></div>
              <div class="app-side-stat-sep"></div>
              <div><b>{pending}</b><span>채택 대기</span></div>
            </div>
          </div>

          <div class="app-side-seclbl">WORKFLOW</div>
          <nav class="app-side-nav">
            {''.join(nav_html)}
          </nav>

          <div class="app-side-foot">
            <span class="{foot_dot_cls}"></span>
            <div>
              <div class="app-side-foot-t">LLM · {backend_safe}</div>
              <div class="app-side-foot-s">{model_safe}</div>
            </div>
          </div>
          {side_rail_open_btn}
        </aside>
        """
    )


def render_app_sola(
    *,
    context_label: str = "",
    context_sub: str = "",
    quick_prompts: list[tuple[str, str]] | None = None,
    last_q: str = "",
    last_a_html: str = "",
    last_time: str = "",
) -> None:
    """`.app-sola` 우측 SOLA 패널 렌더.

    Args:
        context_label: 컨텍스트 핀 카드의 강조 이름.
        context_sub: 컨텍스트 핀 카드의 보조 설명.
        quick_prompts: [(index, prompt_html)] — html 은 신뢰 가능한 마크업이어야 함.
        last_q: 최근 질문 텍스트.
        last_a_html: 최근 답변 HTML (b 태그 등 허용, 호출자 sanitize 책임).
        last_time: 최근 답변 시각 라벨.
    """
    # Phase A: 우측 채팅이 실제 작동하는 st.columns 컬럼(`chat_panel.render_side`)으로
    # 이전됨. 이 고정 HTML 패널(.app-sola)은 입력창·버튼이 모두 disabled 인 목업이라
    # 렌더를 중단한다 — 호출부 호환용 no-op. (본문은 Phase C 에서 함수째 삭제 예정.)
    return None
    quick_prompts = quick_prompts or []
    quick_html_parts = []
    for idx, prompt_html in quick_prompts:
        quick_html_parts.append(
            f"""<button class="app-sola-quick-q" disabled>
              <span class="app-sola-quick-i">{_html.escape(idx)}</span>
              <span>{prompt_html}</span>
            </button>"""
        )
    quick_block_html = ""
    if quick_html_parts:
        quick_block_html = f"""
        <div class="app-sola-quick">
          <div class="app-sola-quick-eye">
            <span>빠른 질문</span>
            <button class="app-sola-quick-refresh" title="다시 추천" disabled>
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='#475569'
                   stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'>
                <path d='M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5M21 12a9 9 0 01-15 6.7L3 16M3 21v-5h5'/>
              </svg>" width="11" height="11" alt="" />
            </button>
          </div>
          <div class="app-sola-quick-list">
            {''.join(quick_html_parts)}
          </div>
        </div>
        """

    ctx_block_html = ""
    if context_label:
        ctx_block_html = f"""
        <div class="app-sola-ctx">
          <div class="app-sola-ctx-eye">컨텍스트 핀</div>
          <div class="app-sola-ctx-card">
            <div class="app-sola-ctx-icon">
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='#475569'
                   stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                <path d='M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z'/>
                <polyline points='14 2 14 8 20 8'/>
              </svg>" width="13" height="13" alt="" />
            </div>
            <div class="app-sola-ctx-body">
              <div class="app-sola-ctx-name">{_html.escape(context_label)}</div>
              <div class="app-sola-ctx-sub">{_html.escape(context_sub)}</div>
            </div>
          </div>
        </div>
        """

    recent_block_html = ""
    if last_a_html:
        recent_block_html = f"""
        <div class="app-sola-recent">
          <div class="app-sola-recent-eye">
            <span>최근 답변</span>
            <span class="app-sola-recent-time">{_html.escape(last_time)}</span>
          </div>
          {f'<div class="app-sola-recent-q">"{_html.escape(last_q)}"</div>' if last_q else ''}
          <div class="app-sola-recent-a">{last_a_html}</div>
        </div>
        """

    collapsed = _sola_collapsed()
    sola_cls = "app-sola app-sola-collapsed" if collapsed else "app-sola"
    sola_toggle_href = _toggle_href("sola")
    sola_collapse_btn = (
        f'<a class="app-sola-hdr-x" href="{sola_toggle_href}" title="접기" target="_self">'
        f'<img src="data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'13\' height=\'13\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'#475569\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><polyline points=\'9 18 15 12 9 6\'/></svg>" width="13" height="13" alt="" />'
        f'</a>'
    )
    sola_rail_html = f"""
      <div class="app-sola-rail">
        <div class="app-sola-rail-mark">
          <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 2L9.5 8.5 3 11l6.5 2.5L12 20l2.5-6.5L21 11l-6.5-2.5z'/></svg>" width="13" height="13" alt="" />
        </div>
        <span class="app-sola-rail-label">SOLA</span>
        <a class="app-sola-rail-open" href="{sola_toggle_href}" title="패널 펴기" target="_self">
          <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='#475569' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'><polyline points='15 18 9 12 15 6'/></svg>" width="13" height="13" alt="" />
        </a>
      </div>
    """

    st.html(
        f"""
        <aside class="{sola_cls}">
          {sola_rail_html}
          <div class="app-sola-hdr">
            <div class="app-sola-hdr-l">
              <div class="app-sola-mark">
                <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='#475569'
                     stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                  <path d='M12 2L9.5 8.5 3 11l6.5 2.5L12 20l2.5-6.5L21 11l-6.5-2.5z'/>
                </svg>" width="14" height="14" alt="" />
              </div>
              <div class="app-sola-hdr-t">
                <div class="app-sola-hdr-name">SOLA<span class="app-sola-pulse-dot"></span></div>
                <div class="app-sola-hdr-meta">컨텍스트 자동 첨부</div>
              </div>
            </div>
            {sola_collapse_btn}
          </div>

          {ctx_block_html}
          {quick_block_html}
          {recent_block_html}

          <div class="app-sola-comp">
            <span class="app-sola-comp-pin">
              <span class="app-sola-comp-pin-i">
                <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='9' height='9' viewBox='0 0 24 24' fill='none' stroke='#475569'
                     stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'>
                  <path d='M12 2v20M2 12h20'/>
                </svg>" width="9" height="9" alt="" />
              </span>
              현재 화면 자동 포함
            </span>
            <div class="app-sola-comp-box">
              <textarea class="app-sola-comp-input" rows="2"
                placeholder="질문을 입력하거나 위 빠른 질문을 클릭하세요..." disabled></textarea>
              <div class="app-sola-comp-foot">
                <div class="app-sola-comp-tools"></div>
                <button class="app-sola-comp-send" disabled>
                  보내기
                  <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='#475569'
                       stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'>
                    <line x1='5' y1='12' x2='19' y2='12'/>
                    <polyline points='12 5 19 12 12 19'/>
                  </svg>" width="11" height="11" alt="" />
                </button>
              </div>
            </div>
            <div class="app-sola-comp-tips">
              현재 페이지 컨텍스트가 자동 첨부됩니다
            </div>
          </div>
        </aside>
        """
    )


def _get_persona() -> Persona:
    """세션에서 페르소나 안전 로드 — sidebar.py 가 먼저 채우지만 보호용."""
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


def refresh_label_now() -> str:
    """헤더 우측 갱신 시각 라벨 — '2026.05.20 · 수 · 06:24 갱신' 형식."""
    now = datetime.now()
    weekday = "월화수목금토일"[now.weekday()]
    return f"{now:%Y.%m.%d} · {weekday} · {now:%H:%M} 갱신"
