"""SOLA 작업실 — v2 디자인 적용.

특수성: SOLA workshop 화면은 우측 .app-sola 패널을 그리지 않는다. 대신 화면
자체가 3-열 `.ws-shell` (쓰레드 / 채팅 / 컨텍스트) 로 구성되어 SOLA 경험을
풀스크린으로 제공.

CSS 규칙은 `body:has(.ws-shell)` 분기로 block-container 우측 패딩을 축소
(scale.css 에 추가).
"""
from __future__ import annotations

import html as _html

import streamlit as st

from config import ASSETS_DIR
from persona.schema import Persona
from store import bookmarks as bookmarks_store
from ui import app_shell
from ui.styles import inject_screen_css


_SOLA_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "sola_main.html"


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


def _archive_stats() -> dict[str, int]:
    summary = bookmarks_store.summary_counts()
    pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
    return {"match_today": 32, "opportunities": 4, "pending_adopt": pending}


def render() -> None:
    """SOLA 작업실 v2 — topbar + app-side + 3-열 ws-shell (app-sola 없음)."""
    inject_screen_css("sola")

    persona = _load_persona()
    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="SOLA 작업실",
        eyebrow_current="SOLA 작업실",
        refresh_label=refresh,
        fresh_kind="accent",
    )
    app_shell.render_app_side(
        active_area="🤖 SOLA 작업실",
        persona=persona,
        stats=stats,
    )
    app_shell.render_setup_banner_if_needed()
    _render_brief_handoff_banner_if_needed()
    _render_main(persona)
    # 의도적으로 app-sola 미렌더 — ws-ctx 가 그 역할 대체


_HANDOFF_LABELS: dict[str, tuple[str, str]] = {
    "brief": ("📊 보드 브리핑에서 인계됨", "3건의 뉴스를 컨텍스트로 사용"),
    "opp": ("🎯 자동화 기회 카드에서 인계됨", "이 부서·공정으로 제안서 초안 시작"),
    "matrix": ("🧭 기회 매트릭스 1위에서 인계됨", "이 부서·공정으로 제안서 초안 시작"),
    "ia_map": ("🔎 인사이트 공정 매핑 카드에서 인계됨", "이 공정 상세 — 매칭 뉴스·작업 컨텍스트"),
}


def _render_brief_handoff_banner_if_needed() -> None:
    """`?from=...` 에 따라 인계 컨텍스트 배너 렌더 (LLM 입력 wire 는 후속 PR).

    지원 from: brief / opp / matrix / ia_map.
      - brief : session_state["_board_brief_items"] 3건 제목 노출
      - opp / matrix / ia_map : URL query 의 dept · lv3 노출
    """
    from_kind = st.query_params.get("from")
    if from_kind not in _HANDOFF_LABELS:
        return

    title, sub = _HANDOFF_LABELS[from_kind]
    body_html = ""

    if from_kind == "brief":
        items = st.session_state.get("_board_brief_items") or []
        if not items:
            return
        body_html = "<ol>" + "".join(
            f'<li><span class="ws-brief-num">{i + 1}</span>{_html.escape(it.get("title", "")[:80])}</li>'
            for i, it in enumerate(items[:3])
        ) + "</ol>"
    else:
        dept = st.query_params.get("dept", "")
        lv3 = st.query_params.get("lv3", "")
        if not dept and not lv3:
            return
        target = " · ".join(p for p in (dept, lv3) if p) or "—"
        body_html = (
            f'<div class="ws-brief-target">'
            f'<span class="ws-brief-target-eye">대상</span>'
            f'<span class="ws-brief-target-v">{_html.escape(target)}</span>'
            f'</div>'
        )

    st.html(
        f"""
        <style>
          body:has(.db-topbar) .ws-brief-handoff {{
            position: sticky; top: 76px; z-index: 8;
            margin: 0 24px 14px; padding: 12px 16px;
            background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 10px;
            font-size: 13px; color: #1E3A8A;
          }}
          body:has(.db-topbar) .ws-brief-handoff-h {{
            font-weight: 800; margin-bottom: 6px;
            display: flex; align-items: center; gap: 6px;
          }}
          body:has(.db-topbar) .ws-brief-handoff-sub {{
            font-weight: 500; color: #1E40AF; margin-left: 6px;
          }}
          body:has(.db-topbar) .ws-brief-handoff ol {{ margin: 0; padding-left: 0; list-style: none; }}
          body:has(.db-topbar) .ws-brief-handoff li {{
            padding: 3px 0; display: flex; gap: 8px; align-items: baseline;
          }}
          body:has(.db-topbar) .ws-brief-num {{
            display: inline-flex; align-items: center; justify-content: center;
            min-width: 18px; height: 18px; padding: 0 5px; border-radius: 4px;
            background: #2563EB; color: #fff; font-size: 11px; font-weight: 800;
          }}
          body:has(.db-topbar) .ws-brief-target {{
            display: flex; gap: 8px; align-items: center;
          }}
          body:has(.db-topbar) .ws-brief-target-eye {{
            font-size: 11px; color: #1E40AF; opacity: 0.7; letter-spacing: 0.04em;
          }}
          body:has(.db-topbar) .ws-brief-target-v {{ font-weight: 700; }}
        </style>
        <div class="ws-brief-handoff">
          <div class="ws-brief-handoff-h">
            {title}<span class="ws-brief-handoff-sub">— {sub}</span>
          </div>
          {body_html}
        </div>
        """
    )


def _render_main(persona: Persona) -> None:
    """sola_main.html 템플릿 로드 + persona snapshot 치환."""
    name = persona.name or "사용자"
    dept = persona.dept or ""
    job = persona.job or ""
    line_parts = [p for p in (name, job, dept) if p]
    persona_line = " · ".join(line_parts) if line_parts else "사용자"

    interests = persona.interest_lv3 or persona.interest_tasks or []
    interests_label = ", ".join(interests[:3]) if interests else "미설정"

    template = _SOLA_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{PERSONA_LINE}}", _html.escape(persona_line))
        .replace("{{PERSONA_INTERESTS}}", _html.escape(interests_label))
        .replace("{{PERSONA_TEAM_SIZE}}", "5–15명")
        .replace("{{KEYWORDS_COUNT}}", "8개")
    )
    st.html(html_out)
