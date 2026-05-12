"""제안서 refine 모듈 단위 테스트 (LLM 모킹)."""
from __future__ import annotations

from unittest.mock import patch

from persona.schema import Persona
from sola import refine


def test_refine_passes_current_md_and_instruction_to_chat():
    captured: dict = {}

    def _fake_chat(messages, **kw):
        captured["messages"] = messages
        captured["kw"] = kw
        return "## 1. 작업 개요\n- 강재선별 자동화 (수정됨)"

    current_md = "## 1. 작업 개요\n- 강재선별"
    instruction = "리스크 섹션을 추가해줘"

    with patch.object(refine, "chat", _fake_chat):
        out = refine.refine_proposal(current_md, instruction)

    assert "수정됨" in out
    user_msg = captured["messages"][-1]["content"]
    assert "현재 제안서" in user_msg
    assert "강재선별" in user_msg
    assert "수정 지시" in user_msg
    assert "리스크 섹션을 추가" in user_msg


def test_refine_injects_persona_into_system_prompt():
    captured: dict = {}

    def _fake_chat(messages, **kw):
        captured["messages"] = messages
        return "## 1. 작업 개요"

    persona = Persona(dept="가공부", job="용접 R&D 3년차")
    with patch.object(refine, "chat", _fake_chat):
        refine.refine_proposal("## 1. 개요", "더 짧게", persona=persona)

    system_msg = captured["messages"][0]["content"]
    assert "사용자 페르소나" in system_msg
    assert "용접 R&D 3년차" in system_msg


def test_refine_persona_none_omits_persona_block():
    captured: dict = {}

    def _fake_chat(messages, **kw):
        captured["messages"] = messages
        return "## 1. 작업 개요"

    with patch.object(refine, "chat", _fake_chat):
        refine.refine_proposal("## 1. 개요", "더 짧게")

    system_msg = captured["messages"][0]["content"]
    assert "사용자 페르소나" not in system_msg


def test_refine_default_temperature_is_low():
    captured: dict = {}

    def _fake_chat(messages, **kw):
        captured["kw"] = kw
        return ""

    with patch.object(refine, "chat", _fake_chat):
        refine.refine_proposal("md", "instr")

    # 제안서 수정은 deterministic 에 가까워야 함 (낮은 temperature).
    assert captured["kw"]["temperature"] <= 0.4
