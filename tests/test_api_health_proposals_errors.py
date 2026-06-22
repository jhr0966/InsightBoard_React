"""LLM 의존 엔드포인트의 그레이스풀 에러 처리 + 진단 헬스체크.

제안서/요약은 룰 폴백이 없어 LLM 미설정·호출 실패가 그대로 500 으로 노출됐다.
이제 미설정=503, 그 외 LLM 오류=502 로 안내와 함께 변환된다(실제 LLM 호출은 모킹).
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from sola.client import LLMNotConfigured

client = TestClient(app)

_TASK = {"task": {"process_id": "7-CT-C2-SUBASM-WELD", "lv3": "용접"}, "days": 7}


def test_generate_llm_not_configured_returns_503():
    with patch("api.routers.proposals.propose_for_task", side_effect=LLMNotConfigured("키 없음")):
        r = client.post("/api/proposals/generate", json=_TASK)
    assert r.status_code == 503
    assert "LLM 미설정" in r.json()["detail"]


def test_generate_llm_error_returns_502():
    with patch("api.routers.proposals.propose_for_task", side_effect=RuntimeError("Host not in allowlist")):
        r = client.post("/api/proposals/generate", json=_TASK)
    assert r.status_code == 502
    assert "LLM 오류" in r.json()["detail"]


def test_summarize_llm_error_returns_502():
    with patch("sola.summarize.summarize_news", side_effect=RuntimeError("boom")):
        r = client.post("/api/proposals/summarize", json={"days": 3})
    assert r.status_code == 502


def test_health_deps_reports_dependencies():
    body = client.get("/api/health/deps").json()
    assert body["status"] == "ok"
    assert "configured" in body["llm"]
    assert "taskdefs" in body and "news_7d" in body
    # liveness 프로브는 의존성과 무관하게 항상 단순 200
    assert client.get("/api/health").json() == {"status": "ok", "phase": "1"}
