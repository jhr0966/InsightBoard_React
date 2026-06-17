"""api.routers.news / trends / proposals — store·sola 위임."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from store import news_db

client = TestClient(app)


def _seed():
    news_db.save_articles(
        [
            {"title": "조선소 용접 자동화", "link": "l1", "source": "naver",
             "keywords": "용접, 자동화", "date": "2026-06-15"},
            {"title": "강재 절단 효율화", "link": "l2", "source": "google",
             "keywords": "절단, 자동화", "date": "2026-06-15"},
        ],
        source="naver",
    )


def test_news_list_and_source_filter():
    _seed()
    alln = client.get("/api/news").json()
    assert len(alln) == 2
    assert "title" in alln[0] and "content" not in alln[0]  # 경량 필드
    naver = client.get("/api/news", params={"source": "naver"}).json()
    assert [r["link"] for r in naver] == ["l1"]


def test_news_today():
    _seed()
    assert len(client.get("/api/news/today").json()) == 2


def test_news_empty_ok():
    assert client.get("/api/news").json() == []


def test_news_detail_returns_content():
    news_db.save_articles(
        [{"title": "본문 있는 기사", "link": "ld1", "source": "naver",
          "content": "이것은 기사 본문 전체입니다.", "keywords_llm": "용접, 로봇",
          "date": "2026-06-15"}],
        source="naver",
    )
    r = client.get("/api/news/detail", params={"link": "ld1"})
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "이것은 기사 본문 전체입니다."
    assert body["keywords_llm"] == "용접, 로봇"


def test_news_detail_404_when_missing():
    assert client.get("/api/news/detail", params={"link": "nope"}).status_code == 404


def test_trends_keywords_volume_sources():
    _seed()
    kw = client.get("/api/trends/keywords").json()
    kws = {r["keyword"]: r["count"] for r in kw}
    assert kws.get("자동화") == 2
    vol = client.get("/api/trends/volume", params={"days": 7}).json()
    assert sum(r["count"] for r in vol) == 2
    src = client.get("/api/trends/sources").json()
    assert {r["source"] for r in src} == {"naver", "google"}


def test_proposals_generate_delegates():
    _seed()
    with patch("api.routers.proposals.propose_for_task", return_value="## 제안서\n초안") as m:
        r = client.post("/api/proposals/generate", json={
            "task": {"process_id": "PNL-1", "org_meta": {"team": "T", "dept": "D"}},
        })
    assert r.status_code == 200
    assert r.json()["proposal"].startswith("## 제안서")
    assert r.json()["task_process_id"] == "PNL-1"
    assert m.called


def test_assistant_context_packages_persona_and_digest():
    _seed()
    r = client.get("/api/assistant/context", params={"screen": "insights", "days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["screen"] == "insights"
    assert body["news_count"] == 2
    assert "자동화" in body["context"]
