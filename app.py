"""제조기술 로드맵 인사이트보드 — 업무 흐름형 Streamlit 진입점.

6개 업무 메뉴 (구 '데이터 관리'를 수집/작업정의 두 화면으로 분리):
  1. 오늘의 보드      — 매일 확인하는 맞춤 인사이트
  2. 뉴스 수집        — 수집잡 + 키워드 + 출처 (탭 3)
  3. 작업 정의        — 엑셀 업로드 + 작업 정의 관리 (탭 없이 단일 화면)
  4. 인사이트 분석    — 트렌드·매칭·자동화 기회 (탭 분할)
  5. SOLA 작업실      — 요약·과제·제안서 초안
  6. 산출물 보관함    — 북마크·채택 의사결정 (단일 페이지)

레이아웃 (Phase A — 네이티브 셸):
  좌측 = 네이티브 st.sidebar (nav 단일 소스) · 본문 = st.columns(main, chat)
  우측 chat 컬럼 = chat_panel.render_side (실제 작동 채팅).
  **모든 화면 동일** — SOLA 작업실도 중앙=산출물 작업대, 우측=채팅으로 통일.
"""
from __future__ import annotations

import streamlit as st

from config import ensure_data_dirs
from store import bookmarks as _bookmarks_store
from persona import store as _persona_store
from ui import (
    app_shell,
    archive_v2,
    board_v2,
    chat_panel,
    data_health,  # noqa: F401 — 테스트 의존: tests/test_data_health.py.
    data_management_v2,
    insights_v2,
    onboarding,
    persona_page,
    sidebar,
    sola_workshop_v2,
)
from ui.styles import inject_global_styles, inject_user_prefs


st.set_page_config(
    page_title="제조기술 로드맵 인사이트보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_data_dirs()
inject_global_styles()
inject_user_prefs()  # 저장된 테마·글자 크기 (베이스 토큰 이후 → :root 오버라이드 우선)

# 세션당 1회: 미채택 제안서 만료 정리 (기본 30일, adopted 는 보존).
if not st.session_state.get("_did_expire_check"):
    _bookmarks_store.expire_old()
    st.session_state["_did_expire_check"] = True

# 좌측 네이티브 사이드바 = nav 단일 소스 (페르소나 카드 · 5-nav · LLM 상태).
with st.sidebar:
    area = sidebar.render()

_persona = st.session_state.get("persona") or _persona_store.load()
st.session_state["persona"] = _persona

# 글로벌 chat 전송 핸들러 — 어느 area 에서든 chat_input/form 으로 송신한 텍스트를
# LLM 호출 → 응답 append → chat_log 영구화 (활성 thread 의 chat_key 로 저장).
chat_panel.consume_send_if_any(_persona)

_is_persona = bool(st.session_state.get("show_persona_editor"))
_area_key = "프로필 설정" if _is_persona else area

# 모든 화면 통일: [좌 사이드바 │ 중앙 콘텐츠(main_col) │ 우 LLM 채팅(chat_col)].
# 각 화면이 보여주는 데이터를 SOLA 컨텍스트로 packaging 해 두면 우측 채팅이 그 화면
# 콘텐츠에 대해 답할 수 있다. SOLA 작업실도 동일 — 중앙은 산출물 작업대, 우측은 대화.
_main_col, _chat_col = st.columns([2.3, 1], gap="large")
with _main_col:
    if _is_persona:
        persona_page.render()
        st.session_state["_chat_context_for_sola"] = persona_page.chat_context_block(_persona)
    elif area == "📊 오늘의 보드":
        board_v2.render()
        st.session_state["_chat_context_for_sola"] = board_v2.chat_context_block(_persona)
    elif area == "🗞 뉴스 수집":
        data_management_v2.render_collect()
        st.session_state["_chat_context_for_sola"] = data_management_v2.chat_context_block_collect(_persona)
    elif area == "📋 작업 정의":
        data_management_v2.render_taskdef()
        st.session_state["_chat_context_for_sola"] = data_management_v2.chat_context_block_taskdef(_persona)
    elif area == "🔎 인사이트 분석":
        insights_v2.render()
        st.session_state["_chat_context_for_sola"] = insights_v2.chat_context_block(_persona)
    elif area == "🤖 SOLA 작업실":
        sola_workshop_v2.render()
        st.session_state["_chat_context_for_sola"] = sola_workshop_v2.chat_context_block(_persona)
    else:
        archive_v2.render()
        st.session_state["_chat_context_for_sola"] = archive_v2.chat_context_block(_persona)
with _chat_col:
    chat_panel.render_side(_persona, area_key=_area_key)

# 페르소나 미설정 + 미dismiss → 배경 화면 위에 중앙 모달로 온보딩.
# 명시적 편집(show_persona_editor) 중에는 마법사를 띄우지 않는다.
if not _is_persona and onboarding.should_show(_persona):
    onboarding.render(_persona)
