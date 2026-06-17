"""작업 정의 API — `store.task_defs_db` 위임.

`docs/REACT_MIGRATION_PLAN.md §2/§3` 의 기준 엔드포인트. 다른 도메인 라우터의
레퍼런스 패턴: (1) `Identity` 의존성으로 행위자 주입, (2) store 직위임,
(3) 응답은 식별·감사 필드를 포함한 `*Out` 모델.
"""
from __future__ import annotations

import json as _json

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from api.deps import Identity, current_identity
from api.schemas import DeletedOut, TaskDefHistoryOut, TaskDefOut, TaskDefUpsertIn
from roadmap.ingest import ingest_excel
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


@router.post("/upload/preview")
def preview_upload(
    file: UploadFile,
    _identity: Identity = Depends(current_identity),
) -> dict:
    """엑셀 업로드 **미리보기** — 저장하지 않고 기존과 diff(신규/갱신/삭제될 항목).

    `removed` 는 replace=true(교체)로 업로드 시 사라질 기존 작업정의 — 파괴적
    동작 전 확인용. 검증 실패 시 422.
    """
    from roadmap.ingest import preview_excel

    try:
        result = preview_excel(file.file)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail={"errors": [f"엑셀 파싱 실패: {exc}"]}) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", [])})
    return result


@router.post("/upload")
def upload_taskdefs(
    file: UploadFile,
    replace: bool = Query(default=False, description="true=기존 데이터셋 교체"),
    _identity: Identity = Depends(current_identity),
) -> dict:
    """공정정의서 엑셀 업로드 → 정규화 + bulk upsert(`roadmap.ingest`).

    `replace=true` 면 기존 작업정의를 비우고 새 데이터셋으로 교체("한 번 더 업로드 = 교체").
    """
    try:
        result = ingest_excel(file.file, replace=replace)
    except Exception as exc:  # noqa: BLE001 — 손상 파일 등 파싱 실패 → 422
        raise HTTPException(status_code=422, detail={"errors": [f"엑셀 파싱 실패: {exc}"]}) from exc
    payload = asdict(result)
    if not result.ok:
        raise HTTPException(status_code=422, detail={"errors": result.errors})
    return payload


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
