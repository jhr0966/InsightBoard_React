"""roadmap.sqlite_sync + ingest SQLite 동기화 + 마이그 CLI (PR-3)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from roadmap import ingest
from roadmap.schema import ALL_COLUMNS, COLUMN_MAP


FIXTURE = Path(__file__).parent / "fixtures" / "sample_task_def.xlsx"


def _row(**kw) -> dict:
    base = {c: "" for c in ALL_COLUMNS}
    base.update(kw)
    return base


def _json(process_id="PNL-SEL-001", **extra) -> str:
    d = {"process_id": process_id, "process_name": "판넬 선별",
         "objectives": ["검수"]}
    d.update(extra)
    return json.dumps(d, ensure_ascii=False)


# ── schema 9 컬럼 폼 ─────────────────────────────────────

def test_schema_maps_process_id_column():
    assert COLUMN_MAP.get("공정ID") == "process_id"
    assert "process_id" in ALL_COLUMNS


# ── row_to_task_def ─────────────────────────────────────

def test_row_to_task_def_uses_process_id_column_first():
    from roadmap.sqlite_sync import row_to_task_def
    row = _row(team="가공팀", dept="판넬조립부", process_id="EXPLICIT-1",
               task_def_json=_json("FROM-JSON"))
    built = row_to_task_def(row)
    assert built is not None
    pid, js = built
    assert pid == "EXPLICIT-1"
    # process_id 컬럼이 JSON 내부를 덮어쓴다 (동기화)
    assert json.loads(js)["process_id"] == "EXPLICIT-1"


def test_row_to_task_def_falls_back_to_json_process_id():
    from roadmap.sqlite_sync import row_to_task_def
    row = _row(team="가공팀", dept="판넬조립부", task_def_json=_json("PNL-SEL-001"))
    built = row_to_task_def(row)
    assert built is not None
    assert built[0] == "PNL-SEL-001"


def test_row_to_task_def_injects_org_meta():
    from roadmap.sqlite_sync import row_to_task_def
    row = _row(team="가공팀", dept="판넬조립부", division="구조내업",
               process="판넬", task="선별", sub_task="선별",
               process_id="X1", task_def_json=_json("X1"))
    _, js = row_to_task_def(row)
    meta = json.loads(js)["org_meta"]
    assert meta["team"] == "가공팀"
    assert meta["division"] == "구조내업"
    assert meta["process"] == "판넬"


def test_row_to_task_def_none_when_no_process_id():
    from roadmap.sqlite_sync import row_to_task_def
    row = _row(team="가공팀", dept="판넬조립부", task_def_json="")
    assert row_to_task_def(row) is None


def test_row_to_task_def_none_when_missing_team():
    from roadmap.sqlite_sync import row_to_task_def
    row = _row(dept="판넬조립부", process_id="X1", task_def_json=_json("X1"))
    # team 누락 → org_meta 검증 실패 → None
    assert row_to_task_def(row) is None


# ── sync_dataframe ──────────────────────────────────────

def test_sync_dataframe_creates_and_updates():
    from roadmap import sqlite_sync
    from store import task_defs_db

    df = pd.DataFrame([
        _row(team="T", dept="D", process_id="A1", task_def_json=_json("A1")),
        _row(team="T", dept="D", process_id="A2", task_def_json=_json("A2")),
    ])
    res = sqlite_sync.sync_dataframe(df)
    assert res.created == 2
    assert res.updated == 0
    assert task_defs_db.count() == 2

    # 같은 id 재동기화 → update
    res2 = sqlite_sync.sync_dataframe(df)
    assert res2.updated == 2
    assert res2.created == 0
    assert task_defs_db.count() == 2


def test_sync_dataframe_skips_invalid_rows():
    from roadmap import sqlite_sync
    from store import task_defs_db

    df = pd.DataFrame([
        _row(team="T", dept="D", process_id="A1", task_def_json=_json("A1")),
        _row(team="T", dept="", process_id="A2", task_def_json=_json("A2")),  # dept 없음
        _row(team="T", dept="D", task_def_json=""),  # process_id 없음
    ])
    res = sqlite_sync.sync_dataframe(df)
    assert res.created == 1
    assert res.skipped == 2
    assert task_defs_db.count() == 1


def test_sync_dataframe_empty_returns_zero():
    from roadmap import sqlite_sync
    res = sqlite_sync.sync_dataframe(pd.DataFrame())
    assert res.created == res.updated == res.skipped == 0


def test_sync_dataframe_records_source_in_history():
    from roadmap import sqlite_sync
    from store import task_defs_db

    df = pd.DataFrame([_row(team="T", dept="D", process_id="A1",
                            task_def_json=_json("A1"))])
    sqlite_sync.sync_dataframe(df, changed_by="migrator", source="migration")
    hist = task_defs_db.history("A1")
    assert hist[0]["source"] == "migration"
    assert hist[0]["changed_by"] == "migrator"


# ── ingest_excel → SQLite ───────────────────────────────

def test_ingest_excel_populates_sqlite():
    from store import task_defs_db
    with open(FIXTURE, "rb") as f:
        res = ingest.ingest_excel(f, sheet_name=0, save_raw=False)
    assert res.ok, res.errors
    # 32행 중 31건은 JSON 내부 process_id 존재, 1건은 JSON 비어 skip.
    assert res.sqlite_created == 31
    assert res.sqlite_skipped == 1
    assert task_defs_db.count() == 31
    # 실제 1건 검증
    row = task_defs_db.get("PNL-SEL-001")
    assert row is not None
    assert row["team"]  # org_meta.team 미러
    assert row["json_obj"]["process_id"] == "PNL-SEL-001"


def test_ingest_excel_to_sqlite_false_skips_sync():
    from store import task_defs_db
    with open(FIXTURE, "rb") as f:
        res = ingest.ingest_excel(f, sheet_name=0, save_raw=False, to_sqlite=False)
    assert res.ok
    assert res.sqlite_created == 0
    assert task_defs_db.count() == 0


def test_ingest_excel_reupload_upserts():
    """같은 엑셀 두 번 → 두 번째는 전부 update (count 유지)."""
    from store import task_defs_db
    with open(FIXTURE, "rb") as f:
        ingest.ingest_excel(f, sheet_name=0, save_raw=False)
    assert task_defs_db.count() == 31
    with open(FIXTURE, "rb") as f:
        res2 = ingest.ingest_excel(f, sheet_name=0, save_raw=False)
    assert res2.sqlite_updated == 31
    assert res2.sqlite_created == 0
    assert task_defs_db.count() == 31


# ── 마이그 CLI ───────────────────────────────────────────

def test_migrate_cli_from_latest_parquet():
    from store import task_defs_db
    from scripts import migrate_roadmap_to_sqlite as mig

    # 먼저 Parquet 만 생성 (SQLite 동기화 끔)
    with open(FIXTURE, "rb") as f:
        ingest.ingest_excel(f, sheet_name=0, save_raw=False, to_sqlite=False)
    assert task_defs_db.count() == 0

    code = mig.main([])
    assert code == 0
    assert task_defs_db.count() == 31


def test_migrate_cli_dry_run_writes_nothing():
    from store import task_defs_db
    from scripts import migrate_roadmap_to_sqlite as mig

    with open(FIXTURE, "rb") as f:
        ingest.ingest_excel(f, sheet_name=0, save_raw=False, to_sqlite=False)

    code = mig.main(["--dry-run"])
    assert code == 0
    assert task_defs_db.count() == 0  # dry-run 은 안 씀


def test_migrate_cli_returns_1_when_no_data():
    from scripts import migrate_roadmap_to_sqlite as mig
    # roadmap_dir 비어있음 (conftest 격리)
    code = mig.main([])
    assert code == 1
