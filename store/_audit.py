"""식별·감사 필드 표준 (`docs/REACT_PREP_INVENTORY.md §4`).

모든 영구화 레코드는 write 직전 `stamp()` 를 통과시켜 아래 5필드를 보장한다:

    user_id      소유 사용자        Phase1 기본 "local"
    workspace_id 테넌트/작업공간    Phase1 기본 "default"
    created_by   행위자(감사)       Phase1 기본 "local"
    created_at   생성 UTC ISO8601
    updated_at   갱신 UTC ISO8601

Phase 1 은 단일 사용자라 값이 상수 기본값이지만, **필드는 지금부터 존재**시켜
Phase 2(Postgres·멀티유저) 이전 시 스키마 변경을 0 에 가깝게 만든다. 인증
미들웨어가 붙으면 호출부가 `user=`/`workspace=` 를 넘기는 것만으로 그대로 흐른다.
"""
from __future__ import annotations

from datetime import datetime, timezone

DEFAULT_USER = "local"
DEFAULT_WORKSPACE = "default"

#: 모든 영구화 레코드가 가져야 하는 식별·감사 필드.
AUDIT_FIELDS: tuple[str, ...] = (
    "user_id",
    "workspace_id",
    "created_by",
    "created_at",
    "updated_at",
)


def now_iso() -> str:
    """UTC ISO8601 (초 단위). 모든 store 의 타임스탬프 단일 진입점."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stamp(
    record: dict,
    *,
    user: str = DEFAULT_USER,
    workspace: str = DEFAULT_WORKSPACE,
    now: str | None = None,
) -> dict:
    """레코드(dict)에 식별·감사 5필드를 보장 (in-place + 반환).

    - 신규(`created_at` 없음): 5필드 모두 채움.
    - 기존(`created_at` 있음): `created_*`/`user_id`/`workspace_id` 보존, `updated_at` 만 갱신.

    dict 가 아니면 그대로 반환(no-op).
    """
    if not isinstance(record, dict):
        return record
    ts = now or now_iso()
    is_new = not record.get("created_at")
    record.setdefault("user_id", user)
    record.setdefault("workspace_id", workspace)
    if is_new:
        record["created_by"] = record.get("created_by") or user
        record["created_at"] = ts
    else:
        record.setdefault("created_by", user)
    record["updated_at"] = ts
    return record


def backfill(
    record: dict,
    *,
    user: str = DEFAULT_USER,
    workspace: str = DEFAULT_WORKSPACE,
) -> dict:
    """읽기 시 과거 레코드에 누락된 식별·감사 필드를 기본값으로 채움 (갱신 X).

    `stamp()` 와 달리 `updated_at` 을 현재 시각으로 바꾸지 않는다 — 읽기는 부작용이
    없어야 하므로 누락분만 기본값으로 메운다.
    """
    if not isinstance(record, dict):
        return record
    record.setdefault("user_id", user)
    record.setdefault("workspace_id", workspace)
    record.setdefault("created_by", user)
    record.setdefault("created_at", "")
    record.setdefault("updated_at", record.get("created_at", ""))
    return record
