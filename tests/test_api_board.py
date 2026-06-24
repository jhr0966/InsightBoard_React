"""api.routers.board — 보드 LLM 다이제스트(룰 폴백 포함)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from store import news_db

client = TestClient(app)


def test_brief_empty_when_no_news():
    r = client.get("/api/board/brief")
    assert r.status_code == 200
    body = r.json()
    assert body["item_count"] == 0
    assert isinstance(body["brief"], str) and body["brief"]  # 룰 폴백 문자열
    assert "persona_label" in body


def test_brief_uses_news_rule_fallback(monkeypatch):
    # LLM 미설정 → board_brief 가 룰 기반 폴백을 반환(키 불필요).
    news_db.save_articles(
        [{"title": "조선소 용접 자동화 로봇", "link": "l1", "source": "naver",
          "summary": "현장 적용 사례", "date": "2026-06-15"}],
        source="naver",
    )
    monkeypatch.setattr("sola.board_brief.is_configured", lambda: False, raising=False)
    r = client.get("/api/board/brief", params={"days": 1})
    assert r.status_code == 200
    assert r.json()["item_count"] == 1


# ── 작업정의 컨텍스트 주입 (Phase C) ──────────────────────

def test_brief_injects_persona_taskdef_into_llm_payload(monkeypatch):
    """페르소나 관심 공정 작업정의가 board_brief LLM user 페이로드에 들어가는지."""
    import json as _json
    from persona import store as persona_store
    from persona.schema import Persona
    from store import task_defs_db

    task_defs_db.upsert("CUT-1", _json.dumps({
        "version": "1.0",
        "org_meta": {"team": "C팀", "dept": "C1", "process": "절단", "task": "절단"},
        "process_id": "CUT-1", "process_name": "절단",
        "process_description": "강재 절단.", "work_flow": "1) NC 절단",
        "overall_quality_risks": ["치수 불량"],
        "automation_potential_areas": ["절단면 AI 비전"],
    }, ensure_ascii=False))
    persona_store.save(Persona(dept="C1", matched_processes=[
        {"process": "절단", "tasks": ["절단"], "score": 1.0}]))
    news_db.save_articles(
        [{"title": "AI 비전 검사 신기술", "link": "lz", "source": "naver",
          "summary": "검사 자동화", "date": "2026-06-20"}], source="naver")

    captured = {}

    def _fake_chat(*, messages, **kw):
        captured["user"] = messages[-1]["content"]
        return "헤드라인\n- 불릿1"

    monkeypatch.setattr("sola.board_brief.chat", _fake_chat, raising=True)
    r = client.get("/api/board/brief", params={"days": 7, "force": True})
    assert r.status_code == 200
    # 절단 작업정의 신호가 LLM 입력에 주입됨
    assert "내 관심 공정 작업 정의" in captured.get("user", "")
    assert "절단면 AI 비전" in captured["user"]
