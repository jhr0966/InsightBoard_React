"""Proposal 엔터티 (Step 13, §15) — 상태 확장·전환 이력·구조 필드·bookmark 이관.

가드하는 것:
- 9-상태 라이프사이클 + 알 수 없는 상태 거부
- 상태 전환마다 proposal_history 보존, 동일 상태 전환은 이력 없음
- PoC 결과는 본문이 아닌 구조 필드(poc_result·actual_effect)로 저장
- 구 bookmark(type=proposal) 이관: 원본 보존 · 멱등 · legacy/evidence_unavailable 표시
- API 레벨: 저장·목록·상태·삭제 + 사용자 격리(X-User-Id)
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from store import proposals_db

client = TestClient(app)
A = {"X-User-Id": "userA"}
B = {"X-User-Id": "userB"}


# ── store 계층 ──────────────────────────────────────────────


def test_create_get_and_status_validation():
    p = proposals_db.create(title="용접 검사 자동화", content="# 초안",
                            task_id="P-001", article_ids=["a1", "a2"],
                            matching_version=2, prompt_version=2)
    got = proposals_db.get(p["proposal_id"])
    assert got is not None
    assert got["status"] == "draft"
    assert got["article_ids"] == ["a1", "a2"]
    assert got["matching_version"] == 2
    # 생성도 이력 1건("" → draft)
    hist = proposals_db.history(p["proposal_id"])
    assert len(hist) == 1 and hist[0]["to_status"] == "draft"
    # 알 수 없는 상태는 거부
    import pytest

    with pytest.raises(ValueError):
        proposals_db.create(title="x", content="", status="approved")


def test_status_transition_history_preserved():
    p = proposals_db.create(title="t", content="")
    pid = p["proposal_id"]
    proposals_db.set_status(pid, "reviewing", note="검토 시작")
    proposals_db.set_status(pid, "poc_ready", note="PoC 준비")
    out = proposals_db.set_status(pid, "adopted", note="채택!")
    assert out is not None and out["status"] == "adopted"
    hist = proposals_db.history(pid)
    # 생성 1 + 전환 3
    assert [(h["from_status"], h["to_status"]) for h in hist] == [
        ("", "draft"), ("draft", "reviewing"),
        ("reviewing", "poc_ready"), ("poc_ready", "adopted")]
    assert hist[-1]["note"] == "채택!"
    # 동일 상태로의 전환은 이력을 만들지 않는다
    proposals_db.set_status(pid, "adopted")
    assert len(proposals_db.history(pid)) == 4
    # 없는 과제는 None
    assert proposals_db.set_status("prop-none", "adopted") is None


def test_update_fields_structured_poc_result():
    p = proposals_db.create(title="t", content="본문")
    out = proposals_db.update_fields(p["proposal_id"], {
        "owner": "홍길동", "expected_kpi": ["검사시간 30%↓", "불량 검출률 95%"],
        "poc_result": "샘플 500장 정확도 92%", "actual_effect": "리드타임 20%↓",
        "unknown_field": "무시되어야 함",
    })
    assert out is not None
    assert out["owner"] == "홍길동"
    assert out["expected_kpi"] == ["검사시간 30%↓", "불량 검출률 95%"]
    assert out["poc_result"] == "샘플 500장 정확도 92%"
    # PoC 결과가 본문에 섞이지 않는다(구조 필드 분리 §15)
    assert out["content"] == "본문"
    assert "unknown_field" not in out


def test_migrate_from_bookmarks_idempotent_and_flags():
    from store import bookmarks as bm_store

    # 근거 meta 있는 신형 bookmark + meta 없는 구형 bookmark
    bm_store.add(bm_store.Bookmark(
        id="bmwithmeta12345", type="proposal", title="근거 있는 제안", content="md1",
        status="pending",
        meta={"task_id": "P-9", "article_ids": ["a1"], "matching_version": 2,
              "prompt_version": 2}))
    bm_store.add(bm_store.Bookmark(
        id="bmnometa678901", type="proposal", title="구형 제안", content="md2",
        status="adopted"))

    r1 = proposals_db.migrate_from_bookmarks()
    assert r1 == {"migrated": 2, "skipped": 0}
    # 재실행 멱등
    r2 = proposals_db.migrate_from_bookmarks()
    assert r2 == {"migrated": 0, "skipped": 2}
    # 원본 bookmark 보존
    assert len(bm_store.list_all(type_="proposal")) == 2

    items = {p["title"]: p for p in proposals_db.list_all()}
    with_meta = items["근거 있는 제안"]
    no_meta = items["구형 제안"]
    # meta 복원 + 상태 매핑(pending→reviewing)
    assert with_meta["legacy"] is True
    assert with_meta["evidence_unavailable"] is False
    assert with_meta["article_ids"] == ["a1"]
    assert with_meta["task_id"] == "P-9"
    assert with_meta["status"] == "reviewing"
    # meta 없음 → 근거 복원 불가 표시
    assert no_meta["legacy"] is True
    assert no_meta["evidence_unavailable"] is True
    assert no_meta["status"] == "adopted"


# ── API 계층 ────────────────────────────────────────────────


def test_api_save_list_status_delete_roundtrip():
    res = client.post("/api/proposals/save", json={
        "title": "API 저장", "content": "md", "task_id": "P-1",
        "article_ids": ["a1"], "matching_version": 2, "prompt_version": 2})
    assert res.status_code == 200
    pid = res.json()["proposal_id"]

    assert any(p["proposal_id"] == pid for p in client.get("/api/proposals/list").json())
    # 잘못된 status 필터/전환은 422
    assert client.get("/api/proposals/list", params={"status": "nope"}).status_code == 422
    assert client.patch(f"/api/proposals/{pid}/status",
                        json={"status": "nope"}).status_code == 422
    # 없는 과제 전환은 404
    assert client.patch("/api/proposals/prop-none/status",
                        json={"status": "adopted"}).status_code == 404

    assert client.patch(f"/api/proposals/{pid}/status",
                        json={"status": "poc_running", "note": "PoC 착수"}
                        ).json()["status"] == "poc_running"
    assert client.patch(f"/api/proposals/{pid}",
                        json={"fields": {"owner": "김담당"}}).json()["owner"] == "김담당"
    hist = client.get(f"/api/proposals/{pid}/history").json()
    assert [h["to_status"] for h in hist] == ["draft", "poc_running"]

    summ = client.get("/api/proposals/summary").json()
    assert summ["total"] >= 1
    assert client.delete(f"/api/proposals/{pid}").json()["deleted"] is True
    assert client.delete(f"/api/proposals/{pid}").json()["deleted"] is False


def test_api_user_isolation():
    client.post("/api/proposals/save", json={"title": "A의 과제", "content": ""}, headers=A)
    client.post("/api/proposals/save", json={"title": "B의 과제", "content": ""}, headers=B)
    a_titles = [p["title"] for p in client.get("/api/proposals/list", headers=A).json()]
    b_titles = [p["title"] for p in client.get("/api/proposals/list", headers=B).json()]
    assert "A의 과제" in a_titles and "B의 과제" not in a_titles
    assert "B의 과제" in b_titles and "A의 과제" not in b_titles
    assert client.get("/api/proposals/summary", headers=A).json()["total"] == 1
