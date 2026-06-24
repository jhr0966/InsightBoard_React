"""api.routers.assistant — SSE 챗 스트리밍 (provider seam 경유)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from sola.providers.base import LLMNotConfigured

client = TestClient(app)


def test_chat_streams_sse_frames():
    def _fake_stream(messages, **kw):
        assert messages[0]["content"] == "안녕"
        yield "반"
        yield "가워"

    with patch("sola.client.chat_stream", _fake_stream):
        with client.stream(
            "POST", "/api/assistant/chat",
            json={"messages": [{"role": "user", "content": "안녕"}]},
        ) as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]
            text = "".join(r.iter_text())
    assert 'data: {"delta": "반"}' in text
    assert 'data: {"delta": "가워"}' in text
    assert 'data: {"done": true}' in text


def test_chat_emits_error_frame_when_not_configured():
    def _raise(messages, **kw):
        raise LLMNotConfigured("no key")
        yield  # pragma: no cover

    with patch("sola.client.chat_stream", _raise):
        with client.stream(
            "POST", "/api/assistant/chat",
            json={"messages": [{"role": "user", "content": "x"}]},
        ) as r:
            text = "".join(r.iter_text())
    assert '"error"' in text and "no key" in text


def test_status_endpoint():
    with patch("sola.client.is_configured", lambda: False):
        r = client.get("/api/assistant/status")
    assert r.status_code == 200
    assert r.json()["configured"] is False
    assert "provider" in r.json()


# ── /context — 화면 다이제스트 + 페르소나 관심 작업정의 + 언급 작업 주입 ──

def _seed_taskdef(process_id, *, process, task):
    import json as _json
    from store import task_defs_db
    payload = {
        "version": "1.0",
        "org_meta": {"team": "C팀", "dept": "C1", "process": process, "task": task},
        "process_id": process_id, "process_name": task,
        "process_description": f"{task} 공정.", "work_flow": "1) 준비 2) 수행",
        "overall_quality_risks": [f"{task} 리스크"],
        "automation_potential_areas": [f"{task} AI 비전"],
    }
    task_defs_db.upsert(process_id, _json.dumps(payload, ensure_ascii=False))


def test_context_returns_labels_and_digest():
    r = client.get("/api/assistant/context", params={"screen": "board"})
    assert r.status_code == 200
    body = r.json()
    assert body["screen"] == "board"
    assert "현재 화면: board" in body["context"]
    assert "현재 화면" in body["labels"]


def test_context_injects_persona_relevant_taskdef():
    from persona import store as persona_store
    from persona.schema import Persona
    _seed_taskdef("CUT-1", process="절단", task="절단")
    persona_store.save(Persona(dept="C1", matched_processes=[
        {"process": "절단", "tasks": ["절단"], "score": 1.0}]))
    r = client.get("/api/assistant/context", params={"screen": "board"})
    body = r.json()
    assert "내 관심 공정 작업 정의" in body["context"]
    assert any("관심 작업정의" in l for l in body["labels"])


def test_context_injects_mentioned_task_from_query():
    _seed_taskdef("CUT-1", process="절단", task="절단")
    _seed_taskdef("PNT-1", process="도장", task="도장")
    r = client.get("/api/assistant/context",
                   params={"screen": "board", "query": "절단 공정 자동화 어떻게?"})
    body = r.json()
    assert "언급된 작업 정의" in body["context"]
    assert any("언급 작업" in l for l in body["labels"])
