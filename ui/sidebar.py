"""사이드바: 업무 흐름형 네비 + 컴팩트 페르소나 카드 + 시스템 푸터."""
from __future__ import annotations

import html as _html
from urllib.parse import unquote

import streamlit as st

from ui.components import render_html, prepare_screen_html

from config import llm_backend, llm_model
from persona import store as persona_store
from persona.schema import Persona
from roadmap.query import load_latest as load_tasks
from sola.client import is_configured as llm_ready


AREAS = (
    "📊 오늘의 보드",
    "🧱 데이터 관리",
    "🔎 인사이트 분석",
    "🤖 SOLA 작업실",
    "📦 산출물 보관함",
)

_AREA_DESCRIPTIONS = {
    "📊 오늘의 보드": "맞춤 인사이트",
    "🧱 데이터 관리": "수집 · 둘러보기 · 작업 정의",
    "🔎 인사이트 분석": "트렌드 · 기회 · 매칭",
    "🤖 SOLA 작업실": "초안 · 대화",
    "📦 산출물 보관함": "북마크 · 채택",
}


def _load_persona_into_state() -> Persona:
    if "persona" not in st.session_state:
        st.session_state["persona"] = persona_store.load()
    return st.session_state["persona"]


def _avatar_text(persona: Persona) -> str:
    if persona.name:
        return persona.name.strip()[0]
    if persona.dept:
        return persona.dept.strip()[0]
    return "?"


def _llm_footer_html(*, ready: bool, backend: str, model: str) -> str:
    """LLM 상태 + 미설정 시 Groq 키 발급 안내 카드.

    헬퍼로 분리해 단위 테스트 가능.
    """
    dot_cls = "ok" if ready else "warn"
    backend_safe = _html.escape(backend)
    model_safe = _html.escape(model or "(미설정)")
    if ready:
        return f"""
        <div class="sidebar-footer">
          <span class="sidebar-dot {dot_cls}"></span>
          <span class="sidebar-footer-text">
            <b>LLM · {backend_safe}</b><br>
            <span class="muted">{model_safe}</span>
          </span>
        </div>
        """
    return f"""
    <div class="sidebar-footer sidebar-footer-empty">
      <div class="sidebar-footer-row">
        <span class="sidebar-dot {dot_cls}"></span>
        <span class="sidebar-footer-text">
          <b>LLM · {backend_safe}</b><br>
          <span class="muted">키 미설정</span>
        </span>
      </div>
      <div class="sidebar-llm-empty-hint">
        요약·제안서·채팅 등 AI 기능을 쓰려면 키가 필요합니다.<br>
        <a href="https://console.groq.com/keys" target="_blank" rel="noopener">
          🔑 Groq 키 발급 (무료)
        </a>
        · 발급 후 <code>.env</code>의<br><code>LLM_API_KEY=gsk_…</code> 한 줄만 채우면 OK
      </div>
    </div>
    """


def _persona_card_html(persona: Persona) -> str:
    """좌측 사이드바 프로필 카드.

    카드 전체가 `?persona_editor=1` 링크라 아바타·이름·역할·안내 문구 어디를
    눌러도 프로필 설정 화면이 열린다. 미설정 시엔 👤 이모지 + 안내 + CTA 로
    설정을 유도한다.
    """
    if persona.is_set():
        avatar = _html.escape(_avatar_text(persona))
        name = _html.escape(persona.name or "사용자")
        role_parts = [p for p in (persona.dept, persona.job) if p]
        role = _html.escape(" · ".join(role_parts)) if role_parts else "부서·직무 미설정"
        team = _html.escape(persona.team or "—")
        interests = _html.escape(
            " · ".join(persona.interest_lv3[:3]) if persona.interest_lv3 else "—"
        )
        return f"""
        <a class="persona-profile-link" href="?persona_editor=1" target="_self"
           aria-label="프로필 편집 열기">
          <div class="persona-profile-card">
            <div class="persona-profile-row">
              <div class="persona-profile-head">{avatar}</div>
              <div class="persona-profile-id">
                <div class="persona-profile-name">{name}</div>
                <div class="persona-profile-role">{role}</div>
              </div>
              <div class="persona-profile-edit" aria-hidden="true">✎</div>
            </div>
            <div class="persona-profile-details">
              <div><span>팀</span><b>{team}</b></div>
              <div><span>관심</span><b>{interests}</b></div>
            </div>
          </div>
        </a>
        """
    return """
    <a class="persona-profile-link" href="?persona_editor=1" target="_self"
       aria-label="프로필 설정 시작">
      <div class="persona-profile-card persona-profile-card-empty">
        <div class="persona-profile-row">
          <div class="persona-profile-head persona-profile-head-empty" aria-hidden="true">👤</div>
          <div class="persona-profile-id">
            <div class="persona-profile-name">프로필 미설정</div>
            <div class="persona-profile-role">눌러서 설정을 시작하세요</div>
          </div>
        </div>
        <div class="persona-profile-empty-hint">
          부서·직무·관심 공정을 설정하면 오늘의 보드와 SOLA 가 나에게 맞춰집니다.
        </div>
        <div class="persona-profile-cta">＋ 프로필 설정하기</div>
      </div>
    </a>
    """


