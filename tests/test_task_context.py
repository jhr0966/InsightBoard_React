"""sola.task_context — 페르소나 관심 작업정의 선별·주입 단위 테스트.

핵심: 전체 작업정의를 다 넣지 않고 페르소나 matched_processes 로 좁혀서, 해당
작업정의만 to_chat_context_lines 로 포매팅·캡 주입하는지 검증.
"""
from __future__ import annotations

import json

from persona.schema import Persona


def _seed(process_id: str, *, process: str, task: str, extra: dict | None = None) -> None:
    from store import task_defs_db

    payload = {
        "version": "1.0",
        "org_meta": {"team": "C팀", "dept": "C1", "division": "7",
                     "process": process, "task": task, "sub_task": task},
        "process_id": process_id,
        "process_name": task,
        "process_description": f"{task} 공정 설명.",
        "work_flow": "1) 준비 2) 수행 3) 확인",
        "overall_quality_risks": [f"{task} 리스크"],
        "automation_potential_areas": [f"{task} AI 비전 검사"],
    }
    if extra:
        payload.update(extra)
    task_defs_db.upsert(process_id, json.dumps(payload, ensure_ascii=False))


# ── 선별 ────────────────────────────────────────────────

def test_relevant_processes_uses_matched_processes_first():
    from sola import task_context

    p = Persona(dept="C1", matched_processes=[
        {"process": "절단", "tasks": ["절단"], "score": 3.0},
        {"process": "가공", "tasks": ["가공"], "score": 2.0},
    ], interest_lv3=["도장"])
    # matched_processes 우선 — interest_lv3 는 폴백이라 무시
    assert task_context.relevant_processes(p, max_processes=2) == ["절단", "가공"]


def test_relevant_processes_falls_back_to_interest_lv3():
    from sola import task_context

    p = Persona(dept="C1", interest_lv3=["절단", "도장"])
    assert task_context.relevant_processes(p) == ["절단", "도장"]


def test_relevant_task_rows_pulls_only_matched(monkeypatch):
    from sola import task_context

    _seed("CUT-1", process="절단", task="절단")
    _seed("PNT-1", process="도장", task="도장")
    p = Persona(dept="C1", matched_processes=[{"process": "절단", "tasks": ["절단"], "score": 1.0}])
    rows = task_context.relevant_task_rows(p)
    pids = {r["process_id"] for r in rows}
    assert pids == {"CUT-1"}  # 도장은 관심 밖이라 제외


# ── 포맷 + 캡 ────────────────────────────────────────────

def test_persona_task_context_includes_structured_signals():
    from sola import task_context

    _seed("CUT-1", process="절단", task="절단")
    p = Persona(dept="C1", matched_processes=[{"process": "절단", "tasks": ["절단"], "score": 1.0}])
    text, labels = task_context.persona_task_context(p)
    assert "내 관심 공정 작업 정의" in text
    assert "작업 흐름" in text and "품질 리스크" in text  # to_chat_context_lines 신호
    assert "절단" in labels


def test_persona_task_context_empty_when_no_interest():
    from sola import task_context

    _seed("CUT-1", process="절단", task="절단")
    text, labels = task_context.persona_task_context(Persona(dept="C1"))
    assert text == "" and labels == []


def test_format_rows_respects_char_cap():
    from sola import task_context

    _seed("CUT-1", process="절단", task="절단")
    from store import task_defs_db
    rows = task_defs_db.list_all()
    text, _ = task_context.format_rows(rows, max_chars=80)
    assert len(text) <= 80 + 40  # 캡 + 생략 안내 꼬리
    assert "생략" in text


# ── 언급된 작업 ──────────────────────────────────────────

def test_mentioned_task_context_resolves_by_search():
    from sola import task_context

    _seed("CUT-1", process="절단", task="절단")
    _seed("PNT-1", process="도장", task="도장")
    text, labels = task_context.mentioned_task_context("절단 공정 자동화 어떻게?")
    assert "언급된 작업 정의" in text
    assert "절단" in labels


def test_mentioned_task_context_empty_query():
    from sola import task_context

    assert task_context.mentioned_task_context("") == ("", [])


# ── first_objective 폴백 (보드 카드 tagline) ──────────────

def test_first_objective_falls_back_to_description():
    from roadmap import task_def_json as tdj
    j = json.dumps({"process_description": "강재를 NC 자동 절단으로 도면 치수로 절단한다. 이후 사상.",
                    "objectives": []}, ensure_ascii=False)
    # objectives 비면 설명 첫 문장
    assert tdj.first_objective(j) == "강재를 NC 자동 절단으로 도면 치수로 절단한다"


def test_first_objective_prefers_objectives():
    from roadmap import task_def_json as tdj
    j = json.dumps({"process_description": "설명", "objectives": ["주판 검수"]}, ensure_ascii=False)
    assert tdj.first_objective(j) == "주판 검수"
