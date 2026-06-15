"""작업 정의 API — `store.task_defs_db` 위임.

`docs/REACT_MIGRATION_PLAN.md §2/§3` 의 기준 엔드포인트. 다른 도메인 라우터의
레퍼런스 패턴: (1) `Identity` 의존성으로 행위자 주입, (2) store 직위임,
(3) 응답은 식별·감사 필드를 포함한 `*Out` 모델.
"""
from __future__ import annotations

import json as _json

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import Identity, current_identity
from api.schemas import DeletedOut, TaskDefHistoryOut, TaskDefOut, TaskDefUpsertIn
from store import task_defs_db

router = APIRouter(prefix="/api/taskdefs", tags=["taskdefs"])


@router.get("", response_model=list[TaskDefOut])
def list_taskdefs(
    team: str | None = Query(default=None),
    dept: str | None = Query(default=None),
    process: str | None = Query(default=None),
    q: str | None = Query(default=None, description="텍스트 검색(주어지면 필터 무시)"),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> list[TaskDefOut]:
    if q:
        rows = task_defs_db.search(q, limit=limit or 50)
    else:
        rows = task_defs_db.list_all(team=team, dept=dept, process=process, limit=limit)
    return [TaskDefOut.from_row(r) for r in rows]


@router.get("/{process_id}", response_model=TaskDefOut)
def get_taskdef(process_id: str) -> TaskDefOut:
    row = task_defs_db.get(process_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"task def not found: {process_id}")
    return TaskDefOut.from_row(row)


@router.put("/{process_id}", response_model=TaskDefOut)
def upsert_taskdef(
    process_id: str,
    body: TaskDefUpsertIn,
    identity: Identity = Depends(current_identity),
) -> TaskDefOut:
    try:
        row = task_defs_db.upsert(
            process_id,
            _json.dumps(body.json_def, ensure_ascii=False),
            task_def_text=body.task_def_text,
            changed_by=identity.user_id,
            source="api",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TaskDefOut.from_row(row)


@router.delete("/{process_id}", response_model=DeletedOut)
def delete_taskdef(
    process_id: str,
    identity: Identity = Depends(current_identity),
) -> DeletedOut:
    ok = task_defs_db.delete(process_id, changed_by=identity.user_id, source="api")
    if not ok:
        raise HTTPException(status_code=404, detail=f"task def not found: {process_id}")
    return DeletedOut(deleted=True, process_id=process_id)


@router.get("/{process_id}/history", response_model=list[TaskDefHistoryOut])
def taskdef_history(
    process_id: str,
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> list[TaskDefHistoryOut]:
    rows = task_defs_db.history(process_id, limit=limit)
    return [
        TaskDefHistoryOut(
            id=r["id"],
            process_id=r["process_id"],
            action=r["action"],
            changed_at=r["changed_at"],
            changed_by=r.get("changed_by"),
            source=r.get("source"),
        )
        for r in rows
    ]
