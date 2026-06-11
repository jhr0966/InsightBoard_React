"""페르소나 온보딩 마법사 — 미설정 사용자에게 단계별 페르소나 설정 제안.

진입 흐름 (app.py):
    persona = ...load...
    if not show_persona_editor and onboarding.should_show(persona):
        onboarding.render(persona)
        st.stop()           # 나머지 화면은 그리지 않음 (집중 온보딩)

단계 (`_onb_step`):
    0  환영 — "맞춤형 인사이트를 위해 페르소나를 설정할까요?" + [시작] / [나중에 하기]
    1  이름 (+[나중에 하기])
    2  팀 · 부서 (팀 먼저 — Enter/Tab 으로 팀→부서 이동)
    3  직무
    4  관심 공정(작업 정의 있으면 multiselect) + 관심 키워드(콤마/Enter→칩) + [완료]
    5  완료 — "지금 바로 뉴스 수집을 실행할까요?" + [지금 수집 실행] / [나중에 하기]
    6  수집 실행 — 진행 표시 + 결과 요약 + [✓ 시작하기] (닫으면 전체 새로고침)

완료 시 `persona.derive.derive_and_store` 로 SOLA 관심사 분석(LLM, 미설정 시
규칙 폴백)을 실행해 derived_interests / matched_processes 를 채운다.

키보드 UX (`ui.components.inject_focus_nav`):
    각 입력 단계의 마지막 텍스트 입력에서 Enter → [다음] 버튼 자동 클릭,
    그 외 입력 Enter → 다음 입력 포커스. 키워드 입력은 콤마 → 칩 등록.

CLAUDE.md 규칙:
  - on_click 금지 → `if st.button(): pending flag → st.rerun()` 패턴
  - 모든 state 쓰기는 run 최상단 pending 핸들러에서 (위젯 인스턴스화 이전)
  - 외부/사용자 문자열은 사용 안 함(고정 카피) — XSS 위험 없음
  - 네임스페이스: 위젯 key `onb_*`, pending `_do_onb_*`, 단계 `_onb_step`
"""
from __future__ import annotations

import streamlit as st

from persona import derive as persona_derive
from persona import store as persona_store
from persona.schema import Persona, parse_keywords_input
from roadmap.query import load_latest as _load_tasks
from ui.components import inject_focus_nav


_TOTAL_INPUT_STEPS = 4  # 이름 / 팀·부서 / 직무 / 관심 공정·키워드
_STEP_COLLECT_OFFER = 5  # 완료 직후 — 수집 실행 제안
_STEP_COLLECT_RUN = 6    # 수집 실행·결과 (닫으면 전체 새로고침)


def should_show(persona: Persona) -> bool:
    """온보딩 마법사를 띄울지 결정.

    - 완료 직후 수집 제안/실행 단계(step≥5) → True (persona 는 이미 저장됨)
    - 페르소나가 이미 설정됨(is_set) → False
    - "나중에 하기" 영구 마커 또는 이번 세션 dismiss → False
    """
    if st.session_state.get("_onb_step", 0) >= _STEP_COLLECT_OFFER:
        return True
    if persona.is_set():
        return False
    if st.session_state.get("_onb_dismissed_session"):
        return False
    if persona_store.is_onboarding_dismissed():
        return False
    return True


def _options(df, col: str) -> list[str]:
    if df is None or df.empty or col not in df.columns:
        return []
    return sorted(df[col].dropna().astype(str).unique().tolist())


# 마법사 입력 위젯 key — 단계 전환 시 unmount 되면 Streamlit 이 state 를 GC 하므로
# (I-2 계열 함정) 매 전환마다 안정 저장소 `_onb_data` 로 스냅샷한다.
_WIZARD_KEYS = ("onb_name", "onb_team", "onb_dept", "onb_job", "onb_lv3", "onb_keywords")


def _onb_data() -> dict:
    return st.session_state.setdefault("_onb_data", {})


