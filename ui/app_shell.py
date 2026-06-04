"""v2 디자인 시스템의 글로벌 크롬 — 모든 화면 공유.

글로벌 크롬:
  - render_topbar()          : 풀폭 fixed 헤더 (60px) — WORKFLOW / 페이지명 + 검색 + 알림/아바타
  - render_command_palette() : ⌘K 빠른 이동 모달
  - get_persona()            : 세션 페르소나 단일 진입점

좌측 nav 는 네이티브 `st.sidebar`(`ui/sidebar.py`), 우측 LLM 채팅은
`chat_panel.render_side`(st.columns 컬럼)가 담당. 구 고정 HTML 패널
(`render_app_side`/`render_app_sola`)과 패널 접기 토글은 Phase 3 에서 삭제됨.
"""
from __future__ import annotations

import html as _html
from datetime import datetime
from urllib.parse import quote

import streamlit as st

from config import llm_backend
from persona.schema import Persona
from sola.client import is_configured as llm_ready
from ui import components as _components


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
            background: var(--surface-card, #fff); border: 1px solid var(--surface-divider, #E5E7EB);
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

    st.html(_components.prepare_screen_html(
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
    ))


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
