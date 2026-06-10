"""글로벌 SOLA 채팅 패널 — 안내 카드 / 추천 질문 / fragment 부분 rerun / 송신 처리."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from persona.schema import Persona
from sola.client import LLMNotConfigured
from ui import chat_panel


# ── intro 카드 + 추천 질문 ───────────────────────────────────

def test_intro_card_includes_area_headline():
    out = chat_panel._intro_card_html("📊 오늘의 보드")
    assert "📊 오늘의 보드" in out
    # 추천 질문은 더 이상 전체 리로드 앵커가 아니라 입력창 위 st.pills(fragment)로
    # 노출 → intro 카드 HTML 에는 칩 앵커가 들어가지 않는다.
    assert "side-chat-chip" not in out
    assert "?sola_prefill=" not in out
    # 추천 질문 목록 자체는 _suggestions_for 가 제공한다(= pills 옵션).
    assert chat_panel._suggestions_for("📊 오늘의 보드") == \
        chat_panel._AREA_INTROS["📊 오늘의 보드"]["suggestions"]


def test_intro_card_falls_back_to_default_for_unknown_area():
    out = chat_panel._intro_card_html("알 수 없는 area")
    # 기본 fallback = 보드
    assert "📊 오늘의 보드" in out


def test_intro_card_escapes_html_in_area_key():
    """XSS — area_key 가 escape 되어야."""
    out = chat_panel._intro_card_html("<script>alert(1)</script>")
    assert "<script>" not in out
    # 기본 폴백으로 보드 노출
    assert "오늘의 보드" in out


def test_all_areas_have_intros():
    """6 area + 페르소나 페이지 = 7 종 intro 정의."""
    expected = {"📊 오늘의 보드", "🗞 뉴스 수집", "📋 작업 정의", "🔎 인사이트 분석",
                "🤖 SOLA 작업실", "📦 산출물 보관함", "프로필 설정"}
    assert set(chat_panel._AREA_INTROS.keys()) == expected


def test_each_intro_has_headline_and_at_least_3_suggestions():
    for area, intro in chat_panel._AREA_INTROS.items():
        assert intro["headline"], f"{area}: headline 없음"
        assert isinstance(intro["suggestions"], list), f"{area}: suggestions 리스트 아님"
        assert len(intro["suggestions"]) >= 3, f"{area}: 추천 질문 3건 미만"


# ── 빠른 작업(quick-action) — SOLA 작업실 채팅 통합 ────────────

def test_quick_actions_only_for_sola_workshop():
    """SOLA 작업실 area 에만 빠른 작업 버튼 칩 3개, 나머지는 미렌더(소켓 rerun 전환)."""
    import streamlit as st
    from unittest.mock import MagicMock, patch
    st.query_params.clear()
    try:
        labels: list[str] = []
        cols = (MagicMock(), MagicMock(), MagicMock())
        with patch("streamlit.container", MagicMock()), \
             patch("streamlit.html"), \
             patch("streamlit.columns", return_value=cols), \
             patch("streamlit.button", side_effect=lambda label, **kw: labels.append(label) or False):
            chat_panel._render_quick_action_chips("🤖 SOLA 작업실")
        assert labels == [l for l, _a in chat_panel._SOLA_QUICK_ACTIONS]

        # 다른 area 는 아무 위젯도 안 그린다
        with patch("streamlit.button") as btn, patch("streamlit.container") as cont:
            for other in ("📊 오늘의 보드", "🔎 인사이트 분석", "📦 산출물 보관함"):
                chat_panel._render_quick_action_chips(other)
        btn.assert_not_called()
        cont.assert_not_called()
    finally:
        st.query_params.clear()


def test_quick_action_click_sets_pending_with_handoff_context():
    """칩 클릭 → `_sola_action_pending` 에 action + 인계 컨텍스트(dept/lv3/from) 보존.

    소비자(`sola_workshop_v2.render`)는 중앙 컬럼 = 채팅 fragment **바깥**이므로
    클릭은 반드시 전체 rerun(scope="app")으로 승격되어야 한다.
    """
    import streamlit as st
    st.query_params.clear()
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전 검사"
    st.query_params["from"] = "opp"
    try:
        cols = (MagicMock(), MagicMock(), MagicMock())
        # 첫 버튼(제안서 생성)만 클릭된 것으로
        presses = iter([True, False, False])
        with patch("streamlit.container", MagicMock()), \
             patch("streamlit.html"), \
             patch("streamlit.columns", return_value=cols), \
             patch("streamlit.button", side_effect=lambda *a, **kw: next(presses)), \
             patch("streamlit.rerun") as rr:
            chat_panel._render_quick_action_chips("🤖 SOLA 작업실")
        pend = st.session_state.pop("_sola_action_pending")
        assert pend["action"] == "generate_proposal"
        assert pend["dept"] == "도장" and pend["lv3"] == "비전 검사" and pend["from"] == "opp"
        rr.assert_called_once_with(scope="app")
    finally:
        st.query_params.clear()
        st.session_state.pop("_sola_action_pending", None)


# ── 메시지 렌더 ─────────────────────────────────────────────

def test_format_recent_messages_empty_returns_empty():
    assert chat_panel._format_recent_messages([]) == ""


def test_format_recent_messages_caps_at_n_recent():
    msgs = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    out = chat_panel._format_recent_messages(msgs, cap=3)
    assert "q9" in out
    assert "q8" in out
    assert "q7" in out
    assert "q6" not in out


def test_format_recent_messages_escapes_html():
    msgs = [{"role": "user", "content": "<script>alert(1)</script>"}]
    out = chat_panel._format_recent_messages(msgs)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_format_recent_messages_role_styling():
    msgs = [
        {"role": "user", "content": "Q"},
        {"role": "assistant", "content": "A"},
    ]
    out = chat_panel._format_recent_messages(msgs)
    assert "🤖 SOLA" in out  # assistant prefix
    # user 메시지는 SOLA 라벨 없음
    user_part = out[:out.index("🤖 SOLA")]
    assert "Q" in user_part


# ── 추천 질문은 pills(fragment) — 전체 리로드 앵커 아님 ─────

def test_suggestions_no_longer_full_reload_anchors():
    """추천 질문이 전체 리로드 앵커(?sola_prefill=)가 아니라 pills 옵션으로 제공된다."""
    out = chat_panel._intro_card_html("📊 오늘의 보드")
    assert 'href="?sola_prefill=' not in out  # 전체 리로드 앵커 제거됨
    suggestions = chat_panel._suggestions_for("📊 오늘의 보드")
    assert len(suggestions) >= 3
    assert all(isinstance(s, str) and s for s in suggestions)


def test_apply_pending_prefill_fills_input_and_pops_pending():
    """pill 클릭 pending → 입력창 키에 주입 + pending 제거(재적용 방지)."""
    from types import SimpleNamespace

    ik = "_side_chat_input_board"
    fake = SimpleNamespace(session_state={f"{ik}__prefill": "트렌드 요약해줘"})
    with patch.object(chat_panel, "st", fake):
        assert chat_panel._apply_pending_prefill(ik) is True
    assert fake.session_state[ik] == "트렌드 요약해줘"
    assert f"{ik}__prefill" not in fake.session_state


def test_apply_pending_prefill_noop_when_no_pending():
    from types import SimpleNamespace

    ik = "_side_chat_input_board"
    fake = SimpleNamespace(session_state={})
    with patch.object(chat_panel, "st", fake):
        assert chat_panel._apply_pending_prefill(ik) is False
    assert fake.session_state == {}


def test_consume_prefill_sets_input_value_and_clears_param():
    from types import SimpleNamespace

    fake = SimpleNamespace(query_params={"sola_prefill": "오늘 KPI 요약"}, session_state={})
    with patch.object(chat_panel, "st", fake):
        chat_panel._consume_prefill("_side_chat_input_board")
    assert fake.session_state["_side_chat_input_board"] == "오늘 KPI 요약"
    assert "sola_prefill" not in fake.query_params  # 소비 후 제거 (재적용 방지)


def test_consume_prefill_noop_when_no_param():
    from types import SimpleNamespace

    fake = SimpleNamespace(query_params={}, session_state={})
    with patch.object(chat_panel, "st", fake):
        chat_panel._consume_prefill("_side_chat_input_board")
    assert fake.session_state == {}


# ── fragment 구조 — render_side 래퍼 + @st.fragment 본체 ─────

def test_render_side_is_thin_wrapper_over_fragment():
    """render_side(공개 시그니처) → `_render_side_fragment`(@st.fragment) 위임.

    st.fragment 데코는 functools.wraps 로 원함수를 감싼다 → __wrapped__ 존재.
    """
    assert chat_panel.render_side is not chat_panel._render_side_fragment
    assert chat_panel._render_side_fragment.__name__ == "_render_side_fragment"
    assert hasattr(chat_panel._render_side_fragment, "__wrapped__")


def test_render_side_delegates_to_fragment():
    persona = Persona(name="홍길동")
    with patch.object(chat_panel, "_render_side_fragment") as frag:
        chat_panel.render_side(persona, "📊 오늘의 보드")
    frag.assert_called_once_with(persona, "📊 오늘의 보드")


def test_fragment_body_consumes_send_before_rendering_messages():
    """fragment 본체 최상단에서 consume(scope="fragment") → 그 다음 메시지 로드.

    순서가 뒤집히면 보낸 메시지가 같은 fragment rerun 에 보이지 않는다.
    """
    import streamlit as st
    st.query_params.clear()
    order: list[str] = []
    seen: dict = {}

    def _fake_consume(persona, scope=None):
        order.append("consume")
        seen["persona"], seen["scope"] = persona, scope

    inner = chat_panel._render_side_fragment.__wrapped__
    persona = Persona(name="홍길동")
    try:
        with patch.object(chat_panel, "consume_send_if_any", side_effect=_fake_consume), \
             patch("ui.sola_workshop_v2._load_messages",
                   side_effect=lambda: order.append("load") or []), \
             patch("streamlit.html"), \
             patch("streamlit.container", MagicMock()), \
             patch("streamlit.pills", return_value=None), \
             patch("streamlit.form", MagicMock()), \
             patch("streamlit.text_area", return_value=""), \
             patch("streamlit.form_submit_button", return_value=False):
            inner(persona, "📊 오늘의 보드")
    finally:
        st.query_params.clear()
    assert order and order[0] == "consume"   # 소비가 메시지 로드/렌더보다 먼저
    assert "load" in order
    assert seen["persona"] is persona
    assert seen["scope"] == "fragment"


# ── rerun scope — 패널 내부 상호작용별 부분/전체 rerun 라우팅 ──

def test_suggestion_pill_click_sets_prefill_and_fragment_rerun():
    """추천 질문 pill 클릭 → __prefill pending + fragment 부분 rerun 만."""
    import streamlit as st
    ik = "_side_chat_input_testarea"
    try:
        with patch("streamlit.container", MagicMock()), \
             patch("streamlit.pills", return_value="오늘 KPI 요약"), \
             patch("streamlit.rerun") as rr:
            chat_panel._render_chat_suggestions("📊 오늘의 보드", ik)
        assert st.session_state[f"{ik}__prefill"] == "오늘 KPI 요약"
        assert st.session_state[f"{ik}__reset_pills"] is True
        rr.assert_called_once_with(scope="fragment")
    finally:
        for k in (f"{ik}__prefill", f"{ik}__reset_pills"):
            st.session_state.pop(k, None)


def test_chat_input_send_uses_fragment_scope_for_regular_areas():
    """일반 area 의 보내기 → `_do_sola_send` pending + fragment 부분 rerun."""
    import streamlit as st
    try:
        with patch("streamlit.container", MagicMock()), \
             patch("streamlit.form", MagicMock()), \
             patch("streamlit.text_area", return_value="  질문입니다  "), \
             patch("streamlit.form_submit_button", return_value=True), \
             patch("streamlit.rerun") as rr:
            chat_panel._render_chat_input("_k", "board", "📊 오늘의 보드")
        assert st.session_state["_do_sola_send"] == "질문입니다"
        rr.assert_called_once_with(scope="fragment")
    finally:
        st.session_state.pop("_do_sola_send", None)


def test_chat_input_send_uses_app_scope_for_sola_workshop():
    """SOLA 작업실의 보내기 → 전체 rerun(scope="app").

    중앙 작업대 캔버스('현재 산출물' = 마지막 assistant 메시지)가 같은 런에서
    답변을 반영해야 하므로 app.py 최상단 consume 경로(풀런)를 태운다.
    """
    import streamlit as st
    try:
        with patch("streamlit.container", MagicMock()), \
             patch("streamlit.form", MagicMock()), \
             patch("streamlit.text_area", return_value="제안서 도와줘"), \
             patch("streamlit.form_submit_button", return_value=True), \
             patch("streamlit.rerun") as rr:
            chat_panel._render_chat_input("_k", "sola", "🤖 SOLA 작업실")
        assert st.session_state["_do_sola_send"] == "제안서 도와줘"
        rr.assert_called_once_with(scope="app")
    finally:
        st.session_state.pop("_do_sola_send", None)


# ── consume_send_if_any — pending → LLM → append → scope rerun ──

def _consume_patches(chat=None, chat_side_effect=None):
    """sw 빌딩블록 + LLM + rerun 패치 묶음 (appended 기록 리스트 반환)."""
    appended: list[tuple[str, str]] = []
    kwargs = {"return_value": chat} if chat_side_effect is None else {"side_effect": chat_side_effect}
    return appended, (
        patch("ui.sola_workshop_v2._append_message",
              side_effect=lambda r, c: appended.append((r, c))),
        patch("ui.sola_workshop_v2._load_messages",
              return_value=[{"role": "user", "content": "질문"}]),
        patch("ui.sola_workshop_v2._build_llm_messages",
              return_value=[{"role": "system", "content": "s"}]),
        patch("sola.client.chat", **kwargs),
        patch("streamlit.rerun"),
    )


def test_consume_send_appends_user_and_assistant_with_fragment_scope():
    import streamlit as st
    st.session_state["_do_sola_send"] = "질문"
    appended, (p_app, p_load, p_build, p_chat, p_rerun) = _consume_patches(chat="답변")
    with p_app, p_load, p_build, p_chat as mock_chat, p_rerun as rr:
        chat_panel.consume_send_if_any(Persona(name="홍길동"), scope="fragment")
    assert appended == [("user", "질문"), ("assistant", "답변")]
    mock_chat.assert_called_once()
    rr.assert_called_once_with(scope="fragment")
    assert "_do_sola_send" not in st.session_state   # pending 소비됨


def test_consume_send_default_scope_is_app():
    """app.py 최상단(풀런 경로) 호출은 기본 scope="app" — 전체 rerun."""
    import streamlit as st
    st.session_state["_do_sola_send"] = "질문"
    _appended, (p_app, p_load, p_build, p_chat, p_rerun) = _consume_patches(chat="답변")
    with p_app, p_load, p_build, p_chat, p_rerun as rr:
        chat_panel.consume_send_if_any(Persona())
    rr.assert_called_once_with(scope="app")


def test_consume_send_llm_not_configured_falls_back_to_preview():
    import streamlit as st
    st.session_state["_do_sola_send"] = "Q"
    appended, (p_app, p_load, p_build, p_chat, p_rerun) = _consume_patches(
        chat_side_effect=LLMNotConfigured("no key"))
    with p_app, p_load, p_build, p_chat, p_rerun as rr:
        chat_panel.consume_send_if_any(Persona(), scope="fragment")
    assert appended[0] == ("user", "Q")
    assert appended[1][0] == "assistant"
    assert "LLM 미설정" in appended[1][1]
    rr.assert_called_once_with(scope="fragment")   # 폴백이어도 rerun 은 동일 scope


def test_consume_send_error_becomes_assistant_message():
    import streamlit as st
    st.session_state["_do_sola_send"] = "Q"
    appended, (p_app, p_load, p_build, p_chat, p_rerun) = _consume_patches(
        chat_side_effect=RuntimeError("network"))
    with p_app, p_load, p_build, p_chat, p_rerun as rr:
        chat_panel.consume_send_if_any(Persona(), scope="fragment")
    assert appended[-1][0] == "assistant"
    assert "응답 생성 실패" in appended[-1][1] and "RuntimeError" in appended[-1][1]
    rr.assert_called_once_with(scope="fragment")


@pytest.mark.parametrize("payload", [None, "", "   "])
def test_consume_send_noop_without_meaningful_pending(payload):
    import streamlit as st
    if payload is None:
        st.session_state.pop("_do_sola_send", None)
    else:
        st.session_state["_do_sola_send"] = payload
    try:
        with patch("sola.client.chat") as cli, patch("streamlit.rerun") as rr:
            chat_panel.consume_send_if_any(Persona(), scope="fragment")
        cli.assert_not_called()
        rr.assert_not_called()   # noop 이면 rerun 루프 금지
    finally:
        st.session_state.pop("_do_sola_send", None)


@pytest.fixture
def _clean_sola_session():
    """활성 thread/메시지 캐시 + 화면 컨텍스트 세션 키 정리 (full-stack 테스트용)."""
    import streamlit as st

    def _clean():
        for k in [k for k in list(st.session_state.keys())
                  if k.startswith("_sola_messages") or k == "_sola_thread_id"]:
            st.session_state.pop(k, None)
        st.session_state.pop("_chat_context_for_sola", None)
        st.session_state.pop("_do_sola_send", None)

    _clean()
    yield
    _clean()


def test_consume_send_full_stack_reads_screen_context_from_session(_clean_sola_session):
    """fragment rerun 에서도 직전 풀런이 세션에 저장한 `_chat_context_for_sola` 가
    LLM system 메시지에 첨부된다 (sw._build_llm_messages 가 session_state 참조).

    sw 빌딩블록을 실제로 태워 thread 생성·메시지 영구화 round-trip 까지 검증.
    """
    import streamlit as st
    st.session_state["_chat_context_for_sola"] = (
        "--- 현재 화면: 오늘의 보드 ---\n오늘 KPI: 수집 125건"
    )
    st.session_state["_do_sola_send"] = "이 화면 요약해줘"
    captured: dict = {}

    def _fake_chat(messages):
        captured["messages"] = messages
        return "요약 답변"

    with patch("sola.client.chat", side_effect=_fake_chat), \
         patch("sola.thread_title.generate", return_value="화면 요약"), \
         patch("streamlit.rerun") as rr:
        chat_panel.consume_send_if_any(Persona(name="홍길동", dept="도장1팀"),
                                       scope="fragment")

    sys_msg = captured["messages"][0]
    assert sys_msg["role"] == "system"
    assert "오늘의 보드" in sys_msg["content"]   # 화면 컨텍스트 (세션 경유)
    assert "도장1팀" in sys_msg["content"]       # 페르소나 블록
    tid = st.session_state["_sola_thread_id"]
    msgs = st.session_state[f"_sola_messages_{tid}"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "이 화면 요약해줘"
    assert msgs[1]["content"] == "요약 답변"
    rr.assert_called_once_with(scope="fragment")


# ── AppTest — 풀런 소비 경로 + 각 화면 패널 sanity ───────────

def _seed_persona_for_apptest() -> None:
    from persona import store as ps
    ps.save(Persona(name="홍길동", team="자동화1팀", dept="도장1팀"))
    ps.dismiss_onboarding()


def test_apptest_pending_send_consumed_at_app_top():
    """풀런으로 도착한 send 는 app.py 최상단 consume 가 처리(작업실 경로와 동일).

    fragment 전환 후에도 풀런 경로가 살아 있어야 작업실 캔버스·인계 자동 전송이
    동작한다 — 응답 append + thread 영구화까지 한 번에 검증.
    """
    _seed_persona_for_apptest()
    from streamlit.testing.v1 import AppTest
    with patch("sola.client.chat", return_value="모킹 답변"), \
         patch("sola.thread_title.generate", return_value="질문 정리"):
        at = AppTest.from_file("app.py", default_timeout=120)
        at.session_state["app_area"] = "📦 산출물 보관함"
        at.session_state["_do_sola_send"] = "테스트 질문"
        at.run()
    assert not at.exception, f"렌더 예외: {at.exception}"
    tid = at.session_state["_sola_thread_id"]
    msgs = at.session_state[f"_sola_messages_{tid}"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]   # 1회만 처리됨
    assert msgs[0]["content"] == "테스트 질문"
    assert msgs[1]["content"] == "모킹 답변"


@pytest.mark.parametrize("area", ["📊 오늘의 보드", "🗞 뉴스 수집", "🤖 SOLA 작업실"])
def test_apptest_chat_panel_renders_on_each_area(area):
    """fragment 전환 후에도 각 화면에서 우측 채팅 패널이 예외 없이 렌더."""
    _seed_persona_for_apptest()
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["app_area"] = area
    at.run()
    assert not at.exception, f"{area} 렌더 예외: {at.exception}"
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "side-chat-marker" in combined   # 우측 채팅 패널이 fragment 안에서 마운트됨
