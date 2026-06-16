"""P1 데이터 API — sources / collect status·diagnose / trends emergence / matches / summarize."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from store import news_db

client = TestClient(app)


def _seed():
    news_db.save_articles(
        [{"title": "조선소 용접 자동화", "link": "l1", "source": "naver",
          "keywords": "용접, 자동화", "date": "2026-06-16", "summary": "현장 적용"}],
        source="naver",
    )


# ── sources ────────────────────────────────────────────────

def test_sources_list_defaults_enabled():
    items = client.get("/api/sources").json()["items"]
    assert len(items) >= 4
    assert all(i["enabled"] for i in items)


def test_sources_toggle_and_custom():
    name = client.get("/api/sources").json()["items"][0]["name"]
    after = client.post(f"/api/sources/{name}/toggle").json()["items"]
    assert any(i["name"] == name and i["enabled"] is False for i in after)

    add = client.post("/api/sources", json={"name": "조선e뉴스", "url": "https://x/rss"})
    assert add.status_code == 201
    assert any(i["name"] == "조선e뉴스" and i["custom"] for i in add.json()["items"])

    assert client.delete("/api/sources/조선e뉴스").status_code == 200
    assert client.delete("/api/sources/없음").status_code == 404


# ── collect status / diagnose ──────────────────────────────

def test_collect_status_empty_ok():
    body = client.get("/api/collect/status").json()
    assert "latest" in body and "daily" in body
    assert client.get("/api/collect/runs").json() == []


def test_collect_diagnose_delegates():
    with patch("scraping.diagnose.diagnose", return_value={"ok": True, "status": 200}) as m:
        r = client.post("/api/collect/diagnose", json={"url": "http://x"})
    assert r.status_code == 200 and r.json()["ok"] is True and m.called


# ── trends emergence ───────────────────────────────────────

def test_trends_emergence_shape():
    _seed()
    body = client.get("/api/trends/emergence").json()
    assert set(body.keys()) >= {"new", "rising"}


# ── matches ────────────────────────────────────────────────

def test_matches_empty_without_roadmap():
    _seed()
    assert client.get("/api/matches").json() == []


# ── proposals summarize ────────────────────────────────────

def test_proposals_summarize_delegates():
    _seed()
    with patch("sola.summarize.summarize_news", return_value="요약 텍스트") as m:
        r = client.post("/api/proposals/summarize", json={"days": 3})
    assert r.status_code == 200 and r.json()["summary"] == "요약 텍스트" and m.called


# ── bookmarks status filter ────────────────────────────────

def test_bookmarks_status_filter():
    client.post("/api/bookmarks", json={"type": "proposal", "title": "p1", "id": "p1"})
    client.post("/api/bookmarks/p1/status", json={"status": "adopted"})
    client.post("/api/bookmarks", json={"type": "proposal", "title": "p2", "id": "p2"})
    adopted = client.get("/api/bookmarks", params={"type": "proposal", "status": "adopted"}).json()
    assert [b["id"] for b in adopted] == ["p1"]
