"""Persona profile editor page.

Opened from the large avatar/profile card in the sidebar so persona fields do not
crowd the global navigation.

v2: 글로벌 셸(topbar + app-side)로 감싸 다른 화면과 시각 통일. 폼 본문은 실제
Streamlit 위젯(selectbox/multiselect/button)을 그대로 사용 — HTML 치환 불가
(편집 입력이 필요). `body:has(.db-topbar)` 패딩 안에 위젯이 정렬된다.

구성 (페르소나 개편):
  ① 기본 정보 — 이름·부서·팀·직무
  ② 관심사 — 관심 공정(lv3) + 자유 입력 관심 키워드(수집에 합류)
  ③ SOLA 분석 — derive 결과(관심사 키워드 + 연관 공정/작업) 카드 + 다시 분석
  ④ 표시 설정 — 테마·글자 크기 (접힌 expander, 프로필과 분리)
"""
from __future__ import annotations

import html as _html

import streamlit as st

from persona import derive as persona_derive
from persona import store as persona_store
from persona.schema import Persona, parse_keywords_input
from roadmap.query import load_latest as load_tasks
from ui import app_shell
from ui.components import inject_focus_nav
from ui.styles import inject_screen_css


def chat_context_block(persona: Persona) -> str:
    """페르소나 편집 화면이 보여주는 데이터를 LLM 컨텍스트로 packaging.

    채워진 / 비어있는 필드, 관심 공정/작업 목록을 LLM 이 인식하도록.
    사용자가 "내 부서에 맞는 관심 공정 추천해줘" 같은 질문을 하면 답 가능.
    """
    parts: list[str] = ["--- 현재 화면: 페르소나 / 프로필 편집 ---"]
    filled, empty = [], []
    for key, val in (
        ("이름", persona.name),
        ("팀", persona.team),
        ("부서", persona.dept),
        ("직무", persona.job),
    ):
        (filled if val else empty).append(f"{key}={val}" if val else key)
    parts.append("채워진 필드: " + (", ".join(filled) if filled else "(없음)"))
    parts.append("비어있는 필드: " + (", ".join(empty) if empty else "(없음)"))
    if persona.interest_lv3:
        parts.append("관심 공정 (Lv3, 최대 6개): " + ", ".join(persona.interest_lv3[:6]))
    else:
        parts.append("관심 공정: 미설정")
    if persona.interest_tasks:
        parts.append("관심 작업: " + ", ".join(persona.interest_tasks[:6]))
    if persona.interest_keywords:
        parts.append("관심 키워드: " + ", ".join(persona.interest_keywords[:10]))
    if persona.derived_interests:
        parts.append("SOLA 분석 관심사: " + ", ".join(persona.derived_interests[:10]))
    if persona.matched_processes:
        tops = [str(m.get("process", "")) for m in persona.matched_processes[:3]]
        parts.append("SOLA 연관 공정: " + ", ".join(t for t in tops if t))
    return "\n".join(parts)


def _options(df, col: str) -> list[str]:
    if df.empty or col not in df.columns:
        return [""]
    return [""] + sorted(df[col].dropna().astype(str).unique().tolist())


def _has_roadmap_options(opts: list[str]) -> bool:
    """`_options()` 결과에서 실제 선택지가 있는지 (빈 값 외에 1개라도 있는지)."""
    return len(opts) > 1


def _lv3_options(df) -> list[str]:
    if df.empty or "lv3" not in df.columns:
        return []
    return sorted(df["lv3"].dropna().astype(str).unique().tolist())


def _keywords_from(raw) -> list[str]:
    """키워드 입력값 정규화 — multiselect 칩(list) 또는 구버전 문자열 둘 다 수용."""
    if isinstance(raw, str):
        return parse_keywords_input(raw)
    return parse_keywords_input(", ".join(str(k) for k in (raw or [])))


def _save_from_state(persona: Persona) -> None:
    new = Persona(
        name=st.session_state.get("px_name", "").strip(),
        team=st.session_state.get("px_team", "").strip(),
        dept=st.session_state.get("px_dept", "").strip(),
        job=st.session_state.get("px_job", "").strip(),
        interest_lv3=list(st.session_state.get("px_lv3", []) or []),
        interest_tasks=persona.interest_tasks,
        interest_keywords=_keywords_from(st.session_state.get("px_keywords", [])),
        # 숨김 키워드·기존 분석 결과는 편집 폼에 없으므로 보존.
        muted_keywords=list(persona.muted_keywords or []),
        derived_interests=list(persona.derived_interests or []),
        matched_processes=list(persona.matched_processes or []),
        derived_at=persona.derived_at,
        derived_source=persona.derived_source,
    )
    persona_store.save(new)
    # 프로필이 바뀌면 SOLA 분석도 갱신 (캐시 히트 시 LLM 재호출 없음, 실패 무해).
    new = persona_derive.derive_and_store(new)
    st.session_state["persona"] = new
    st.session_state["persona_page_msg"] = ("ok", f"페르소나 저장됨: {new.label()}")


