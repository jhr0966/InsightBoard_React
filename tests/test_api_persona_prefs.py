"""api.routers.persona / prefs — 페르소나 CRUD·derive + 표시 설정."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ── persona ────────────────────────────────────────────────

def test_persona_default_empty():
    r = client.get("/api/persona")
    assert r.status_code == 200
    body = r.json()
    assert body["is_set"] is False
    assert body["label"] == "(미설정)"


def test_persona_put_and_get_roundtrip():
    payload = {"name": "홍길동", "team": "가공팀", "dept": "가공부", "job": "용접 담당",
               "interest_keywords": ["용접 로봇"]}
    r = client.put("/api/persona", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["dept"] == "가공부"
    assert body["is_set"] is True
    assert body["label"] == "가공부 · 용접 담당"
    assert body["interest_keywords"] == ["용접 로봇"]
    # 영속 확인
    assert client.get("/api/persona").json()["name"] == "홍길동"


def test_persona_derive_runs_without_llm():
    client.put("/api/persona", json={"dept": "가공부", "interest_keywords": ["자동화"]})
    r = client.post("/api/persona/derive")
    assert r.status_code == 200
    # LLM 미설정 → 룰 기반 폴백으로라도 derived_source 채워짐
    assert r.json()["derived_source"]


def test_persona_reset():
    client.put("/api/persona", json={"dept": "가공부"})
    r = client.post("/api/persona/reset")
    assert r.status_code == 200 and r.json()["is_set"] is False


# ── ui-prefs ───────────────────────────────────────────────

def test_prefs_default():
    r = client.get("/api/ui-prefs")
    assert r.json() == {"theme": "light", "font": "medium"}


def test_prefs_put_roundtrip():
    r = client.put("/api/ui-prefs", json={"theme": "dark", "font": "large"})
    assert r.json() == {"theme": "dark", "font": "large"}
    assert client.get("/api/ui-prefs").json()["theme"] == "dark"


def test_prefs_invalid_falls_back():
    r = client.put("/api/ui-prefs", json={"theme": "bogus", "font": "huge"})
    assert r.json() == {"theme": "light", "font": "medium"}
