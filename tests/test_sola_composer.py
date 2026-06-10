"""SOLA composer wire — 컨텍스트 빌드 / 영구화 / thread 액션·전환 / 인계 자동 전송.

send 소비(`_do_sola_send` → LLM → append → rerun)는 `chat_panel.consume_send_if_any`
단일 구현으로 이동 — happy/폴백/예외/noop 커버리지는 `test_chat_panel.py` 참조.
(구 `sola_workshop_v2._consume_send_if_any` 는 production-unused 로 삭제됨.)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from persona.schema import Persona
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
    """SOLA 영구화(chat_log + threads + disk cache) 가 임시 디렉토리를 쓰도록 격리.

    B.4 이후 메시지는 활성 thread 의 chat_key 에 저장되므로 thread store 도 격리.
    LLM 디스크 캐시(thread_title 등)도 격리해 다른 테스트의 캐시 오염 차단.
    """
    import config
    sola_dir = tmp_path / "sola"
    sola_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(config, "SOLA_DIR", sola_dir)
    from store import chat_log, sola_threads, cache as _cache
    monkeypatch.setattr(chat_log, "SOLA_DIR", sola_dir)
    monkeypatch.setattr(sola_threads, "SOLA_DIR", sola_dir)
    monkeypatch.setattr(_cache, "_cache_dir", lambda: cache_dir)
    # 다른 테스트(test_sola_client 등)에서 LRU 캐시에 남은 fake OpenAI 클라이언트
    # 영향 차단 — _client() 가 매번 새로 평가되도록 캐시 클리어.
    try:
        from sola import client as _llm_client
        _llm_client._client.cache_clear()
    except Exception:
        pass
    import streamlit as st
    # 모든 _sola_messages_* 캐시 + active thread id 초기화
    for k in [k for k in list(st.session_state.keys()) if k.startswith("_sola_messages") or k == "_sola_thread_id"]:
        st.session_state.pop(k, None)
    yield
    for k in [k for k in list(st.session_state.keys()) if k.startswith("_sola_messages") or k == "_sola_thread_id"]:
        st.session_state.pop(k, None)


def test_append_message_persists_to_chat_log(clean_chat_log):
    # 첫 user 메시지의 thread 제목 자동생성은 LLM 의존(가용 시 압축 제목, 미설정 시
    # 룰 fallback)이라 환경(CI/로컬)에 따라 값이 달라진다 → 생성기를 목해 결정적으로.
    # (제목 생성기 자체 동작은 test_thread_title_llm 가 검증. 이 테스트 목적은
    #  chat_log 영속 + message_count + 제목 wiring.)
    with patch("sola.thread_title.generate", return_value="hello 정리"):
        sola_v2._append_message("user", "hello")
        sola_v2._append_message("assistant", "world")
    # 활성 thread id 로 chat_log 에 저장됨
    from store import chat_log, sola_threads
    import streamlit as st
    active_id = st.session_state["_sola_thread_id"]
    saved = chat_log.load_history(active_id)
    assert [m["role"] for m in saved] == ["user", "assistant"]
    assert [m["content"] for m in saved] == ["hello", "world"]
    # thread message_count + title 자동 (제목 생성기 결과)
    th = sola_threads.get(active_id)
    assert th.message_count == 2
    assert th.title == "hello 정리"  # 첫 user 메시지 → 제목 생성기 결과


def test_load_messages_seeds_from_chat_log_when_session_empty(clean_chat_log):
    """첫 진입 시 활성 thread 의 chat_log 에서 load."""
    from store import chat_log, sola_threads
    # 미리 thread 만들고 그 chat_key 로 메시지 저장
    th = sola_threads.create("이전 대화")
    chat_log.save_history(
        [{"role": "user", "content": "이전 질문"}],
        th.id,
    )
    import streamlit as st
    st.session_state["_sola_thread_id"] = th.id
    msgs = sola_v2._load_messages()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "이전 질문"


# ── thread 전환 소비 — pending(오버레이 버튼) 우선 → 쿼리(딥링크) 폴백 ──

def test_switch_thread_pending_sets_active_without_rerun(clean_chat_log):
    """오버레이 버튼 경로 — render 최상단 소비라 같은 run 으로 계속(rerun 불필요)."""
    import streamlit as st
    from store import sola_threads
    th = sola_threads.create("전환 대상")
    st.query_params.clear()
    st.session_state["_switch_thread_pending"] = th.id
    try:
        with patch("streamlit.rerun") as rr:
            sola_v2._switch_thread_from_query_if_any()
            rr.assert_not_called()
        assert st.session_state["_sola_thread_id"] == th.id
        assert "_switch_thread_pending" not in st.session_state   # pop-once
    finally:
        st.query_params.clear()
        st.session_state.pop("_switch_thread_pending", None)


def test_switch_thread_pending_wins_over_query_and_strips(clean_chat_log):
    """pending(최신 클릭)이 쿼리보다 먼저 — 스테일 ?switch_thread= 는 함께 strip."""
    import streamlit as st
    from store import sola_threads
    a = sola_threads.create("a")
    b = sola_threads.create("b")
    st.query_params.clear()
    st.query_params["switch_thread"] = a.id
    st.session_state["_switch_thread_pending"] = b.id
    try:
        with patch("streamlit.rerun"):
            sola_v2._switch_thread_from_query_if_any()
        assert st.session_state["_sola_thread_id"] == b.id
        assert "switch_thread" not in st.query_params
    finally:
        st.query_params.clear()
        st.session_state.pop("_switch_thread_pending", None)


def test_switch_thread_pending_unknown_id_keeps_active(clean_chat_log):
    """존재하지 않는 id 는 무시(active 유지) — pending 은 소비."""
    import streamlit as st
    from store import sola_threads
    keep = sola_threads.create("유지")
    st.session_state["_sola_thread_id"] = keep.id
    st.session_state["_switch_thread_pending"] = "th_nonexistent_xxxxx"
    try:
        with patch("streamlit.rerun") as rr:
            sola_v2._switch_thread_from_query_if_any()
            rr.assert_not_called()
        assert st.session_state["_sola_thread_id"] == keep.id
        assert "_switch_thread_pending" not in st.session_state
    finally:
        st.session_state.pop("_switch_thread_pending", None)


def test_switch_thread_query_deep_link_still_works(clean_chat_log):
    """딥링크 호환 유지 — ?switch_thread= 1회 소비 → 전환 + strip + rerun."""
    import streamlit as st
    from store import sola_threads
    th = sola_threads.create("딥링크")
    st.query_params.clear()
    st.query_params["switch_thread"] = th.id
    try:
        with patch("streamlit.rerun") as rr:
            sola_v2._switch_thread_from_query_if_any()
            rr.assert_called_once()
        assert st.session_state["_sola_thread_id"] == th.id
        assert "switch_thread" not in st.query_params   # 재방문 재실행 방지
    finally:
        st.query_params.clear()


# ── prefill ask 흐름 ─────────────────────────────────────────

def test_ask_prefill_creates_new_thread_and_sets_send_payload(clean_chat_log):
    """인계(CTA)는 새 thread 를 만들고 prefill 텍스트를 그 thread 로 전송."""
    import streamlit as st
    from store import sola_threads

    before = len(sola_threads.list_threads())
    st.session_state["_do_ask_prefill"] = True
    st.query_params.clear()
    st.query_params["from"] = "opp"
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전 검사"
    try:
        with patch("streamlit.rerun"):
            sola_v2._consume_prefill_ask_if_any()
        # 새 thread 생성됨 + active 전환
        after = sola_threads.list_threads()
        assert len(after) == before + 1
        active_id = st.session_state["_sola_thread_id"]
        assert sola_threads.get(active_id) is not None
        # 인계 종류 기반 시드 제목
        assert sola_threads.get(active_id).title == "자동화 기회 검토"
        # composer_prefill 의 opp 텍스트가 송신 페이로드에
        sent = st.session_state.get("_do_sola_send", "")
        assert "도장" in sent and "비전 검사" in sent
    finally:
        st.query_params.clear()
        st.session_state.pop("_do_sola_send", None)
        st.session_state.pop("_do_ask_prefill", None)


def test_toggle_pin_action_flips_pinned(clean_chat_log):
    import streamlit as st
    from store import sola_threads

    th = sola_threads.create("핀 테스트")
    assert th.pinned is False
    st.session_state["_do_toggle_pin"] = th.id
    with patch("streamlit.rerun"):
        sola_v2._consume_thread_actions_if_any()
    assert sola_threads.get(th.id).pinned is True
    # 다시 토글 → 해제
    st.session_state["_do_toggle_pin"] = th.id
    with patch("streamlit.rerun"):
        sola_v2._consume_thread_actions_if_any()
    assert sola_threads.get(th.id).pinned is False


def test_delete_action_removes_thread_and_resets_active(clean_chat_log):
    import streamlit as st
    from store import sola_threads

    keep = sola_threads.create("유지")
    victim = sola_threads.create("삭제대상")
    st.session_state["_sola_thread_id"] = victim.id
    st.session_state["_do_delete_thread"] = victim.id
    with patch("streamlit.rerun"):
        sola_v2._consume_thread_actions_if_any()
    assert sola_threads.get(victim.id) is None
    # 활성 thread id 가 삭제된 것이면 초기화됨 (다음 _active_thread 가 재선정)
    assert st.session_state.get("_sola_thread_id") is None
    assert sola_threads.get(keep.id) is not None


# ── 채팅 quick-action(?sola_action=) → 작업대 pending flag 매핑 ──

def test_sola_action_generate_proposal_maps_to_payload_with_context():
    """`?sola_action=generate_proposal` → `_do_generate_proposal` (dept/lv3/from 보존)."""
    import streamlit as st
    st.query_params.clear()
    st.query_params["sola_action"] = "generate_proposal"
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전 검사"
    st.query_params["from"] = "opp"
    try:
        sola_v2._consume_sola_action_from_query_if_any()
        payload = st.session_state.get("_do_generate_proposal")
        assert payload == {"dept": "도장", "lv3": "비전 검사", "kind": "opp"}
        # sola_action 만 소비, dept/lv3 는 보존
        assert "sola_action" not in st.query_params
        assert st.query_params.get("dept") == "도장"
    finally:
        st.query_params.clear()
        st.session_state.pop("_do_generate_proposal", None)


def test_sola_action_simple_flags_map_to_true():
    """summarize/new_thread/save_proposal → 각 pending flag True."""
    import streamlit as st
    for action, flag in (
        ("summarize", "_do_summarize"),
        ("new_thread", "_do_new_thread"),
        ("save_proposal", "_do_save_proposal"),
    ):
        st.query_params.clear()
        st.query_params["sola_action"] = action
        try:
            sola_v2._consume_sola_action_from_query_if_any()
            assert st.session_state.get(flag) is True
            assert "sola_action" not in st.query_params
        finally:
            st.query_params.clear()
            st.session_state.pop(flag, None)


def test_sola_action_unknown_is_consumed_without_side_effect():
    """알 수 없는 action 은 쿼리만 소비, pending flag 미설정."""
    import streamlit as st
    st.query_params.clear()
    st.query_params["sola_action"] = "bogus"
    try:
        sola_v2._consume_sola_action_from_query_if_any()
        assert "sola_action" not in st.query_params
        assert "_do_generate_proposal" not in st.session_state
    finally:
        st.query_params.clear()


# ── 인계(?from=) 자동 LLM 전송 배선 ──────────────────────────

def test_auto_run_handoff_triggers_ask_prefill_once():
    """opp 인계가 처음 도착하면 `_do_ask_prefill` 1회 set, 같은 인계 재실행 안 함."""
    import streamlit as st
    st.query_params.clear()
    st.query_params["from"] = "opp"
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전 검사"
    try:
        sola_v2._auto_run_handoff_if_any()
        assert st.session_state.get("_do_ask_prefill") is True
        # 1회성 — 시그니처 기록 후 재호출 시 다시 set 하지 않음
        st.session_state.pop("_do_ask_prefill", None)
        sola_v2._auto_run_handoff_if_any()
        assert "_do_ask_prefill" not in st.session_state
    finally:
        st.query_params.clear()
        st.session_state.pop("_do_ask_prefill", None)
        st.session_state.pop("_handoff_autorun_done", None)


def test_auto_run_handoff_skips_when_prefill_empty():
    """컨텍스트 없는 인계(dept/lv3 없음)는 자동 전송하지 않음."""
    import streamlit as st
    st.query_params.clear()
    st.query_params["from"] = "opp"  # dept/lv3 없음 → prefill 빈 문자열
    try:
        sola_v2._auto_run_handoff_if_any()
        assert "_do_ask_prefill" not in st.session_state
    finally:
        st.query_params.clear()
        st.session_state.pop("_handoff_autorun_done", None)


def test_auto_run_handoff_ignores_non_handoff_query():
    """`?from` 없거나 미지원 종류면 아무것도 안 함."""
    import streamlit as st
    st.query_params.clear()
    try:
        sola_v2._auto_run_handoff_if_any()
        assert "_do_ask_prefill" not in st.session_state
    finally:
        st.query_params.clear()
        st.session_state.pop("_handoff_autorun_done", None)


def test_sola_action_pending_flag_takes_priority_over_query():
    """버튼 칩 경로 — `_sola_action_pending` 이 쿼리보다 먼저 소비돼 flag 로 매핑."""
    import streamlit as st
    from ui import sola_workshop_v2 as sola_v2
    st.session_state["_sola_action_pending"] = {
        "action": "generate_proposal", "dept": "도장", "lv3": "비전 검사", "from": "opp"}
    try:
        sola_v2._consume_sola_action_from_query_if_any()
        payload = st.session_state.pop("_do_generate_proposal")
        assert payload == {"dept": "도장", "lv3": "비전 검사", "kind": "opp"}
        assert "_sola_action_pending" not in st.session_state
    finally:
        for k in ("_sola_action_pending", "_do_generate_proposal"):
            st.session_state.pop(k, None)
