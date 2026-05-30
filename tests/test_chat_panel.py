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


# ── consume_send_if_any 위임 ────────────────────────────────

def test_consume_send_delegates_to_sola_workshop():
    """chat_panel.consume_send_if_any 가 sw._consume_send_if_any 호출."""
    persona = Persona(name="홍길동")
    with patch("ui.sola_workshop_v2._consume_send_if_any") as mock_consume:
        chat_panel.consume_send_if_any(persona)
        mock_consume.assert_called_once_with(persona)


# ── render — SOLA workshop 에선 미렌더 ───────────────────────

def test_render_returns_early_for_sola_workshop_area():
    """SOLA workshop area 는 자체 풀스크린 채팅이 있으므로 글로벌 패널 미렌더."""
    persona = Persona()
    with patch("streamlit.divider") as mock_div, \
         patch("streamlit.markdown"), \
         patch("streamlit.chat_input"):
        chat_panel.render(persona, area_key="🤖 SOLA 작업실")
    mock_div.assert_not_called()
