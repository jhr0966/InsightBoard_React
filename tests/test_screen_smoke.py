"""화면 render() 오케스트레이션 스모크 — 각 v2 화면이 예외 없이 끝까지 렌더되는지.

개별 `_*_html` 빌더·pending consumer 는 단위 테스트가 덮지만, render() 가 그것들을
**조립**하는 경로(topbar → 핸드오프 → 본문 + pending 소비)는 무커버리지였다.
Streamlit 은 ScriptRunContext 없이도 위젯이 기본값을 반환하므로(st.button→False,
st.columns→컨텍스트), 실제 render() 를 호출해 "끝까지 통과(예외 0)" 만 확인하면
조립 깨짐(빠진 속성·잘못된 호출·빌더 예외)을 싸게 잡는다. mock 최소 — brittle 회피.

conftest 가 data/ 를 tmp 로 격리하므로 빈 데이터(또는 graceful 폴백) 경로를 탄다.
"""
from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

# (모듈명, area_key, render_fn, context_fn) — area_key 는 컨텍스트 블록 스모크용.
# 데이터 관리는 뉴스 수집/작업 정의 두 화면으로 분리 → render·context 함수가 각각 다르다.
_SCREENS = [
    ("ui.board_v2", "📊 오늘의 보드", "render", "chat_context_block"),
    ("ui.data_management_v2", "🗞 뉴스 수집", "render_collect", "chat_context_block_collect"),
    ("ui.data_management_v2", "📋 작업 정의", "render_taskdef", "chat_context_block_taskdef"),
    ("ui.insights_v2", "🔎 인사이트 분석", "render", "chat_context_block"),
    ("ui.sola_workshop_v2", "🤖 SOLA 작업실", "render", "chat_context_block"),
    ("ui.archive_v2", "📦 산출물 보관함", "render", "chat_context_block"),
    ("ui.persona_page", "프로필 설정", "render", "chat_context_block"),
]
_SCREEN_IDS = [f"{m.split('.')[-1]}:{a}" for m, a, *_ in _SCREENS]


@pytest.fixture
def _no_rerun():
    """우발적 st.rerun(pending 잔재 등)이 RerunException 으로 테스트를 깨지 않도록 no-op."""
    with patch("streamlit.rerun"):
        yield


@pytest.mark.parametrize("module_name,area_key,render_fn,context_fn", _SCREENS, ids=_SCREEN_IDS)
def test_screen_render_smoke_no_exception(module_name, area_key, render_fn, context_fn, _no_rerun):
    """빈 데이터(tmp 격리)에서도 화면 render 함수가 예외 없이 끝까지 통과."""
    import streamlit as st
    st.query_params.clear()
    st.session_state.clear()
    try:
        mod = importlib.import_module(module_name)
        getattr(mod, render_fn)()  # 예외 발생 시 테스트 실패 = 조립 깨짐
    finally:
        st.query_params.clear()
        st.session_state.clear()


@pytest.mark.parametrize("module_name,area_key,render_fn,context_fn", _SCREENS, ids=_SCREEN_IDS)
def test_screen_chat_context_block_smoke(module_name, area_key, render_fn, context_fn):
    """각 화면의 chat_context_block(persona) 도 예외 없이 문자열을 반환(우측 채팅 컨텍스트)."""
    from persona.schema import Persona
    mod = importlib.import_module(module_name)
    ctx_fn = getattr(mod, context_fn, None)
    if ctx_fn is None:
        pytest.skip(f"{module_name}: {context_fn} 없음")
    out = ctx_fn(Persona(name="홍길동", dept="도장1팀"))
    assert isinstance(out, str)


def test_sola_workshop_render_smoke_with_handoff(_no_rerun):
    """SOLA 작업실 — 인계(?from=opp) 컨텍스트가 있어도 render() 통과(자동실행 배선 포함)."""
    import streamlit as st
    from ui import sola_workshop_v2
    st.query_params.clear()
    st.session_state.clear()
    st.query_params["from"] = "opp"
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전 검사"
    try:
        sola_workshop_v2.render()
    finally:
        st.query_params.clear()
        st.session_state.clear()
