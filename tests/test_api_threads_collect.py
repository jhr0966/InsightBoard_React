"""api.routers.threads (스레드+메시지 영구화) / collect (수집 실행 위임)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ── threads ────────────────────────────────────────────────

def test_thread_crud_and_messages():
    created = client.post("/api/threads", json={"title": "용접 자동화 검토"}).json()
    tid = created["id"]
    assert created["title"].startswith("용접")
    assert created["created_at"]

    assert any(t["id"] == tid for t in client.get("/api/threads").json())
    assert client.get(f"/api/threads/{tid}").json()["id"] == tid

    # 핀 고정
    patched = client.patch(f"/api/threads/{tid}", json={"pinned": True}).json()
    assert patched["pinned"] is True

    # 메시지 저장 → 복원 + 스레드 카운트 동기화
    msgs = [{"role": "user", "content": "안녕"}, {"role": "assistant", "content": "반가워요"}]
    put = client.put(f"/api/threads/{tid}/messages", json={"messages": msgs})
    assert put.json() == {"ok": True, "count": 2}
    assert client.get(f"/api/threads/{tid}/messages").json() == msgs
    assert client.get(f"/api/threads/{tid}").json()["message_count"] == 2

    # 삭제 → 메시지도 reset
    assert client.delete(f"/api/threads/{tid}").json()["deleted"] is True
    assert client.get(f"/api/threads/{tid}").status_code == 404
    assert client.get(f"/api/threads/{tid}/messages").json() == []


def test_thread_missing_404():
    assert client.get("/api/threads/nope").status_code == 404
    assert client.patch("/api/threads/nope", json={"title": "x"}).status_code == 404
    assert client.delete("/api/threads/nope").status_code == 404


# ── collect ────────────────────────────────────────────────

def test_collect_delegates(monkeypatch):
    import scraping.run_daily as rd

    class _Report:
        total_articles = 3
        total_files = 1
        saved = [{"source": "naver", "keywords": "용접", "count": 3, "path": "x.parquet"}]
        errors: list = []

    captured = {}

    def _fake_batch(keywords, **kw):
        captured["keywords"] = list(keywords)
        captured["max_results"] = kw.get("max_results")
        return _Report()

    monkeypatch.setattr(rd, "collect_batch", _fake_batch)
    r = client.post("/api/collect", json={"keywords": ["용접 로봇"], "max_results": 5, "do_enrich": False})
    assert r.status_code == 200
    body = r.json()
    assert body["total_articles"] == 3 and body["total_files"] == 1
    assert captured["keywords"] == ["용접 로봇"]
    assert captured["max_results"] == 5


def test_collect_stream_emits_step_and_done(monkeypatch):
    import scraping.run_daily as rd

    class _Report:
        total_articles = 2
        total_files = 1
        errors: list = []

    def _fake_batch(keywords, *, on_step=None, **kw):
        if on_step:
            on_step("naver", "용접", 2)
        return _Report()

    monkeypatch.setattr(rd, "collect_batch", _fake_batch)
    with client.stream("POST", "/api/collect/stream",
                       json={"keywords": ["용접"], "do_enrich": False}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        frames = [ln for ln in r.iter_lines() if ln and ln.startswith("data:")]
    types = [__import__("json").loads(f[5:].strip())["type"] for f in frames]
    assert types[0] == "start"
    assert "step" in types and types[-1] == "done"
