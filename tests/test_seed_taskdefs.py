"""roadmap.seed — 작업 정의 시드 적재(빈 DB 한정 · idempotent)."""
from __future__ import annotations

from roadmap.seed import SEED_PATH, seed_if_empty
from store import task_defs_db


def test_seed_file_exists():
    assert SEED_PATH.exists(), "시드 엑셀(roadmap/seed_data/task_defs.xlsx)이 리포에 있어야 함"


def test_seed_loads_into_empty_db():
    """빈 DB → 시드 적재. 적재 건수 > 0 이고 list_all 과 일치."""
    assert task_defs_db.list_all() == []  # conftest 가 tmp 로 격리 → 시작은 비어 있음
    n = seed_if_empty()
    assert n > 0
    assert len(task_defs_db.list_all()) == n


def test_seed_is_idempotent():
    """이미 데이터가 있으면 건너뛴다(사용자 편집 덮어쓰기 방지)."""
    first = seed_if_empty()
    assert first > 0
    again = seed_if_empty()
    assert again == 0
    assert len(task_defs_db.list_all()) == first
