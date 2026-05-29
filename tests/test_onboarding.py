"""페르소나 온보딩 마법사 — should_show 로직 + 단계 흐름 + dismiss/완료 영구화."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from persona.schema import Persona
from ui import onboarding


# ── should_show 분기 ─────────────────────────────────────────

def test_should_show_true_for_empty_persona_not_dismissed():
    with patch.object(onboarding.persona_store, "is_onboarding_dismissed", return_value=False):
        import streamlit as st
        st.session_state.pop("_onb_dismissed_session", None)
        assert onboarding.should_show(Persona()) is True


def test_should_show_false_for_configured_persona():
    p = Persona(dept="도장1팀", job="검사관")
    with patch.object(onboarding.persona_store, "is_onboarding_dismissed", return_value=False):
        assert onboarding.should_show(p) is False


def test_should_show_false_when_persisted_dismiss():
    with patch.object(onboarding.persona_store, "is_onboarding_dismissed", return_value=True):
        assert onboarding.should_show(Persona()) is False


def test_should_show_false_when_session_dismissed():
    import streamlit as st
    st.session_state["_onb_dismissed_session"] = True
    try:
        with patch.object(onboarding.persona_store, "is_onboarding_dismissed", return_value=False):
            assert onboarding.should_show(Persona()) is False
    finally:
        st.session_state.pop("_onb_dismissed_session", None)


# ── dismiss/clear 마커 영구화 (persona.store) ────────────────

def test_dismiss_marker_roundtrip(tmp_path, monkeypatch):
    import persona.store as ps
    monkeypatch.setattr(ps, "DATA_ROOT", tmp_path)
    assert ps.is_onboarding_dismissed() is False
    ps.dismiss_onboarding()
    assert ps.is_onboarding_dismissed() is True
    ps.clear_onboarding_dismiss()
    assert ps.is_onboarding_dismissed() is False


# ── 단계 진행 (AppTest, 실제 app.py 구동) ────────────────────

def _fresh_app():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["app_area"] = "📊 오늘의 보드"
    return at


def _click(at, kw: str) -> bool:
    for b in at.button:
        if kw in b.label:
            b.click()
            return True
    return False


@pytest.fixture
def clean_persona(tmp_path, monkeypatch):
    """격리된 페르소나 디렉토리 — 테스트가 실제 프로필을 건드리지 않도록."""
    import persona.store as ps
    monkeypatch.setattr(ps, "DATA_ROOT", tmp_path)
    yield ps


def test_wizard_welcome_then_full_completion_saves_persona(clean_persona):
    at = _fresh_app()
    at.run()
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "반갑습니다" in htmls          # welcome 노출
    assert not at.exception

    assert _click(at, "시작"); at.run()
    at.text_input(key="onb_name").set_value("홍길동"); at.run()
    assert _click(at, "다음"); at.run()
    at.text_input(key="onb_dept").set_value("도장1팀"); at.run()
    assert _click(at, "다음"); at.run()
    at.text_input(key="onb_job").set_value("품질 검사관"); at.run()
    assert _click(at, "다음"); at.run()
    assert _click(at, "완료"); at.run()

    saved = clean_persona.load()
    assert saved.name == "홍길동"
    assert saved.dept == "도장1팀"
    assert saved.job == "품질 검사관"
    assert saved.is_set()
    # 완료 후 마법사 사라지고 실제 화면 렌더
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "db-topbar" in htmls and "반갑습니다" not in htmls


def test_wizard_skip_persists_dismiss(clean_persona):
    at = _fresh_app()
    at.run()
    assert _click(at, "다음에 하기"); at.run()
    assert clean_persona.is_onboarding_dismissed() is True
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "db-topbar" in htmls and "반갑습니다" not in htmls


def test_wizard_back_navigation_preserves_input(clean_persona):
    at = _fresh_app()
    at.run()
    _click(at, "시작"); at.run()
    at.text_input(key="onb_name").set_value("김철수"); at.run()
    _click(at, "다음"); at.run()       # → step2
    _click(at, "이전"); at.run()       # ← step1
    assert at.text_input(key="onb_name").value == "김철수"


def test_persona_editor_open_suppresses_wizard(clean_persona):
    """명시적 프로필 편집 중에는 마법사가 끼어들지 않는다."""
    at = _fresh_app()
    at.session_state["show_persona_editor"] = True
    at.run()
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "반갑습니다" not in htmls   # welcome 미노출
    assert "사용자 프로필 설정" in htmls or "프로필" in htmls
