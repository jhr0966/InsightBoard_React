"""SOLA composer 실 LLM 호출 wire — 전송 → 응답 → 영구화 / 폴백 / 컨텍스트 빌드."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from persona.schema import Persona
from sola.client import LLMNotConfigured
from ui import sola_workshop_v2 as sola_v2


# ── 메시지 렌더링 (HTML 정확성) ──────────────────────────────

def test_msg_html_user_role_emits_user_classes():
    h = sola_v2._msg_html("user", "안녕", "")
    assert "ws-msg-user" in h
    assert "ws-bubble-user" in h
    assert "안녕" in h


def test_msg_html_assistant_role_emits_sola_classes():
    h = sola_v2._msg_html("assistant", "도움이 필요하세요?", "")
    assert "ws-msg-user" not in h
    assert "ws-bubble-sola" in h
    assert "ws-msg-from-name" in h


def test_msg_html_escapes_html():
    """XSS 방어 — < > 같은 문자는 escape 되어야."""
    h = sola_v2._msg_html("user", "<script>alert(1)</script>", "")
    assert "<script>" not in h
    assert "&lt;script&gt;" in h


def test_msg_html_newlines_become_br():
    h = sola_v2._msg_html("assistant", "line1\nline2", "")
    assert "line1<br>line2" in h


def test_render_messages_empty_shows_friendly_prompt():
    out = sola_v2._render_messages_html([])
    assert "대화를 시작해보세요" in out
    assert "SOLA와 검토" in out


def test_render_messages_emits_ordered_html():
    msgs = [
        {"role": "user", "content": "Q1", "ts": ""},
        {"role": "assistant", "content": "A1", "ts": ""},
        {"role": "user", "content": "Q2", "ts": ""},
    ]
    out = sola_v2._render_messages_html(msgs)
    assert out.index("Q1") < out.index("A1") < out.index("Q2")


# ── LLM 입력 messages 빌드 ───────────────────────────────────

def test_build_llm_messages_includes_system_and_persona():
    persona = Persona(name="홍길동", dept="도장1팀", job="검사관")
    history = [
        {"role": "user", "content": "Q", "ts": ""},
        {"role": "assistant", "content": "A", "ts": ""},
    ]
    import streamlit as st
    st.session_state.pop("_chat_context_for_sola", None)
    msgs = sola_v2._build_llm_messages(persona, history)
    assert msgs[0]["role"] == "system"
    assert "SOLA" in msgs[0]["content"]
    assert "도장1팀" in msgs[0]["content"]  # persona block 주입
    assert msgs[1] == {"role": "user", "content": "Q"}
    assert msgs[2] == {"role": "assistant", "content": "A"}


def test_build_llm_messages_includes_screen_context_when_set():
    """_chat_context_for_sola 가 set 되어 있으면 system 메시지에 첨부."""
    import streamlit as st
    persona = Persona(name="홍길동", dept="도장1팀")
    st.session_state["_chat_context_for_sola"] = (
        "--- 현재 화면: 오늘의 보드 ---\n"
        "오늘 KPI: 수집 125건 · 매칭 18건\n"
        "④ 자동화 기회: 도장 · 비전 검사 (점수 95)"
    )
    try:
        msgs = sola_v2._build_llm_messages(persona, [])
    finally:
        st.session_state.pop("_chat_context_for_sola", None)
    sys_content = msgs[0]["content"]
    assert "오늘의 보드" in sys_content
    assert "비전 검사" in sys_content
    assert "점수 95" in sys_content
    # 페르소나 블록은 여전히 존재
    assert "도장1팀" in sys_content


def test_build_llm_messages_omits_screen_context_when_unset():
    import streamlit as st
    st.session_state.pop("_chat_context_for_sola", None)
    msgs = sola_v2._build_llm_messages(Persona(name="홍길동", dept="도장"), [])
    assert "현재 화면" not in msgs[0]["content"]


def test_build_llm_messages_skips_invalid_history_entries():
    persona = Persona()
    history = [
        {"role": "user", "content": "ok", "ts": ""},
        {"role": "user", "content": ""},          # empty content → skip
        {"role": "tool", "content": "irrelevant"}, # invalid role → skip
    ]
    msgs = sola_v2._build_llm_messages(persona, history)
    user_msgs = [m for m in msgs if m["role"] == "user"]
    assert user_msgs == [{"role": "user", "content": "ok"}]


# ── 영구화 round-trip ────────────────────────────────────────

@pytest.fixture
def clean_chat_log(tmp_path, monkeypatch):
    """chat_log 가 임시 디렉토리를 쓰도록 — 실 데이터 격리."""
    import config
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path)
    from store import chat_log
    monkeypatch.setattr(chat_log, "SOLA_DIR", tmp_path / "sola")
    import streamlit as st
    st.session_state.pop("_sola_messages", None)
    yield
    st.session_state.pop("_sola_messages", None)


def test_append_message_persists_to_chat_log(clean_chat_log):
    import streamlit as st
    st.session_state["_sola_messages"] = []
    sola_v2._append_message("user", "hello")
    sola_v2._append_message("assistant", "world")
    from store import chat_log
    saved = chat_log.load_history(sola_v2._SOLA_CHAT_KEY)
    assert [m["role"] for m in saved] == ["user", "assistant"]
    assert [m["content"] for m in saved] == ["hello", "world"]


def test_load_messages_seeds_from_chat_log_when_session_empty(clean_chat_log):
    """첫 진입 시 chat_log 에서 load."""
    from store import chat_log
    chat_log.save_history(
        [{"role": "user", "content": "이전 질문", "ts": ""}],
        sola_v2._SOLA_CHAT_KEY,
    )
    msgs = sola_v2._load_messages()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "이전 질문"


# ── consume_send happy / 미설정 폴백 / 일반 예외 ─────────────

def test_consume_send_happy_path_appends_user_and_assistant(clean_chat_log):
    import streamlit as st
    st.session_state["_sola_messages"] = []
    st.session_state["_do_sola_send"] = "테스트 질문"
    with patch("sola.client.chat", return_value="테스트 답변"), \
         patch("streamlit.rerun"):
        sola_v2._consume_send_if_any(Persona(name="홍길동"))
    msgs = st.session_state["_sola_messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "테스트 질문"
    assert msgs[1]["content"] == "테스트 답변"
    # pending flag 소비됨
    assert "_do_sola_send" not in st.session_state


def test_consume_send_llm_not_configured_falls_back_to_preview(clean_chat_log):
    import streamlit as st
    st.session_state["_sola_messages"] = []
    st.session_state["_do_sola_send"] = "Q"
    with patch("sola.client.chat", side_effect=LLMNotConfigured("no key")), \
         patch("streamlit.rerun"):
        sola_v2._consume_send_if_any(Persona())
    msgs = st.session_state["_sola_messages"]
    assert len(msgs) == 2
    # preview 마커 — sola.preview.format_messages_preview 의 typical 출력
    assert "LLM 미설정" in msgs[1]["content"] or "system" in msgs[1]["content"]


def test_consume_send_general_exception_yields_friendly_assistant_msg(clean_chat_log):
    import streamlit as st
    st.session_state["_sola_messages"] = []
    st.session_state["_do_sola_send"] = "Q"
    with patch("sola.client.chat", side_effect=RuntimeError("network")), \
         patch("streamlit.rerun"):
        sola_v2._consume_send_if_any(Persona())
    msgs = st.session_state["_sola_messages"]
    assert msgs[-1]["role"] == "assistant"
    assert "응답 생성 실패" in msgs[-1]["content"]
    assert "RuntimeError" in msgs[-1]["content"]


def test_consume_send_empty_payload_is_noop(clean_chat_log):
    import streamlit as st
    st.session_state["_sola_messages"] = []
    st.session_state["_do_sola_send"] = "   "  # whitespace only
    with patch("sola.client.chat") as cli, patch("streamlit.rerun"):
        sola_v2._consume_send_if_any(Persona())
        cli.assert_not_called()
    assert st.session_state["_sola_messages"] == []


def test_consume_send_no_pending_is_noop(clean_chat_log):
    import streamlit as st
    st.session_state["_sola_messages"] = []
    st.session_state.pop("_do_sola_send", None)
    with patch("sola.client.chat") as cli, patch("streamlit.rerun"):
        sola_v2._consume_send_if_any(Persona())
        cli.assert_not_called()


# ── prefill ask 흐름 ─────────────────────────────────────────

def test_ask_prefill_sets_send_payload_from_composer_prefill():
    import streamlit as st
    st.session_state["_do_ask_prefill"] = True
    st.query_params.clear()
    st.query_params["from"] = "opp"
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전 검사"
    try:
        with patch("streamlit.rerun"):
            sola_v2._consume_prefill_ask_if_any()
        # composer_prefill 의 opp 분기가 만든 텍스트가 그대로 송신 페이로드에
        sent = st.session_state.get("_do_sola_send", "")
        assert "도장" in sent and "비전 검사" in sent
    finally:
        st.query_params.clear()
        st.session_state.pop("_do_sola_send", None)
        st.session_state.pop("_do_ask_prefill", None)