def _keywords_from(raw) -> list[str]:
    """키워드 입력값 정규화 — multiselect 칩(list) 또는 구버전 문자열 둘 다 수용."""
    if isinstance(raw, str):
        return parse_keywords_input(raw)
    return parse_keywords_input(", ".join(str(k) for k in (raw or [])))


def _snapshot_inputs() -> None:
    """현재 run 최상단에서 살아있는 onb_* 위젯 값을 `_onb_data` 로 보존.

    버튼 클릭으로 발생한 rerun 의 최상단에서는 직전 run 에 사용자가 입력한
    위젯 값이 아직 session_state 에 남아있다 → 여기서 스냅샷하면 안전.
    """
    data = _onb_data()
    for k in _WIZARD_KEYS:
        if k in st.session_state:
            data[k] = st.session_state[k]


# ── pending 핸들러 (run 최상단) ──────────────────────────────

def _handle_pending() -> None:
    if st.session_state.pop("_do_onb_start", False):
        st.session_state["_onb_step"] = 1
        st.rerun()

    if st.session_state.pop("_do_onb_next", False):
        _snapshot_inputs()
        st.session_state["_onb_step"] = min(
            st.session_state.get("_onb_step", 1) + 1, _TOTAL_INPUT_STEPS
        )
        st.rerun()

    if st.session_state.pop("_do_onb_prev", False):
        _snapshot_inputs()
        st.session_state["_onb_step"] = max(st.session_state.get("_onb_step", 1) - 1, 1)
        st.rerun()

    if st.session_state.pop("_do_onb_dismiss", False):
        persona_store.dismiss_onboarding()
        st.session_state["_onb_dismissed_session"] = True
        st.session_state.pop("_onb_step", None)
        st.session_state.pop("_onb_data", None)
        st.rerun()

    if st.session_state.pop("_do_onb_finish", False):
        _snapshot_inputs()
        data = _onb_data()
        new = Persona(
            name=str(data.get("onb_name", "")).strip(),
            team=str(data.get("onb_team", "")).strip(),
            dept=str(data.get("onb_dept", "")).strip(),
            job=str(data.get("onb_job", "")).strip(),
            interest_lv3=list(data.get("onb_lv3", []) or []),
            interest_tasks=[],
            interest_keywords=_keywords_from(data.get("onb_keywords", [])),
        )
        persona_store.save(new)
        # SOLA 관심사 분석 — LLM 미설정/오류 시 내부에서 규칙 폴백·no-op (저장은 이미 완료).
        new = persona_derive.derive_and_store(new)
        persona_store.clear_onboarding_dismiss()
        st.session_state["persona"] = new
        st.session_state.pop("_onb_data", None)
        # 5단계부터 키워드 multiselect 가 unmount 되며 위젯 상태가 GC 되는데,
        # AppTest 가 직전 트리를 직렬화할 때 그 상태를 다시 읽어 KeyError 가 난다
        # → 일반 세션 값으로 유지해 두면 실런타임·테스트 모두 무해하게 통과.
        st.session_state["onb_keywords"] = list(new.interest_keywords)
        st.session_state["persona_page_msg"] = ("ok", f"환영합니다, {new.label()} 님! 페르소나가 저장됐어요.")
        # 모달은 닫지 않고 수집 제안 단계로 — "지금 바로 뉴스 수집할까요?"
        st.session_state["_onb_step"] = _STEP_COLLECT_OFFER
        st.rerun()

    if st.session_state.pop("_do_onb_collect_now", False):
        st.session_state["_onb_step"] = _STEP_COLLECT_RUN
        st.rerun()

    if st.session_state.pop("_do_onb_close", False):
        # 수집 제안 거절 또는 수집 결과 확인 후 — 마법사 상태 정리 + 전체 새로고침.
        for k in ("_onb_step", "_onb_data", "_onb_collect_result"):
            st.session_state.pop(k, None)
        st.rerun()


# ── 스타일 ──────────────────────────────────────────────────

