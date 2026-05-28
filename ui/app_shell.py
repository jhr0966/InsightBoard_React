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
            <div class="db-hdr-search">
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='15' height='15' viewBox='0 0 24 24' fill='none' stroke='#475569'
                   stroke-width='2' stroke-linecap='round' stroke-linejoin='round'
                   style='color:var(--text-muted);'>
                <circle cx='11' cy='11' r='8'/><path d='M21 21l-4.35-4.35'/>
              </svg>" width="15" height="15" alt="" />
              <input placeholder="뉴스 · 작업 · 키워드 검색" disabled>
            </div>
          </div>

          <div class="db-topbar-r">
            <button class="db-hdr-btn" title="알림" disabled>
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='#475569'
                   stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                <path d='M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0'/>
              </svg>" width="16" height="16" alt="" />
              <span class="db-hdr-dot"></span>
            </button>
            <button class="db-hdr-btn" title="설정" disabled>
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='#475569'
                   stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                <circle cx='12' cy='12' r='3'/>
                <path d='M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 008 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.6 15 1.65 1.65 0 003.09 14H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 008 4.6 1.65 1.65 0 009 3.09V3a2 2 0 014 0v.09A1.65 1.65 0 0014 4.6a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9c.16.5.66.91 1.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z'/>
              </svg>" width="16" height="16" alt="" />
            </button>
            <div class="db-topbar-divider"></div>
            <button class="db-topbar-avatar" title="프로필" disabled>{_avatar_letter(_get_persona())}</button>
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

    st.html(
        f"""
        <aside class="app-side">
          <div class="app-side-brand">
            <div class="app-side-mark">
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none'
                   stroke='#475569' stroke-width='2.2'
                   stroke-linecap='round' stroke-linejoin='round'>
                <path d='M4 22h16M5 2h14a1 1 0 011 1v18H4V3a1 1 0 011-1zM9 7h10M9 11h10M9 15h7'/>
              </svg>" width="14" height="14" alt="" />
            </div>
            <span class="app-side-brand-t">인사이트<b>보드</b></span>
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

    st.html(
        f"""
        <aside class="app-sola">
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
            <button class="app-sola-hdr-x" title="접기" disabled>
              <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='#475569'
                   stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                <polyline points='9 18 15 12 9 6'/>
              </svg>" width="13" height="13" alt="" />
            </button>
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
