"""roadmap.query.load_latest — SQLite 우선, Parquet fallback (PR-4)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from roadmap import ingest, query
from roadmap.schema import ALL_COLUMNS


FIXTURE = Path(__file__).parent / "fixtures" / "sample_task_def.xlsx"


# ── 시그니처 호환 ─────────────────────────────────────────

def test_load_latest_returns_all_columns_dataframe_when_empty():
    df = query.load_latest()
    assert df.empty


def test_load_latest_parquet_fallback_when_sqlite_empty(tmp_path):
    """SQLite 가 비어있고 Parquet 만 있으면 Parquet 사용."""
    # to_sqlite=False — Parquet 만 만들기
    with open(FIXTURE, "rb") as f:
        res = ingest.ingest_excel(f, sheet_name=0, save_raw=False, to_sqlite=False)
    assert res.ok

    from store import task_defs_db
    assert task_defs_db.count() == 0

    df = query.load_latest()
    # Parquet fallback — 32행 모두 유지 (process_id 없는 행 포함)
    assert len(df) == 32
    for col in ALL_COLUMNS:
        assert col in df.columns


def test_load_latest_prefers_sqlite_when_populated():
    """SQLite 에 데이터가 있으면 거기서 읽는다 (Parquet 무시)."""
    # SQLite + Parquet 둘 다 채움
    with open(FIXTURE, "rb") as f:
        res = ingest.ingest_excel(f, sheet_name=0, save_raw=False, to_sqlite=True)
    assert res.ok
    assert res.sqlite_created == 31

    df = query.load_latest()
    # SQLite 행 수 (31) — process_id 없는 1건 skip
    assert len(df) == 31
    for col in ALL_COLUMNS:
        assert col in df.columns


def test_load_latest_explicit_parquet_skips_sqlite():
    """`prefer='parquet'` 는 SQLite 가 차있어도 Parquet 만 읽는다 (마이그용)."""
    with open(FIXTURE, "rb") as f:
        ingest.ingest_excel(f, sheet_name=0, save_raw=False, to_sqlite=True)

    df = query.load_latest(prefer="parquet")
    assert len(df) == 32  # Parquet 원본


# ── SQLite → DataFrame 빌드 정확성 ────────────────────────

def test_sqlite_dataframe_preserves_org_meta_fields():
    from store import task_defs_db

    js = json.dumps({
        "process_id": "PNL-SEL-001",
        "process_name": "판넬 선별",
        "org_meta": {
            "team": "가공팀", "dept": "판넬조립부",
            "division": "구조내업", "process": "판넬",
            "task": "선별", "sub_task": "선별",
        },
    }, ensure_ascii=False)
    task_defs_db.upsert("PNL-SEL-001", js, task_def_text="줄글")

    df = query.load_latest()
    assert len(df) == 1
    row = df.iloc[0]
    assert row["team"] == "가공팀"
    assert row["dept"] == "판넬조립부"
    assert row["division"] == "구조내업"
    assert row["process"] == "판넬"
    assert row["task"] == "선별"
    assert row["sub_task"] == "선별"
    # lv1/lv2/lv3 fallback (division/process/task)
    assert row["lv1"] == "구조내업"
    assert row["lv2"] == "판넬"
    assert row["lv3"] == "선별"
    assert row["task_def"] == "줄글"
    assert row["process_id"] == "PNL-SEL-001"


def test_sqlite_dataframe_works_with_by_dept_and_filter():
    """기존 by_dept / filter_hierarchy 가 SQLite-backed DF 에서도 동작."""
    from store import task_defs_db

    for pid, dept in (("A1", "D1"), ("A2", "D1"), ("A3", "D2")):
        js = json.dumps({
            "process_id": pid,
            "org_meta": {"team": "T", "dept": dept, "process": "P", "task": "X"},
        }, ensure_ascii=False)
        task_defs_db.upsert(pid, js)

    df = query.load_latest()
    by = query.by_dept(df)
    assert dict(zip(by["dept"], by["count"])) == {"D1": 2, "D2": 1}

    only_d1 = query.filter_hierarchy(df, dept="D1")
    assert len(only_d1) == 2
    assert set(only_d1["process_id"]) == {"A1", "A2"}


def test_ingest_excel_then_load_latest_roundtrip_preserves_task_def_json():
    """ingest_excel → SQLite → load_latest → task_def_json 보존."""
    with open(FIXTURE, "rb") as f:
        ingest.ingest_excel(f, sheet_name=0, save_raw=False)
    df = query.load_latest()
    # 임의의 1건 — task_def_json 안에 org_meta 가 주입돼있다
    sample = df[df["process_id"] == "PNL-SEL-001"]
    assert len(sample) == 1
    obj = json.loads(sample.iloc[0]["task_def_json"])
    assert obj["process_id"] == "PNL-SEL-001"
    assert obj["org_meta"]["team"]
    assert obj["org_meta"]["dept"]
