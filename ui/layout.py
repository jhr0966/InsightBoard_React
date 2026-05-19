"""레이아웃 헬퍼 — 페이지 메인 + (옵션) 우측 사이드 채팅 패널.

핵심 패턴:
  is_open = page_header(title, sub, chat_toggle_key="<key>")
  with main_col, chat_col in split_with_chat(is_open):
      with main_col: ...   # 화면 주요 컨텐츠
      if chat_col:
          render_chat_panel(...)  # 채팅 패널

또는 컨텍스트 매니저 스타일:
  with main_and_chat("<key>", title="...", sub="...") as (main, chat):
      with main: render_main()
      if chat is not None:
          with chat: render_chat(...)
"""
from __future__ import annotations

import contextlib
import html as _html
from typing import Iterator

import streamlit as st

from ui.components import render_html

from persona.schema import Persona
from sola.client import LLMNotConfigured, chat
from sola.side_context import build_side_system


def split_with_chat(is_open: bool, *, main_chat_ratio: tuple[int, int] = (3, 2)):
    """is_open 이면 메인+채팅 2열, 아니면 메인 1열 반환.

    Returns:
        (main_column, chat_column_or_none)
    """
    if not is_open:
        # 단일 컬럼이지만 caller 가 일관된 패턴을 쓰도록 with 가능한 객체 반환.
        return st.container(), None
    main_col, chat_col = st.columns(list(main_chat_ratio), gap="large")
    return main_col, chat_col


def render_chat_panel(
    *,
    chat_key: str,
    page_context: str,
    persona: Persona | None = None,
    system_prompt: str = "",
    placeholder: str = "이 화면에 대해 물어보세요…",
    title: str = "💬 SOLA",
    hint: str = "",
    include_adopted: bool = True,
    include_session_proposal: bool = True,
    adopted_limit: int = 5,
) -> None:
    """우측 사이드 채팅 패널. 페이지 + 페르소나 + 채택 제안서 + 직전 제안서를 시스템에 자동 주입.

    Args:
        chat_key: 페이지별 히스토리 분리용 키. `st.session_state[f"_sidechat_{chat_key}"]`.
        page_context: 현재 화면의 내용 텍스트.
        persona: 페르소나 (있으면 시스템에 주입).
        system_prompt: 추가 시스템 지시 (선택). 비면 기본 SYSTEM_CHAT 사용.
        placeholder: 입력창 placeholder.
        title: 패널 헤더.
        hint: 패널 헤더 아래 1줄 안내.
        include_adopted: 채택된 제안서 N건을 자동 컨텍스트로 첨부.
        include_session_proposal: 세션 직전 작성 제안서(`sola_prop_result`) 자동 첨부.
        adopted_limit: 첨부할 채택 제안서 최대 건수.
    """
    from sola.prompts import SYSTEM_CHAT
    from store import bookmarks as _bm

    history_key = f"_sidechat_{chat_key}"
    pending_key = f"_sidechat_pending_{chat_key}"
    reset_key = f"_sidechat_reset_{chat_key}"

    st.session_state.setdefault(history_key, [])
    history: list[dict] = st.session_state[history_key]

    # 자동 첨부 컨텍스트 수집 (헤더 칩 표시 + LLM 호출 모두 동일 데이터 사용)
    adopted = _bm.list_adopted_proposals(limit=adopted_limit) if include_adopted else []
    session_prop = st.session_state.get("sola_prop_result") if include_session_proposal else None

    base_system = system_prompt or SYSTEM_CHAT
    _, labels = build_side_system(
        base_system=base_system,
        persona=persona,
        page_context=page_context,
        session_proposal=session_prop,
        adopted_proposals=adopted,
    )

    # 헤더 + 초기화
    head_cols = st.columns([3, 1])
    with head_cols[0]:
        render_html(
            f'<div class="chat-panel-title">{title}</div>',
            unsafe_allow_html=True,
        )
    with head_cols[1]:
        if st.button("초기화", key=f"_sidechat_resetbtn_{chat_key}", use_container_width=True):
            st.session_state[reset_key] = True

    if hint:
        render_html(
            f'<div class="chat-panel-hint">{hint}</div>',
            unsafe_allow_html=True,
        )

    # 자동 첨부 칩 노출
    if labels:
        chips = "".join(
            f'<span class="app-header-chip" style="font-size:0.68rem;padding:3px 9px;">'
            f'📎 {_html.escape(lbl)}</span>'
            for lbl in labels
        )
        render_html(
            f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:0.7rem;">{chips}</div>',
            unsafe_allow_html=True,
        )

    if st.session_state.pop(reset_key, False):
        st.session_state[history_key] = []
        st.rerun()

    # 히스토리 렌더
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 입력
    user_input = st.chat_input(placeholder, key=f"_sidechat_input_{chat_key}")
    if user_input:
        history.append({"role": "user", "content": user_input})
        st.session_state[pending_key] = True
        st.rerun()

    if st.session_state.pop(pending_key, False):
        sys_msg, _ = build_side_system(
            base_system=base_system,
            persona=persona,
            page_context=page_context,
            session_proposal=session_prop,
            adopted_proposals=adopted,
        )
        messages = [{"role": "system", "content": sys_msg}]
        messages.extend(
            {"role": m["role"], "content": m["content"]}
            for m in history if m["role"] in ("user", "assistant")
        )
        try:
            with st.spinner("LLM 호출 중…"):
                reply = chat(messages=messages, temperature=0.3)
        except LLMNotConfigured as e:
            reply = f"⚠️ LLM 미설정: {e}"
        except Exception as e:  # noqa: BLE001
            reply = f"⚠️ 호출 실패: {e}"
        history.append({"role": "assistant", "content": reply})
        st.rerun()


@contextlib.contextmanager
def main_and_chat(
    chat_key: str,
    *,
    page_context_fn=None,
    persona: Persona | None = None,
    placeholder: str = "이 화면에 대해 물어보세요…",
    hint: str = "",
    main_chat_ratio: tuple[int, int] = (3, 2),
) -> Iterator[tuple]:
    """컨텍스트 매니저 — 메인 영역 yield + 채팅 패널 자동 렌더.

    사용 예:
        with main_and_chat("home", page_context_fn=lambda: my_text) as main:
            with main:
                render_home()
        # 채팅 토글이 켜져 있으면 우측에 자동 노출됨.

    `page_context_fn` 은 호출 시점에 평가돼 LLM 시스템 컨텍스트에 주입된다.
    토글이 꺼진 상태면 context_fn 은 호출되지 않음 (lazy).
    """
    open_key = f"_chat_open_{chat_key}"
    is_open = st.session_state.get(open_key, False)
    main_col, chat_col = split_with_chat(is_open, main_chat_ratio=main_chat_ratio)
    try:
        yield main_col
    finally:
        if is_open and chat_col is not None:
            with chat_col:
                ctx = page_context_fn() if page_context_fn else ""
                render_chat_panel(
                    chat_key=chat_key,
                    page_context=ctx,
                    persona=persona,
                    placeholder=placeholder,
                    hint=hint,
                )