def _consume_persona_editor_query() -> None:
    """Open the persona editor when the sidebar avatar link is clicked."""
    if st.query_params.get("persona_editor") != "1":
        return
    st.session_state["show_persona_editor"] = True
    del st.query_params["persona_editor"]


def _consume_area_query() -> None:
    """Open a sidebar area when the Apple-style nav link is clicked."""
    raw = st.query_params.get("app_area")
    if not raw:
        return
    area = unquote(raw)
    if area in AREAS:
        st.session_state["app_area"] = area
        st.session_state["show_persona_editor"] = False
    del st.query_params["app_area"]


def _nav_label(idx: int, area: str, desc: str) -> str:
    """5-nav `st.button` 라벨(markdown) — `**제목** *설명*`.

    `**…**`→`<strong>`(제목), `*…*`→`<em>`(설명) 두 요소로 분해돼 `sidebar.css`
    가 각각 제목/설명으로 스타일한다(설명은 `display:block` 으로 둘째 줄·ellipsis,
    인덱스 01·02… 는 CSS counter `::before` 로 생성). 핵심 markdown 만 써서(색·코드
    directive 의존 X) 버튼 라벨 렌더에 안전하다.
    """
    base = f"**{area}**"
    return f"{base} *{desc}*" if desc else base


def _render_sidebar_nav(current_area: str) -> None:
    """업무 흐름 5-nav — `st.button` 위젯(구 `<a href=?app_area=>` 앵커 대체).

    앵커는 클릭 시 **브라우저 문서 전체 reload**(흰 깜빡임)였다. 버튼은 클릭 시
    **소켓 rerun**(부분 갱신·문서 reload 없음)이라 화면 전환에서 흰 깜빡임이 사라진다.
    look 은 `sidebar.css` 의 `.st-key-sidebar_nav` 스코프가 기존 `.sidebar-nav-item`
    룩(인덱스+제목+설명, 활성=accent)으로 복제한다. 활성 항목은 `type="primary"` →
    CSS 가 accent 배경/테두리. `on_click` 미사용 — `if st.button(): 세팅 → st.rerun()`
    (CLAUDE.md #3). 컨텍스트 딥링크(`?app_area=` from 보드/히트맵/알림)는 그대로
    `_consume_area_query` 가 처리하므로 여기선 사이드바 메뉴 이동만 위젯화한다.
    """
    editing = bool(st.session_state.get("show_persona_editor"))
    with st.container(key="sidebar_nav"):
        for idx, area in enumerate(AREAS, start=1):
            active = (area == current_area) and not editing
            clicked = st.button(
                _nav_label(idx, area, _AREA_DESCRIPTIONS.get(area, "")),
                key=f"_nav_btn_{idx}",
                use_container_width=True,
                type="primary" if active else "secondary",
            )
            # 이미 활성(같은 area·편집 아님)이면 무반응 → 불필요한 rerun 방지.
            if clicked and not active:
                st.session_state["app_area"] = area
                st.session_state["show_persona_editor"] = False
                st.rerun()