def _handle_pending(persona: Persona) -> None:
    if st.session_state.pop("_do_persona_page_save", False):
        _save_from_state(persona)
        st.session_state["show_persona_editor"] = False
        st.rerun()

    if st.session_state.pop("_do_persona_page_reset", False):
        persona_store.reset()
        st.session_state["persona"] = Persona()
        st.session_state["persona_page_msg"] = ("warn", "페르소나 초기화 완료")
        st.rerun()

    if st.session_state.pop("_do_persona_page_back", False):
        st.session_state["show_persona_editor"] = False
        st.rerun()

    if st.session_state.pop("_do_persona_page_derive", False):
        updated = persona_derive.derive_and_store(persona, force=True)
        st.session_state["persona"] = updated
        n_kw = len(updated.derived_interests)
        n_proc = len(updated.matched_processes)
        if n_kw:
            label = "SOLA" if updated.derived_source == "llm" else "규칙 폴백"
            st.session_state["persona_page_msg"] = (
                "ok", f"분석 완료({label}): 관심사 {n_kw}개 · 연관 공정 {n_proc}개"
            )
        else:
            st.session_state["persona_page_msg"] = (
                "warn", "분석할 프로필 입력이 없습니다. 부서·직무·관심사를 먼저 채워주세요."
            )
        st.rerun()


_THEME_LABELS = [("light", "라이트"), ("dark", "다크"), ("ocean", "오션"), ("sunset", "선셋")]
_FONT_LABELS = [("small", "작게"), ("medium", "보통"), ("large", "크게")]


def _section_label(text: str) -> None:
    st.html(
        '<div style="font-size:12px; font-weight:800; letter-spacing:0.08em; '
        f'text-transform:uppercase; color:var(--text-muted,#94A3B8); margin:16px 0 6px;">{_html.escape(text)}</div>'
    )


