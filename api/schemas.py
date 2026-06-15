"""API 공통 Pydantic 스키마.

모든 영구화 리소스 응답은 `AuditedModel` 을 상속해 식별·감사 5필드를 노출한다
(`store/_audit.py` 표준). 클라이언트(React)는 처음부터 이 필드를 인지하므로,
Phase 2 멀티유저 전환 시 응답 형태가 바뀌지 않는다.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditedModel(BaseModel):
    """식별·감사 5필드 (store/_audit.AUDIT_FIELDS)."""
    user_id: str = "local"
    workspace_id: str = "default"
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TaskDefOut(AuditedModel):
    """작업 정의 응답. `json` 은 디코드된 객체로 노출(store 의 json_obj).

    Python 속성은 `json_def` 지만 직렬화 키는 alias `"json"` — BaseModel.json()
    메서드 shadowing 경고를 피하면서 계약 키는 `json` 으로 유지.
    """
    model_config = ConfigDict(populate_by_name=True)

    process_id: str
    team: Optional[str] = None
    dept: Optional[str] = None
    division: Optional[str] = None
    process: Optional[str] = None
    task: Optional[str] = None
    json_def: dict[str, Any] | None = Field(
        default=None, alias="json", description="작업 정의 본문(디코드됨)"
    )
    task_def_text: Optional[str] = None
    updated_by: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TaskDefOut":
        """store.task_defs_db 의 row(dict) → 응답 모델."""
        return cls(
            process_id=row.get("process_id", ""),
            team=row.get("team"),
            dept=row.get("dept"),
            division=row.get("division"),
            process=row.get("process"),
            task=row.get("task"),
            json_def=row.get("json_obj"),
            task_def_text=row.get("task_def_text"),
            user_id=row.get("user_id") or "local",
            workspace_id=row.get("workspace_id") or "default",
            created_by=row.get("created_by"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            updated_by=row.get("updated_by"),
        )


class TaskDefUpsertIn(BaseModel):
    """작업 정의 생성/갱신 요청 본문. `json` 은 작업 정의 전체 객체."""
    model_config = ConfigDict(populate_by_name=True)

    json_def: dict[str, Any] = Field(
        ..., alias="json", description="작업 정의 본문(org_meta 포함)"
    )
    task_def_text: Optional[str] = None


class TaskDefHistoryOut(BaseModel):
    id: int
    process_id: str
    action: str
    changed_at: str
    changed_by: Optional[str] = None
    source: Optional[str] = None


class DeletedOut(BaseModel):
    deleted: bool
    process_id: str


# ── bookmarks ──────────────────────────────────────────────

class BookmarkOut(AuditedModel):
    """북마크 응답 (store.bookmarks.Bookmark)."""
    id: str
    type: str
    title: str
    content: str = ""
    link: str = ""
    tags: list[str] = Field(default_factory=list)
    status: str = "pending"
    decision_note: str = ""
    decided_at: str = ""

    @classmethod
    def from_bookmark(cls, bm: Any) -> "BookmarkOut":
        d = bm.to_dict()
        return cls(**d)


class BookmarkCreateIn(BaseModel):
    type: str = Field(..., description="news | proposal | opportunity | task")
    title: str
    content: str = ""
    link: str = ""
    tags: list[str] = Field(default_factory=list)
    id: Optional[str] = Field(default=None, description="생략 시 내용 해시로 생성")


class BookmarkUpdateIn(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None


class BookmarkStatusIn(BaseModel):
    status: str = Field(..., description="pending | adopted | rejected")
    note: str = ""