def _inject_css() -> None:
    st.html(
        """
        <style>
          /* 온보딩 중앙 카드 — v2 Azure 토큰 */
          .onb-hero {
            max-width: 560px; margin: 8px auto 18px; text-align: center;
          }
          .onb-badge {
            display: inline-flex; align-items: center; gap: 6px;
            padding: 5px 12px; border-radius: 999px;
            background: rgba(37,99,235,0.10); color: #2563EB;
            font-size: 12.5px; font-weight: 700; letter-spacing: 0.02em;
            margin-bottom: 14px;
          }
          .onb-title {
            font-size: 26px; font-weight: 800; color: #0F172A;
            letter-spacing: -0.02em; margin: 0 0 10px;
          }
          .onb-sub {
            font-size: 15px; color: #475569; line-height: 1.6; margin: 0;
          }
          .onb-steps {
            display: flex; gap: 6px; justify-content: center; margin: 18px auto 4px;
          }
          .onb-dot {
            width: 28px; height: 4px; border-radius: 2px; background: #E2E8F0;
          }
          .onb-dot-on { background: #2563EB; }
          .onb-dot-done { background: #93C5FD; }
          .onb-step-label {
            text-align: center; font-size: 12.5px; color: #94A3B8;
            font-weight: 700; margin-bottom: 2px;
          }
          .onb-q {
            text-align: center; font-size: 19px; font-weight: 800;
            color: #0F172A; margin: 6px auto 2px; letter-spacing: -0.01em;
          }
          .onb-q-help {
            text-align: center; font-size: 13.5px; color: #64748B;
            margin: 0 auto 6px; line-height: 1.5;
          }
          /* 단계마다 모달 높이가 출렁이지 않게 본문 높이 통일 —
             가장 긴 입력 단계(2/4) 기준 min-height, 더 길면 자연 확장.
             st.container(key=) 는 stVerticalBlock 자체에 st-key-* 클래스가 붙는다. */
          .st-key-onb_body { min-height: 470px; }
          /* 입력 단계 — 본문 바로 아래(1뎁스) 내부 컨테이너만 남은 높이를 차지하고,
             그 마지막 요소(네비 버튼 행)를 하단 고정해 빈 공간이 본문 중간에 생기게.
             (컬럼 내부의 중첩 VerticalBlock 은 건드리지 않는다) */
          .st-key-onb_body > div[data-testid="stVerticalBlock"],
          .st-key-onb_body > div > div[data-testid="stVerticalBlock"] {
            flex-grow: 1;
          }
          .st-key-onb_body > div[data-testid="stVerticalBlock"] > div:last-child,
          .st-key-onb_body > div > div[data-testid="stVerticalBlock"] > div:last-child {
            margin-top: auto;
          }
          /* 환영 화면 — 시작 버튼부터 아래(버튼 2 + 캡션)를 하단 고정. */
          .st-key-onb_body > div:has([class*="st-key-onb_start_btn"]) {
            margin-top: auto; flex-grow: 0 !important;
          }
        </style>
        """
    )


def _progress_html(step: int) -> str:
    dots = []
    for i in range(1, _TOTAL_INPUT_STEPS + 1):
        cls = "onb-dot"
        if i < step:
            cls += " onb-dot-done"
        elif i == step:
            cls += " onb-dot-on"
        dots.append(f'<span class="{cls}"></span>')
    return (
        f'<div class="onb-step-label">단계 {step} / {_TOTAL_INPUT_STEPS}</div>'
        f'<div class="onb-steps">{"".join(dots)}</div>'
    )


# ── 렌더 (중앙 모달 + backdrop 딤 = st.dialog) ───────────────