def _side_stats_html(stats: dict) -> str:
    """좌측 사이드바 통계 3칸 (오늘 매칭 / 자동화 기회 / 채택 대기).

    이전 고정 HTML `.app-side` 의 통계 블록을 네이티브 사이드바로 이전 (Phase A).
    값은 `board_v2._archive_stats()` (60초 캐시 실데이터) 위임 — 보드 KPI 와 일관.
    """
    cells = (
        ("오늘 매칭", int(stats.get("match_today", 0))),
        ("자동화 기회", int(stats.get("opportunities", 0))),
        ("채택 대기", int(stats.get("pending_adopt", 0))),
    )
    inner = "".join(
        f'<div style="flex:1; text-align:center;">'
        f'<div style="font-size:21px; font-weight:800; color:var(--text-primary); line-height:1.1;">{v}</div>'
        f'<div style="font-size:11px; color:var(--text-muted); margin-top:2px;">{_html.escape(lbl)}</div>'
        f'</div>'
        for lbl, v in cells
    )
    return (
        '<div style="display:flex; gap:6px; margin:10px 0 4px; padding:11px 10px; '
        'background:var(--surface-soft); border:1px solid var(--surface-divider); border-radius:10px;">'
        f'{inner}</div>'
    )


def _load_side_stats() -> dict:
    """board 의 실데이터 통계 위임 — 실패 시 0 폴백 (사이드바가 죽지 않게)."""
    try:
        from ui import board_v2
        return board_v2._archive_stats()
    except Exception:
        return {"match_today": 0, "opportunities": 0, "pending_adopt": 0}


def _render_persona_block(persona: Persona, _tasks_df) -> None:
    """Render a clickable profile summary; editing happens on the main page."""
    _consume_persona_editor_query()
    render_html(_persona_card_html(persona), unsafe_allow_html=True)

    msg = st.session_state.pop("persona_page_msg", None)
    if msg:
        kind, text = msg
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](text)


def render() -> str:
    """사이드바 렌더링 후 현재 선택된 영역(string) 반환."""
    tasks_df = load_tasks()
    persona = _load_persona_into_state()

    # 최상단 메인 로고 — 그라데이션 마크(상승 막대 + 인사이트 스파크) + 워드마크 + 태그라인.
    # 인라인 <svg> 는 st.html 이 sanitize 하므로 prepare_screen_html 로 data-URI <img> 변환.
    render_html(prepare_screen_html(
        """
        <div class="sidebar-brand sidebar-brand-top">
          <div class="sidebar-brand-logo">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#FFFFFF">
              <rect x="3" y="13.4" width="3.9" height="7.1" rx="1.5"/>
              <rect x="10.05" y="9.7" width="3.9" height="10.8" rx="1.5"/>
              <rect x="17.1" y="7.2" width="3.9" height="13.3" rx="1.5"/>
              <path d="M18.95 1.4l.74 1.78 1.78.74-1.78.74-.74 1.78-.74-1.78-1.78-.74 1.78-.74z"/>
            </svg>
          </div>
          <div class="sidebar-brand-copy">
            <div class="sidebar-brand-text">Insight<span class="sidebar-brand-accent">Board</span></div>
            <div class="sidebar-brand-tag">조선소 작업 인사이트</div>
          </div>
        </div>
        """
    ))

    # 브랜드 아래 사용자 프로필
    _render_persona_block(persona, tasks_df)

    # 실데이터 통계 3칸 (보드 KPI 와 동일 소스)
    render_html(_side_stats_html(_load_side_stats()), unsafe_allow_html=True)

    # 업무 흐름 네비
    _consume_area_query()
    if st.session_state.get("app_area") not in AREAS:
        st.session_state["app_area"] = AREAS[0]
    area = st.session_state["app_area"]
    render_html('<div class="sidebar-section sidebar-section-nav">Workflow</div>', unsafe_allow_html=True)
    _render_sidebar_nav(area)
    render_html(
        '<div class="sidebar-flow-hint apple">'
        '데이터 준비 → 분석 → SOLA 산출물 → 보관'
        '</div>',
        unsafe_allow_html=True,
    )

    # 시스템 푸터 (점선 인디케이터 + 미설정 시 안내 카드)
    render_html(
        _llm_footer_html(
            ready=llm_ready(),
            backend=llm_backend(),
            model=llm_model() or "",
        ),
        unsafe_allow_html=True,
    )

    return area
