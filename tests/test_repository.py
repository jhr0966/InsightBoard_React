"""store.repository — 영구화 백엔드 seam (Phase 2 교체점)."""
from __future__ import annotations

import pytest

from store.repository import JsonlRepository, Repository, get_repository


def test_jsonl_is_a_repository():
    assert isinstance(JsonlRepository("x"), Repository)


def test_upsert_get_delete_roundtrip():
    repo = JsonlRepository("unit_coll")
    saved = repo.upsert({"id": "a", "v": 1})
    # upsert 가 식별·감사 필드 stamp
    assert saved["user_id"] == "local" and saved["workspace_id"] == "default"
    assert saved["created_at"] and saved["updated_at"]
    assert repo.get("a")["v"] == 1
    assert repo.get("missing") is None

    repo.upsert({"id": "a", "v": 2})  # 같은 id → 교체
    assert repo.get("a")["v"] == 2
    assert len(repo.read_all()) == 1

    assert repo.delete("a") is True
    assert repo.delete("a") is False
    assert repo.read_all() == []


def test_upsert_custom_identity_and_list_scope():
    repo = JsonlRepository("scoped")
    repo.upsert({"id": "1"}, user="alice", workspace="ws1")
    repo.upsert({"id": "2"}, user="bob", workspace="ws2")
    assert {r["id"] for r in repo.list(user_id="alice")} == {"1"}
    assert {r["id"] for r in repo.list(workspace_id="ws2")} == {"2"}
    assert len(repo.list()) == 2


def test_read_all_backfills_legacy_records():
    repo = JsonlRepository("legacy")
    repo.write_all([{"id": "old"}])  # 식별필드 없는 과거 레코드
    got = repo.read_all()[0]
    assert got["user_id"] == "local" and got["workspace_id"] == "default"


def test_get_repository_file_default(monkeypatch):
    monkeypatch.delenv("INSIGHTBOARD_STORAGE", raising=False)
    assert isinstance(get_repository("c"), JsonlRepository)
    monkeypatch.setenv("INSIGHTBOARD_STORAGE", "file")
    assert isinstance(get_repository("c"), JsonlRepository)


def test_get_repository_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("INSIGHTBOARD_STORAGE", "postgres")
    with pytest.raises(NotImplementedError):
        get_repository("c")