def render(persona: Persona) -> None:
    """온보딩 마법사 렌더 — 실제 화면 위에 중앙 모달로 띄운다.

    app.py 는 화면(보드 등)을 먼저 렌더한 뒤 should_show True 일 때 이 함수를
    호출한다. `st.dialog(dismissible=False)` 라 backdrop/ESC/X 로는 닫히지 않고
    "나중에 하기" 또는 단계 진행 버튼으로만 종료된다 → 닫히면 should_show 가
    False 가 되어 다음 run 에서 다시 뜨지 않는다.
    """
    _handle_pending()
    step = st.session_state.get("_onb_step", 0)
    if step == 0:
        title = "반갑습니다 👋"
    elif step == _STEP_COLLECT_OFFER:
        title = "페르소나 설정 완료 🎉"
    elif step == _STEP_COLLECT_RUN:
        title = "📡 뉴스 수집"
    else:
        title = "페르소나 설정"
    # 동적 title 을 위해 런타임 데코레이트.
    dialog = st.dialog(title, width="large", dismissible=False)
    dialog(_dialog_body)(persona)


def _dialog_body(persona: Persona) -> None:
    """모달 내부 — 단계에 따라 환영 / 입력 스텝 / 수집 제안·실행.

    본문 전체를 `onb_body` 컨테이너(min-height 고정 + 마지막 요소 하단 고정)로
    감싸 단계마다 모달 높이가 출렁이지 않게 통일한다 (`_inject_css` 참고).
    """
    _inject_css()
    step = st.session_state.get("_onb_step", 0)
    with st.container(key="onb_body"):
        if step == 0:
            _render_welcome()
        elif step == _STEP_COLLECT_OFFER:
            _render_collect_offer()
        elif step == _STEP_COLLECT_RUN:
            _render_collect_run()
        else:
            _render_step(step, persona)
            # 키보드 UX — 모달 첫 입력 자동 포커스 + Enter→다음 입력 이동.
            # nonce=step: 단계 전환(rerun) 시 스크립트 재실행 → 새 단계 첫 입력 재포커스.
            # submit: 마지막 텍스트 입력 Enter = [다음] 클릭 (4단계는 키워드 Enter=칩 등록이라 제외).
            # chips: 키워드 multiselect 에서 콤마 입력 → 칩(버블) 즉시 등록.
            # 주입 위치는 onb_body 컨테이너 **안** — 밖에 두면 단계 화면만 요소+gap
            # 16px 이 더 생겨 환영/제안 화면과 모달 높이가 어긋난다(높이 통일).
            submit_sel = (
                f".st-key-onb_next_{step} button" if step < _TOTAL_INPUT_STEPS else ""
            )
            chips_sel = ".st-key-onb_keywords" if step == _TOTAL_INPUT_STEPS else ""
            inject_focus_nav(
                '[data-testid="stDialog"]',
                nonce=f"onb-step-{step}",
                submit_selector=submit_sel,
                chips_selector=chips_sel,
            )


def _render_welcome() -> None:
    st.html(
        """
        <div class="onb-hero">
          <span class="onb-badge">✨ 처음 오셨네요</span>
          <p class="onb-sub">
            부서·직무·관심 공정을 알려주시면 <b>오늘의 보드</b>와 <b>SOLA</b>가
            당신의 작업에 맞춘 인사이트로 채워집니다.<br>
            1분이면 끝나요 — 지금 설정할까요?
          </p>
        </div>
        """
    )
    if st.button("페르소나 설정 시작하기", type="primary", use_container_width=True, key="onb_start_btn"):
        st.session_state["_do_onb_start"] = True
        st.rerun()
    if st.button("나중에 하기", use_container_width=True, key="onb_skip_btn"):
        st.session_state["_do_onb_dismiss"] = True
        st.rerun()
    st.caption("나중에 사이드바 페르소나 카드에서 언제든 설정할 수 있어요.")


