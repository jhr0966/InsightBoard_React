"""store.task_defs_db — SQLite 저장소 단위 테스트.

PR-1 / docs/TASK_DEF_PLAN.md M1.
"""
from __future__ import annotations

import json

import pytest


# ── 샘플 빌더 ────────────────────────────────────────────

def _make_json(
    process_id: str = "PNL-SEL-001",
    *,
    team: str = "가공팀",
    dept: str = "판넬조립부",
    division: str | None = "구조내업",
    process: str | None = "판넬",
    task: str | None = "선별",
    objectives: list[str] | None = None,
    extra: dict | None = None,
) -> str:
    payload = {
        "version": "1.0",
        "org_meta": {
            "team": team, "dept": dept, "division": division,
            "process": process, "task": task, "sub_task": task,
        },
        "process_id": process_id,
        "process_name": f"{process or 'X'} {task or 'Y'}",
        "objectives": objectives or ["품질 확보"],
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


# ── schema 자동 생성 ──────────────────────────────────────

def test_schema_is_created_on_first_connect():
    from store import task_defs_db
    # 단순히 호출만 해도 schema 가 만들어진다 (count → 0)
    assert task_defs_db.count() == 0
    assert task_defs_db.list_all() == []


def test_db_path_under_isolated_roadmap_dir():
    from store import task_defs_db
    # conftest fixture 가 ROADMAP_DIR 을 tmp_path 로 바꿔놨으므로
    # db_path() 도 tmp_path 하위여야 한다.
    p = task_defs_db.db_path()
    assert p.name == "task_defs.db"


# ── upsert 신규/갱신 ─────────────────────────────────────

def test_upsert_creates_new_row():
    from store import task_defs_db
    row = task_defs_db.upsert("PNL-SEL-001", _make_json())
    assert row is not None
    assert row["process_id"] == "PNL-SEL-001"
    assert row["team"] == "가공팀"
    assert row["dept"] == "판넬조립부"
    assert row["division"] == "구조내업"
    assert row["created_at"] == row["updated_at"]
    assert row["json_obj"]["objectives"] == ["품질 확보"]
    assert task_defs_db.count() == 1


def test_upsert_updates_existing_row():
    from store import task_defs_db
    task_defs_db.upsert("PNL-SEL-001", _make_json(objectives=["A"]))
    row = task_defs_db.upsert(
        "PNL-SEL-001",
        _make_json(objectives=["A", "B"]),
    )
    assert row is not None
    assert row["json_obj"]["objectives"] == ["A", "B"]
    # updated_at >= created_at
    assert row["updated_at"] >= row["created_at"]
    assert task_defs_db.count() == 1  # PK 보존


def test_upsert_records_changed_by_and_source():
    from store import task_defs_db
    row = task_defs_db.upsert(
        "PNL-SEL-001", _make_json(),
        changed_by="alice", source="excel_upload",
    )
    assert row["created_by"] == "alice"
    assert row["updated_by"] == "alice"
    hist = task_defs_db.history("PNL-SEL-001")
    assert len(hist) == 1
    assert hist[0]["action"] == "create"
    assert hist[0]["changed_by"] == "alice"
    assert hist[0]["source"] == "excel_upload"


# ── validation ──────────────────────────────────────────

def test_upsert_rejects_missing_process_id():
    from store import task_defs_db
    with pytest.raises(ValueError, match="process_id"):
        task_defs_db.upsert("", _make_json())


def test_upsert_rejects_invalid_json():
    from store import task_defs_db
    with pytest.raises(ValueError, match="invalid JSON"):
        task_defs_db.upsert("X1", "not json {")


def test_upsert_rejects_non_object_json():
    from store import task_defs_db
    with pytest.raises(ValueError, match="object"):
        task_defs_db.upsert("X1", json.dumps(["list"]))


def test_upsert_rejects_missing_org_meta():
    from store import task_defs_db
    bad = json.dumps({"process_id": "X1", "objectives": []})
    with pytest.raises(ValueError, match="org_meta"):
        task_defs_db.upsert("X1", bad)


def test_upsert_rejects_missing_team_in_org_meta():
    from store import task_defs_db
    bad = json.dumps({
        "process_id": "X1",
        "org_meta": {"dept": "D"},
    })
    with pytest.raises(ValueError, match="team"):
        task_defs_db.upsert("X1", bad)


def test_upsert_rejects_process_id_mismatch():
    from store import task_defs_db
    js = _make_json("PNL-SEL-001")
    with pytest.raises(ValueError, match="process_id mismatch"):
        task_defs_db.upsert("DIFFERENT-ID", js)


# ── get / delete ────────────────────────────────────────

def test_get_returns_none_for_missing():
    from store import task_defs_db
    assert task_defs_db.get("NOPE") is None
    assert task_defs_db.get("") is None


def test_get_returns_row_with_decoded_json():
    from store import task_defs_db
    task_defs_db.upsert("PNL-SEL-001", _make_json(objectives=["X"]))
    row = task_defs_db.get("PNL-SEL-001")
    assert row is not None
    assert row["json_obj"]["objectives"] == ["X"]


def test_delete_existing_returns_true_and_records_history():
    from store import task_defs_db
    task_defs_db.upsert("PNL-SEL-001", _make_json())
    ok = task_defs_db.delete("PNL-SEL-001", changed_by="bob")
    assert ok is True
    assert task_defs_db.get("PNL-SEL-001") is None
    hist = task_defs_db.history("PNL-SEL-001")
    assert [h["action"] for h in hist] == ["delete", "create"]
    assert hist[0]["changed_by"] == "bob"


def test_delete_missing_returns_false():
    from store import task_defs_db
    assert task_defs_db.delete("NOPE") is False


# ── list_all 필터 ───────────────────────────────────────

def test_list_all_filters_by_team_and_dept():
    from store import task_defs_db
    task_defs_db.upsert("A1", _make_json("A1", team="T1", dept="D1"))
    task_defs_db.upsert("A2", _make_json("A2", team="T1", dept="D2"))
    task_defs_db.upsert("A3", _make_json("A3", team="T2", dept="D1"))
    assert {r["process_id"] for r in task_defs_db.list_all(team="T1")} == {"A1", "A2"}
    assert {r["process_id"] for r in task_defs_db.list_all(dept="D1")} == {"A1", "A3"}
    assert {r["process_id"] for r in task_defs_db.list_all(team="T1", dept="D2")} == {"A2"}


def test_list_all_orders_by_updated_at_desc():
    from store import task_defs_db
    task_defs_db.upsert("A1", _make_json("A1"))
    task_defs_db.upsert("A2", _make_json("A2"))
    task_defs_db.upsert("A1", _make_json("A1", objectives=["new"]))  # touch
    rows = task_defs_db.list_all()
    # A1 이 가장 최근 updated_at 이므로 맨 앞
    assert rows[0]["process_id"] == "A1"


# ── search ──────────────────────────────────────────────

def test_search_matches_process_id():
    from store import task_defs_db
    task_defs_db.upsert("PNL-SEL-001", _make_json("PNL-SEL-001"))
    task_defs_db.upsert("WLD-ARC-001", _make_json("WLD-ARC-001"))
    hits = task_defs_db.search("PNL")
    assert len(hits) == 1
    assert hits[0]["process_id"] == "PNL-SEL-001"


def test_search_matches_json_content():
    from store import task_defs_db
    task_defs_db.upsert("X1", _make_json("X1", objectives=["비전 검사 정확도"]))
    task_defs_db.upsert("X2", _make_json("X2", objectives=["용접 속도"]))
    hits = task_defs_db.search("비전")
    assert len(hits) == 1
    assert hits[0]["process_id"] == "X1"


def test_search_empty_returns_empty():
    from store import task_defs_db
    task_defs_db.upsert("X1", _make_json("X1"))
    assert task_defs_db.search("") == []
    assert task_defs_db.search("   ") == []


# ── history ─────────────────────────────────────────────

def test_history_accumulates_unbounded():
    from store import task_defs_db
    task_defs_db.upsert("X1", _make_json("X1", objectives=["a"]))
    task_defs_db.upsert("X1", _make_json("X1", objectives=["a", "b"]))
    task_defs_db.upsert("X1", _make_json("X1", objectives=["a", "b", "c"]))
    hist = task_defs_db.history("X1")
    assert len(hist) == 3
    actions = [h["action"] for h in hist]
    assert actions == ["update", "update", "create"]
    # json_before: 첫 create 는 NULL, 이후 update 는 직전 json
    assert hist[-1]["json_before"] is None
    assert hist[-1]["json_after"] is not None


def test_history_returns_empty_for_unknown_process_id():
    from store import task_defs_db
    assert task_defs_db.history("NOPE") == []
    assert task_defs_db.history("") == []




# ── C4: 스키마 마이그레이션 (user_version + 누락 컬럼 ADD) ──────

def test_connect_sets_user_version():
    from store import task_defs_db
    conn = task_defs_db._connect()
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == task_defs_db._SCHEMA_VERSION
    finally:
        conn.close()


def test_migrate_adds_missing_columns_to_old_db():
    import sqlite3
    from store import task_defs_db
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE task_defs (process_id TEXT PRIMARY KEY, json TEXT)")  # 구 스키마(컬럼 부족)
    task_defs_db._migrate(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(task_defs)")}
    assert {"team", "dept", "updated_by", "created_at"} <= cols      # 누락 컬럼 ADD 됨
    assert conn.execute("PRAGMA user_version").fetchone()[0] == task_defs_db._SCHEMA_VERSION
    conn.close()
