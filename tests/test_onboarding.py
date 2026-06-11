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
    """격리된 페르소나 디렉토리 — 테스트가 실제 프로필을 건드리지 않도록.

    완료 시 실행되는 SOLA 분석(persona.derive)은 실 LLM 호출 없이 폴백 경로를
    타도록 `_call_llm` 을 차단한다 (.env 에 키가 있어도 네트워크 미발생).
    """
    import persona.store as ps
    import persona.derive as pd_mod
    from sola.client import LLMNotConfigured

    monkeypatch.setattr(ps, "DATA_ROOT", tmp_path)

    def _no_llm(_text: str) -> str:
        raise LLMNotConfigured("test: llm blocked")

    monkeypatch.setattr(pd_mod, "_call_llm", _no_llm)
    yield ps


def test_wizard_welcome_then_full_completion_saves_persona(clean_persona):
    at = _fresh_app()
    at.run()
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "처음 오셨네요" in htmls       # welcome 모달 body 노출 ("반갑습니다"는 dialog 제목)
    assert "db-topbar" in htmls          # 배경 화면도 함께 렌더 (모달이 위에 뜸)
    assert not at.exception

    assert _click(at, "시작"); at.run()
    at.text_input(key="onb_name").set_value("홍길동"); at.run()
    assert _click(at, "다음"); at.run()
    at.text_input(key="onb_dept").set_value("도장1팀"); at.run()
    assert _click(at, "다음"); at.run()
    at.text_input(key="onb_job").set_value("품질 검사관"); at.run()
    assert _click(at, "다음"); at.run()
    at.multiselect(key="onb_keywords").set_value(["용접 로봇", "비전 검사"]); at.run()
    assert _click(at, "완료"); at.run()

    saved = clean_persona.load()
    assert saved.name == "홍길동"
    assert saved.dept == "도장1팀"
    assert saved.job == "품질 검사관"
    assert saved.is_set()
    # 관심 키워드 칩(multiselect accept_new_options) → 리스트로 저장
    assert saved.interest_keywords == ["용접 로봇", "비전 검사"]
    # 완료 시 SOLA 분석 실행 — LLM 차단 환경이라 규칙 폴백(입력 토큰 그대로)
    assert saved.derived_source == "fallback"
    assert "용접 로봇" in saved.derived_interests
    # 완료 후 → 수집 제안 단계 (모달 유지, "지금 바로 뉴스를 수집할까요?")
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "지금 바로 뉴스를 수집" in htmls
    # [나중에 하기] → 마법사 종료, 실제 화면만 렌더
    assert _click(at, "나중에 하기"); at.run()
    at.run()  # pending 연쇄 rerun 정착 (skip 테스트와 동일 사유)
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "db-topbar" in htmls and "처음 오셨네요" not in htmls
    assert "지금 바로 뉴스를 수집" not in htmls


def test_wizard_skip_persists_dismiss(clean_persona):
    at = _fresh_app()
    at.run()
    assert _click(at, "나중에 하기"); at.run()
    # dismiss 마커는 즉시 기록됨
    assert clean_persona.is_onboarding_dismissed() is True
    # AppTest 는 _handle_pending 연쇄 rerun 을 1 run 에 완전 정착 못 시킴
    # (실 브라우저는 즉시 정착) → 한 번 더 run 으로 should_show=False 반영
    at.run()
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "db-topbar" in htmls and "처음 오셨네요" not in htmls


def test_wizard_step1_has_later_button_but_step2_not(clean_persona):
    """단계 정돈 — [나중에 하기]는 환영 화면 + 1단계(이름)에만, 2단계부터는 이전/다음만."""
    at = _fresh_app()
    at.run()
    _click(at, "시작"); at.run()
    labels = [b.label for b in at.button]
    assert any("나중에 하기" in lbl for lbl in labels)  # 1단계 왼쪽 = 나중에 하기
    assert any("다음" in lbl for lbl in labels)          # 다음 → 버튼은 존재
    _click(at, "다음"); at.run()                          # → 2단계 (팀·부서)
    labels = [b.label for b in at.button]
    assert not any("나중에 하기" in lbl for lbl in labels)
    assert any("이전" in lbl for lbl in labels)


def test_wizard_step2_team_above_dept(clean_persona):
    """2단계 — 팀 입력이 부서보다 위(먼저) 렌더된다 (Enter/Tab 이동 순서 = DOM 순서)."""
    at = _fresh_app()
    at.run()
    _click(at, "시작"); at.run()
    _click(at, "다음"); at.run()  # → 2단계
    labels = [ti.label for ti in at.text_input]
    assert labels.index("팀") < labels.index("부서")


def test_wizard_collect_now_runs_and_closes(clean_persona, monkeypatch):
    """완료 → [📡 지금 수집 실행] → 수집 1회 실행 + 결과 요약 → [✓ 시작하기]로 종료."""
    import ui.data_management_v2 as dm

    calls = {"n": 0}

    def _fake_collect(progress=None):
        calls["n"] += 1
        return {
            "ok": True, "message": "✓ 테스트 수집 3건",
            "total_articles": 3, "total_files": 1, "n_keywords": 1,
            "used_default": False, "n_feeds": 0, "errors": [],
            "sources": [{"source": "naver", "count": 3, "ok": True}],
        }

    monkeypatch.setattr(dm, "_run_collect_for_modal", _fake_collect)

    at = _fresh_app()
    at.run()
    _click(at, "시작"); at.run()
    at.text_input(key="onb_name").set_value("홍길동"); at.run()
    _click(at, "다음"); at.run()
    at.text_input(key="onb_dept").set_value("도장1팀"); at.run()
    _click(at, "다음"); at.run()
    at.text_input(key="onb_job").set_value("검사관"); at.run()
    _click(at, "다음"); at.run()
    _click(at, "완료"); at.run()

    assert _click(at, "지금 수집 실행"); at.run()
    assert calls["n"] == 1  # 수집 1회 실행 (결과 세션 가드로 재수집 없음)
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "테스트 수집 3건" in htmls  # 결과 요약 노출

    assert _click(at, "시작하기"); at.run()
    at.run()  # pending 연쇄 rerun 정착
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "테스트 수집 3건" not in htmls and "처음 오셨네요" not in htmls
    assert not at.exception


def test_wizard_back_navigation_preserves_input(clean_persona):
    at = _fresh_app()
    at.run()
    _click(at, "시작"); at.run()
    at.text_input(key="onb_name").set_value("김철수"); at.run()
    _click(at, "다음"); at.run()       # → step2
    _click(at, "이전"); at.run()       # ← step1
    assert at.text_input(key="onb_name").value == "김철수"


def test_persona_editor_open_suppresses_wizard(clean_persona):
    """명시적 페르소나 편집 중에는 마법사가 끼어들지 않는다."""
    at = _fresh_app()
    at.session_state["show_persona_editor"] = True
    at.run()
    htmls = "\n".join(h.proto.body for h in at.get("html"))
    assert "처음 오셨네요" not in htmls   # welcome 모달 미노출
    assert "페르소나 설정" in htmls or "페르소나" in htmls
