"""store._audit — 식별·감사 필드 표준 헬퍼."""
from __future__ import annotations

from store._audit import (
    AUDIT_FIELDS,
    DEFAULT_USER,
    DEFAULT_WORKSPACE,
    backfill,
    now_iso,
    stamp,
)


def test_now_iso_is_utc_seconds():
    s = now_iso()
    assert s.endswith("+00:00")  # UTC offset
    assert "." not in s  # 초 단위 (마이크로초 없음)


def test_stamp_new_record_fills_all_fields():
    rec = stamp({"id": "x"})
    for f in AUDIT_FIELDS:
        assert f in rec
    assert rec["user_id"] == DEFAULT_USER
    assert rec["workspace_id"] == DEFAULT_WORKSPACE
    assert rec["created_by"] == DEFAULT_USER
    assert rec["created_at"] == rec["updated_at"]  # 신규는 동일


def test_stamp_existing_preserves_created_bumps_updated():
    rec = stamp(
        {"id": "x", "created_at": "2020-01-01T00:00:00+00:00", "created_by": "alice"},
        now="2026-06-15T00:00:00+00:00",
    )
    assert rec["created_at"] == "2020-01-01T00:00:00+00:00"  # 보존
    assert rec["created_by"] == "alice"  # 보존
    assert rec["updated_at"] == "2026-06-15T00:00:00+00:00"  # 갱신


def test_stamp_custom_user_workspace():
    rec = stamp({"id": "x"}, user="bob", workspace="ws2")
    assert rec["user_id"] == "bob"
    assert rec["workspace_id"] == "ws2"
    assert rec["created_by"] == "bob"


def test_stamp_non_dict_is_noop():
    assert stamp("not a dict") == "not a dict"  # type: ignore[arg-type]


def test_backfill_does_not_change_updated_at():
    rec = backfill({"id": "x", "created_at": "2020-01-01T00:00:00+00:00"})
    assert rec["updated_at"] == "2020-01-01T00:00:00+00:00"  # created_at 로 백필
    assert rec["user_id"] == DEFAULT_USER


def test_backfill_preserves_existing_values():
    rec = backfill({"user_id": "alice", "workspace_id": "ws9"})
    assert rec["user_id"] == "alice"
    assert rec["workspace_id"] == "ws9"
