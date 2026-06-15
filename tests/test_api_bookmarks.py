"""api.routers.bookmarks — 북마크 CRUD + 상태 (store 위임 + 식별필드)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_create_lists_with_identity():
    r = client.post("/api/bookmarks", json={"type": "news", "title": "기사", "link": "http://x"})
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "news" and body["title"] == "기사"
    assert body["user_id"] == "local" and body["workspace_id"] == "default"
    assert body["created_at"] and body["updated_at"]

    lst = client.get("/api/bookmarks").json()
    assert len(lst) == 1 and lst[0]["id"] == body["id"]


def test_create_rejects_unknown_type():
    assert client.post("/api/bookmarks", json={"type": "bogus", "title": "t"}).status_code == 422


def test_filter_by_type():
    client.post("/api/bookmarks", json={"type": "news", "title": "n", "id": "n1"})
    client.post("/api/bookmarks", json={"type": "proposal", "title": "p", "id": "p1"})
    news = client.get("/api/bookmarks", params={"type": "news"}).json()
    assert [b["id"] for b in news] == ["n1"]


def test_update_content_bumps_updated_at():
    client.post("/api/bookmarks", json={"type": "news", "title": "v1", "id": "b1"})
    r = client.patch("/api/bookmarks/b1", json={"title": "v2"})
    assert r.status_code == 200 and r.json()["title"] == "v2"


def test_update_missing_404():
    assert client.patch("/api/bookmarks/nope", json={"title": "x"}).status_code == 404


def test_status_flow_and_summary():
    client.post("/api/bookmarks", json={"type": "proposal", "title": "p", "id": "p1"})
    r = client.post("/api/bookmarks/p1/status", json={"status": "adopted"})
    assert r.status_code == 200 and r.json()["status"] == "adopted"
    assert r.json()["updated_at"] == r.json()["decided_at"]
    summ = client.get("/api/bookmarks/summary").json()
    assert summ["proposal_status"]["adopted"] == 1


def test_status_invalid_422():
    client.post("/api/bookmarks", json={"type": "proposal", "title": "p", "id": "p1"})
    assert client.post("/api/bookmarks/p1/status", json={"status": "bogus"}).status_code == 422


def test_delete():
    client.post("/api/bookmarks", json={"type": "news", "title": "n", "id": "b1"})
    assert client.delete("/api/bookmarks/b1").status_code == 200
    assert client.delete("/api/bookmarks/b1").status_code == 404
