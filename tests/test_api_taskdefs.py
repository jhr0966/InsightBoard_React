"""api.routers.taskdefs — FastAPI 작업정의 엔드포인트 (store 위임 + 식별필드)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _make_json(process_id: str = "PNL-SEL-001", *, team: str = "가공팀",
               dept: str = "판넬조립부", objectives=None) -> dict:
    return {
        "process_id": process_id,
        "org_meta": {"team": team, "dept": dept, "division": "구조내업",
                     "process": "선별", "task": "강재선별"},
        "objectives": objectives or ["품질 확보"],
    }


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_put_creates_and_get_returns_with_identity():
    r = client.put("/api/taskdefs/PNL-SEL-001", json={"json": _make_json()})
    assert r.status_code == 200
    body = r.json()
    assert body["process_id"] == "PNL-SEL-001"
    assert body["team"] == "가공팀"
    assert body["json"]["objectives"] == ["품질 확보"]
    # 식별·감사 필드 노출
    assert body["user_id"] == "local"
    assert body["workspace_id"] == "default"
    assert body["created_at"] and body["updated_at"]

    g = client.get("/api/taskdefs/PNL-SEL-001")
    assert g.status_code == 200
    assert g.json()["process_id"] == "PNL-SEL-001"


def test_get_missing_returns_404():
    assert client.get("/api/taskdefs/NOPE").status_code == 404


def test_list_and_filter():
    client.put("/api/taskdefs/A1", json={"json": _make_json("A1", team="T1", dept="D1")})
    client.put("/api/taskdefs/A2", json={"json": _make_json("A2", team="T1", dept="D2")})
    all_rows = client.get("/api/taskdefs").json()
    assert {r["process_id"] for r in all_rows} == {"A1", "A2"}
    d1 = client.get("/api/taskdefs", params={"dept": "D1"}).json()
    assert [r["process_id"] for r in d1] == ["A1"]


def test_search_q():
    client.put("/api/taskdefs/PNL-SEL-001", json={"json": _make_json("PNL-SEL-001")})
    client.put("/api/taskdefs/OTHER-1", json={"json": _make_json("OTHER-1")})
    found = client.get("/api/taskdefs", params={"q": "PNL-SEL"}).json()
    assert len(found) == 1 and found[0]["process_id"] == "PNL-SEL-001"


def test_put_updates_existing_and_records_history():
    client.put("/api/taskdefs/A1", json={"json": _make_json("A1", objectives=["v1"])})
    r = client.put("/api/taskdefs/A1", json={"json": _make_json("A1", objectives=["v1", "v2"])})
    assert r.json()["json"]["objectives"] == ["v1", "v2"]
    hist = client.get("/api/taskdefs/A1/history").json()
    actions = [h["action"] for h in hist]
    assert actions == ["update", "create"]  # 최신순
    assert all(h["source"] == "api" for h in hist)


def test_put_invalid_json_returns_422():
    # org_meta 누락 → store 가 ValueError → 422
    r = client.put("/api/taskdefs/BAD", json={"json": {"process_id": "BAD"}})
    assert r.status_code == 422


def test_delete():
    client.put("/api/taskdefs/A1", json={"json": _make_json("A1")})
    d = client.delete("/api/taskdefs/A1")
    assert d.status_code == 200 and d.json()["deleted"] is True
    assert client.get("/api/taskdefs/A1").status_code == 404
    assert client.delete("/api/taskdefs/A1").status_code == 404  # 두 번째는 없음
