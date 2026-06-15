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