def _render_step(step: int, persona: Persona) -> None:
    tasks = _load_tasks()
    data = _onb_data()
    st.html(_progress_html(step))

    with st.container():  # dialog 폭이 이미 좁아 별도 중앙 컬럼 불필요
        if step == 1:
            st.html('<div class="onb-q">이름을 알려주세요</div>'
                    '<div class="onb-q-help">보고서·제안서에 표시될 이름이에요.</div>')
            st.text_input("이름", value=data.get("onb_name", persona.name), key="onb_name",
                          placeholder="예: 홍길동", label_visibility="collapsed")

        elif step == 2:
            st.html('<div class="onb-q">어느 팀·부서에서 일하시나요?</div>'
                    '<div class="onb-q-help">매칭·자동화 기회가 이 부서 기준으로 정렬됩니다. '
                    '팀 입력 후 Enter/Tab → 부서, 부서 입력 후 Enter → 다음.</div>')
            dept_opts = _options(tasks, "dept")
            team_opts = _options(tasks, "team")
            cur_dept = data.get("onb_dept", persona.dept)
            cur_team = data.get("onb_team", persona.team)
            # 팀이 부서보다 위 — Enter/Tab 순서(팀→부서)도 DOM 순서를 그대로 따른다.
            if team_opts:
                cur = cur_team if cur_team in team_opts else ""
                st.selectbox("팀", [""] + team_opts,
                             index=([""] + team_opts).index(cur) if cur else 0,
                             key="onb_team")
            else:
                st.text_input("팀", value=cur_team, key="onb_team",
                              placeholder="예: 자동화 1팀")
            if dept_opts:
                cur = cur_dept if cur_dept in dept_opts else ""
                st.selectbox("부서", [""] + dept_opts,
                             index=([""] + dept_opts).index(cur) if cur else 0,
                             key="onb_dept")
            else:
                st.text_input("부서", value=cur_dept, key="onb_dept",
                              placeholder="예: 생산기술팀, 자동화기술팀")
            if not dept_opts and not team_opts:
                st.caption("🗂 작업 정의 데이터를 아직 안 올려서 자유 입력이에요. 올린 뒤엔 추천 목록으로 바뀝니다.")

        elif step == 3:
            st.html('<div class="onb-q">맡고 계신 직무는요?</div>'
                    '<div class="onb-q-help">예: 용접 담당 · 자동화 엔지니어 · 품질 검사관</div>')
            st.text_input("직무", value=data.get("onb_job", persona.job), key="onb_job",
                          placeholder="예: 도장 품질 검사관", label_visibility="collapsed")

        elif step == 4:
            st.html('<div class="onb-q">관심 공정과 키워드를 알려주세요</div>'
                    '<div class="onb-q-help">선택한 공정·키워드 중심으로 뉴스 수집과 트렌드·자동화 기회가 정렬됩니다.</div>')
            lv3_opts = _options(tasks, "lv3")
            if lv3_opts:
                seed = data.get("onb_lv3", persona.interest_lv3)
                default = [v for v in seed if v in lv3_opts]
                st.multiselect("관심 공정", options=lv3_opts, default=default,
                               key="onb_lv3")
            else:
                st.caption("관심 공정 선택은 작업 정의 데이터 업로드 후 활성화됩니다. 지금은 건너뛰고 나중에 추가할 수 있어요.")
                data["onb_lv3"] = list(persona.interest_lv3)
            # 키워드 — 콤마/Enter 로 하나씩 칩(버블) 등록 (accept_new_options).
            seed_kws = _keywords_from(data.get("onb_keywords", persona.interest_keywords))
            st.multiselect(
                "관심 키워드 (콤마/Enter로 하나씩 등록)",
                options=seed_kws,
                default=seed_kws,
                key="onb_keywords",
                accept_new_options=True,
                placeholder="예: 용접 로봇 ← 입력 후 콤마(,) 또는 Enter",
                help="등록한 키워드는 뉴스 수집 검색어에 바로 합류합니다.",
            )

        st.write("")
        # ── 네비게이션 버튼 ──
        if step < _TOTAL_INPUT_STEPS:
            cprev, cnext = st.columns(2)
            with cprev:
                if step == 1:
                    # 첫 입력 단계 — 왼쪽은 [나중에 하기] (환영 화면과 동일 dismiss).
                    if st.button("나중에 하기", use_container_width=True, key="onb_later_1"):
                        st.session_state["_do_onb_dismiss"] = True
                        st.rerun()
                elif st.button("← 이전", use_container_width=True, key=f"onb_prev_{step}"):
                    st.session_state["_do_onb_prev"] = True
                    st.rerun()
            with cnext:
                if st.button("다음 →", type="primary", use_container_width=True, key=f"onb_next_{step}"):
                    st.session_state["_do_onb_next"] = True
                    st.rerun()
        else:
            cprev, cdone = st.columns(2)
            with cprev:
                if st.button("← 이전", use_container_width=True, key=f"onb_prev_{step}"):
                    st.session_state["_do_onb_prev"] = True
                    st.rerun()
            with cdone:
                if st.button("✓ 완료", type="primary", use_container_width=True, key="onb_finish_btn"):
                    st.session_state["_do_onb_finish"] = True
                    st.rerun()

        # [나중에 하기]는 환영 화면 + 1단계(이름)에만 — 2단계부터는 이전/다음만
        # 노출해 모달을 단순하게 유지 (시작 후 이탈은 브라우저 새로고침으로도 가능).


