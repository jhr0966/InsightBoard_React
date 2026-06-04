"""글로벌 SOLA 채팅 패널 — 안내 카드 / 추천 질문 / 송신 위임."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from persona.schema import Persona
from ui import chat_panel


# ── intro 카드 + 추천 질문 ───────────────────────────────────

def test_intro_card_includes_area_headline_and_chips():
    out = chat_panel._intro_card_html("📊 오늘의 보드")
    assert "📊 오늘의 보드" in out
    # 5 개 추천 질문 모두 chip 으로 노출
    suggestions = chat_panel._AREA_INTROS["📊 오늘의 보드"]["suggestions"]
    for s in suggestions:
        assert s in out


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
    """5 area + 페르소나 페이지 = 6 종 intro 정의."""
    expected = {"📊 오늘의 보드", "🧱 데이터 관리", "🔎 인사이트 분석",
                "🤖 SOLA 작업실", "📦 산출물 보관함", "프로필 설정"}
    assert set(chat_panel._AREA_INTROS.keys()) == expected


def test_each_intro_has_headline_and_at_least_3_suggestions():
    for area, intro in chat_panel._AREA_INTROS.items():
        assert intro["headline"], f"{area}: headline 없음"
        assert isinstance(intro["suggestions"], list), f"{area}: suggestions 리스트 아님"
        assert len(intro["suggestions"]) >= 3, f"{area}: 추천 질문 3건 미만"


# ── 빠른 작업(quick-action) — SOLA 작업실 채팅 통합 ────────────

def test_quick_actions_only_for_sola_workshop():
    """SOLA 작업실 area 에만 quick-action 칩, 나머지는 빈 문자열."""
    import streamlit as st
    st.query_params.clear()
    try:
        out = chat_panel._quick_actions_html("🤖 SOLA 작업실")
        assert "빠른 작업" in out
        # 3 액션 모두 노출 + sola_action 링크
        for _label, action in chat_panel._SOLA_QUICK_ACTIONS:
            assert f"sola_action={action}" in out
        # 다른 area 는 칩 미노출
        for other in ("📊 오늘의 보드", "🔎 인사이트 분석", "📦 산출물 보관함"):
            assert chat_panel._quick_actions_html(other) == ""
    finally:
        st.query_params.clear()


def test_quick_actions_preserve_handoff_context():
    """제안서 생성 링크가 인계 컨텍스트(dept/lv3/from)를 보존."""
    import streamlit as st
    st.query_params.clear()
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전 검사"
    st.query_params["from"] = "opp"
    try:
        out = chat_panel._quick_actions_html("🤖 SOLA 작업실")
        # urlencode 라 한글은 percent-encoding — 키 존재로 검증
        assert "dept=" in out and "lv3=" in out and "from=opp" in out
        assert "sola_action=generate_proposal" in out
    finally:
        st.query_params.clear()


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


# ── 추천 질문 chip 은 클릭 링크(?sola_prefill=) ─────────────

def test_intro_card_chips_are_prefill_links():
    """추천 질문이 정적 span 이 아니라 ?sola_prefill= 링크여야 클릭 시 입력창에 채워진다."""
    out = chat_panel._intro_card_html("📊 오늘의 보드")
    assert "side-chat-chip" in out
    assert "?sola_prefill=" in out
    # 질문 텍스트가 href 로 인코딩돼 들어간다 (예: 공백 → %20)
    assert "href=\"?sola_prefill=" in out


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


# ── consume_send_if_any 위임 ────────────────────────────────

def test_consume_send_delegates_to_sola_workshop():
    """chat_panel.consume_send_if_any 가 sw._consume_send_if_any 호출."""
    persona = Persona(name="홍길동")
    with patch("ui.sola_workshop_v2._consume_send_if_any") as mock_consume:
        chat_panel.consume_send_if_any(persona)
        mock_consume.assert_called_once_with(persona)