def _render_display_settings() -> None:
    """🎨 표시 설정 — 테마 + 글자 크기. 프로필과 무관한 시스템 설정이라 접힌
    expander 로 분리(변경 즉시 저장·적용, on_change 콜백 대신 diff 감지)."""
    from store import ui_prefs

    prefs = ui_prefs.load()
    with st.expander("🎨 표시 설정 — 테마 · 글자 크기", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            theme_labels = [lbl for _, lbl in _THEME_LABELS]
            ti = next((i for i, (k, _) in enumerate(_THEME_LABELS) if k == prefs["theme"]), 0)
            sel_theme = st.radio("테마", theme_labels, index=ti, key="ux_theme",
                                 horizontal=True, help="라이트 · 다크 · 강조색(오션/선셋)")
        with c2:
            font_labels = [lbl for _, lbl in _FONT_LABELS]
            fi = next((i for i, (k, _) in enumerate(_FONT_LABELS) if k == prefs["font"]), 1)
            sel_font = st.radio("글자 크기", font_labels, index=fi, key="ux_font", horizontal=True)
        new_theme = next(k for k, lbl in _THEME_LABELS if lbl == sel_theme)
        new_font = next(k for k, lbl in _FONT_LABELS if lbl == sel_font)
        if new_theme != prefs["theme"] or new_font != prefs["font"]:
            ui_prefs.save(theme=new_theme, font=new_font)
            st.rerun()
        st.caption("변경하면 즉시 적용되고 다음 접속에도 유지됩니다.")


def _derived_card_html(persona: Persona) -> str:
    """③ SOLA 분석 카드 본문 HTML — derived 키워드 칩 + 연관 공정/작업 리스트.

    모든 표시 문자열은 LLM/저장 데이터이므로 `html.escape` (CLAUDE.md #5).
    """
    src_label = {
        "llm": "🤖 SOLA(LLM) 분석",
        "cache": "🤖 SOLA(LLM) 분석 · 캐시",
        "fallback": "⚙ 규칙 기반 분석 (LLM 미설정 폴백)",
    }.get(persona.derived_source, "")
    when = _html.escape((persona.derived_at or "").replace("T", " ").replace("+00:00", " UTC"))
    head_meta = (
        f'<span style="font-size:11.5px; color:var(--text-muted,#94A3B8);">'
        f'{_html.escape(src_label)}{" · " + when if when else ""}</span>'
    )

    chips = "".join(
        f'<span style="display:inline-flex; align-items:center; padding:3px 10px; '
        f'border-radius:999px; background:rgba(37,99,235,0.08); color:#2563EB; '
        f'font-size:12.5px; font-weight:700; margin:0 6px 6px 0;">{_html.escape(kw)}</span>'
        for kw in persona.derived_interests[:10]
    )

    proc_rows: list[str] = []
    for m in persona.matched_processes[:8]:
        proc = _html.escape(str(m.get("process", "")))
        tasks = [
            _html.escape(str(t)) for t in (m.get("tasks") or [])[:5] if str(t).strip()
        ]
        tasks_html = " · ".join(tasks) if tasks else "(작업 미상)"
        proc_rows.append(
            f'<div style="display:flex; gap:10px; padding:7px 0; '
            f'border-top:1px solid var(--surface-divider,#E2E8F0); font-size:13px;">'
            f'<b style="min-width:120px; color:var(--text-primary,#0F172A);">{proc}</b>'
            f'<span style="color:var(--text-secondary,#475569); line-height:1.5;">{tasks_html}</span>'
            f'</div>'
        )
    proc_html = (
        "".join(proc_rows)
        if proc_rows
        else '<div style="font-size:12.5px; color:var(--text-muted,#94A3B8); padding:6px 0;">'
             '작업 정의 데이터와 매칭된 공정이 아직 없습니다 — 작업 정의를 업로드하면 추천이 생깁니다.</div>'
    )

    return (
        '<div style="margin:2px 0 4px;">'
        f'<div style="margin-bottom:8px;">{head_meta}</div>'
        f'<div style="margin-bottom:4px;">{chips}</div>'
        f'<div style="font-size:11.5px; font-weight:800; color:var(--text-muted,#94A3B8); '
        f'margin:10px 0 2px;">연관 공정 · 추천 작업</div>'
        f'{proc_html}'
        '</div>'
    )


def _render_derived_section(persona: Persona) -> None:
    """③ 'SOLA가 분석한 내 관심 공정/작업' 카드 + 다시 분석 버튼."""
    _section_label("🤖 SOLA가 분석한 내 관심 공정/작업")
    with st.container(border=True):
        if persona.derived_interests:
            st.html(_derived_card_html(persona))
        else:
            st.html(
                '<div style="font-size:13px; color:var(--text-secondary,#475569); '
                'line-height:1.55; padding:2px 0 6px;">'
                '아직 분석 결과가 없습니다. 프로필을 저장하거나 아래 <b>지금 분석</b>을 누르면 '
                'SOLA 가 부서·직무·관심사에서 관심 키워드를 추출하고 작업 정의와 매칭해 '
                '연관 공정·작업을 추천합니다. (LLM 미설정 시 입력 키워드 기반 규칙 분석)'
                '</div>'
            )
        c1, _sp = st.columns([1, 2])
        with c1:
            label = "🔄 다시 분석" if persona.derived_interests else "✨ 지금 분석"
            if st.button(label, key="persona_page_derive_btn", use_container_width=True):
                st.session_state["_do_persona_page_derive"] = True
                st.rerun()


def render() -> None:
    """Render the main-content persona editor page (v2 셸 적용)."""
    persona: Persona = st.session_state.get("persona") or persona_store.load()
    tasks = load_tasks()

    # ── v2 글로벌 셸 — 다른 화면과 동일한 topbar + 좌측 네비 ──
    inject_screen_css("board")  # 공통 토큰만 필요 (.db-* 미사용이나 안전)
    app_shell.render_topbar(
        page_title="페르소나 설정",
        eyebrow_current="페르소나 설정",
        refresh_label=app_shell.refresh_label_now(),
        fresh_kind="",
    )
    app_shell.render_setup_banner_if_needed()

    # v2 인트로 (구 page_header 의 .app-header V1 마크업 제거 — topbar 가 제목 담당)
    st.html(
        '<div style="font-size:14px; color:#475569; line-height:1.55; '
        'margin:2px 0 14px; max-width:760px;">'
        '부서·직무·관심 공정·키워드를 설정하면 뉴스 수집과 오늘의 보드, SOLA 컨텍스트가 개인화됩니다.'
        '</div>'
    )

    msg = st.session_state.pop("persona_page_msg", None)
    if msg:
        kind, text = msg
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](text)

    _handle_pending(persona)

    dept_opts = _options(tasks, "dept")
    team_opts = _options(tasks, "team")
    lv3_opts = _lv3_options(tasks)
    no_roadmap = (
        not _has_roadmap_options(dept_opts)
        and not _has_roadmap_options(team_opts)
        and not lv3_opts
    )
    if no_roadmap:
        st.info(
            "🗂 작업 정의 데이터가 아직 업로드되지 않아 부서·팀·관심 공정 추천 목록이 비어있습니다. "
            "일단 자유 입력으로 설정해도 OK — 작업 정의 데이터를 올린 뒤 다시 들어오면 드롭다운으로 바뀝니다."
        )

    # ── ① 기본 정보 ──────────────────────────────────────────
    _section_label("기본 정보")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("이름", value=persona.name, key="px_name", placeholder="예: 홍길동")
            if _has_roadmap_options(dept_opts):
                st.selectbox(
                    "부서",
                    dept_opts,
                    index=dept_opts.index(persona.dept) if persona.dept in dept_opts else 0,
                    key="px_dept",
                )
            else:
                st.text_input(
                    "부서",
                    value=persona.dept,
                    key="px_dept",
                    placeholder="예: 생산기술팀, 자동화기술팀",
                    help="작업 정의 데이터를 업로드하면 이 자리에 부서 추천 목록이 나타납니다.",
                )
        with c2:
            if _has_roadmap_options(team_opts):
                st.selectbox(
                    "팀",
                    team_opts,
                    index=team_opts.index(persona.team) if persona.team in team_opts else 0,
                    key="px_team",
                )
            else:
                st.text_input(
                    "팀",
                    value=persona.team,
                    key="px_team",
                    placeholder="예: 자동화 1팀",
                    help="작업 정의 데이터를 업로드하면 이 자리에 팀 추천 목록이 나타납니다.",
                )
            st.text_input(
                "직무",
                value=persona.job,
                key="px_job",
                placeholder="예: 용접 담당, 자동화 엔지니어, 검사관",
            )

    # ── ② 관심사 — 공정 + 자유 키워드 ────────────────────────
    _section_label("관심사")
    with st.container(border=True):
        if lv3_opts:
            st.multiselect(
                "관심 공정",
                options=lv3_opts,
                default=[v for v in persona.interest_lv3 if v in lv3_opts],
                key="px_lv3",
                help="관심 공정을 선택하면 오늘의 보드와 인사이트 분석이 그 공정 중심으로 정렬됩니다. (작업 정의의 공정 항목 기준)",
            )
        else:
            st.caption(
                "관심 공정 선택은 작업 정의 데이터 업로드 후 활성화됩니다. "
                "현재 저장된 관심 공정: " + (" · ".join(persona.interest_lv3) if persona.interest_lv3 else "없음")
            )
            # 입력 누락 시에도 _save_from_state 에서 빈 리스트가 들어가지 않도록 기존 값 유지.
            st.session_state["px_lv3"] = list(persona.interest_lv3)

        # 키워드 — Enter 로 하나씩 칩(버블) 등록 (온보딩 4단계와 동일 UX).
        st.multiselect(
            "관심 키워드 (입력 후 Enter로 하나씩 등록)",
            options=list(persona.interest_keywords),
            default=list(persona.interest_keywords),
            key="px_keywords",
            accept_new_options=True,
            placeholder="예: 용접 로봇 — 입력 후 Enter",
            help="등록한 키워드는 뉴스 수집 검색어와 보드 키워드 관리에 바로 합류합니다.",
        )

    # ── ③ SOLA 분석 카드 ─────────────────────────────────────
    _render_derived_section(persona)

    # ── 액션 버튼 ────────────────────────────────────────────
    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        if st.button("저장", type="primary", key="persona_page_save_btn", use_container_width=True):
            st.session_state["_do_persona_page_save"] = True
            st.rerun()
    with b2:
        if st.button("초기화", key="persona_page_reset_btn", use_container_width=True):
            st.session_state["_do_persona_page_reset"] = True
            st.rerun()
    with b3:
        if st.button("돌아가기", key="persona_page_back_btn", use_container_width=True):
            st.session_state["_do_persona_page_back"] = True
            st.rerun()

    # ── ④ 표시 설정 (프로필과 분리 — 접힌 expander) ───────────
    _section_label("시스템")
    _render_display_settings()

    # 키보드 UX — 진입 시 이름 입력 자동 포커스 + Enter→다음 입력 이동.
    # scope 를 `px_*` 위젯 컨테이너(`st-key-px_*` 클래스)로 한정해 우측 채팅
    # 입력 등 폼 밖 Enter 동작은 건드리지 않는다.
    inject_focus_nav(
        '[class*="st-key-px_"]',
        nonce="persona-page",
    )