# ── 완료 후 — 뉴스 수집 제안·실행 ───────────────────────────

def _render_collect_offer() -> None:
    """5단계 — 페르소나 저장 완료, 지금 바로 뉴스 수집을 실행할지 제안."""
    st.html(
        """
        <div class="onb-hero">
          <span class="onb-badge">🎉 설정 완료</span>
          <p class="onb-sub">
            페르소나가 저장됐어요. 등록한 관심 키워드로<br>
            <b>지금 바로 뉴스를 수집</b>할까요? 1~2분 정도 걸려요.
          </p>
        </div>
        """
    )
    clater, cgo = st.columns(2)
    with clater:
        if st.button("나중에 하기", use_container_width=True, key="onb_collect_later"):
            st.session_state["_do_onb_close"] = True
            st.rerun()
    with cgo:
        if st.button("📡 지금 수집 실행", type="primary", use_container_width=True,
                     key="onb_collect_now"):
            st.session_state["_do_onb_collect_now"] = True
            st.rerun()
    st.caption("나중에 🗞 뉴스 수집 화면의 [🔄 지금 뉴스 수집]으로 언제든 실행할 수 있어요.")


def _render_collect_run() -> None:
    """6단계 — 수집 실행(진행 표시) + 결과 요약 + [✓ 시작하기].

    수집·진행률·결과 요약·캐시 무효화는 수집 현황 모달과 동일 경로
    (`data_management_v2._run_collect_for_modal` / `_collect_result_summary_html`)
    를 재사용한다. 결과는 `_onb_collect_result` 세션에 저장해 rerun 시 재수집을
    가드. [✓ 시작하기]가 온보딩 상태를 비우고 rerun → 캐시는 이미 무효화돼
    있으므로 전체 화면이 새 수집 데이터로 다시 그려진다(전체 새로고침).
    """
    from ui import components as _components
    from ui import data_management_v2 as _dm
    from ui.styles import inject_screen_css

    inject_screen_css("data_management")  # 결과 요약 카드(.sc-cm-*) 스타일
    result = st.session_state.get("_onb_collect_result")
    if result is None:
        with st.status("📡 뉴스 수집 중… 기사 본문·이미지를 가져오는 중이에요.",
                       expanded=True) as _stat:
            prog = st.progress(0.0, text="수집 준비 중…")
            result = _dm._run_collect_for_modal(prog)
            st.session_state["_onb_collect_result"] = result
            _stat.update(
                label="수집 완료" if result.get("ok") else "수집 중 오류 발생",
                state="complete" if result.get("ok") else "error",
                expanded=False,
            )
    st.html(_components.prepare_screen_html(
        _dm._collect_result_summary_html(result)
    ))
    if st.button("✓ 시작하기", type="primary", use_container_width=True,
                 key="onb_collect_done"):
        st.session_state["_do_onb_close"] = True
        st.rerun()
