"""북마크 API — `store.bookmarks` 위임 (보관함 = 뉴스/제안/기회/작업 통합 저장소).

식별·감사 필드는 store 가 stamp 하며, 생성 시 행위자를 `Identity.user_id` 로 지정.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import Identity, current_identity
from api.schemas import (
    BookmarkCreateIn,
    BookmarkOut,
    BookmarkStatusIn,
    BookmarkUpdateIn,
)
from store import bookmarks

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


@router.get("", response_model=list[BookmarkOut])
def list_bookmarks(
    type: str | None = Query(default=None, description="타입 필터(news/proposal/...)"),
) -> list[BookmarkOut]:
    return [BookmarkOut.from_bookmark(b) for b in bookmarks.list_all(type_=type)]


@router.get("/summary")
def summary() -> dict:
    return bookmarks.summary_counts()


@router.post("", response_model=BookmarkOut, status_code=201)
def create_bookmark(
    body: BookmarkCreateIn,
    identity: Identity = Depends(current_identity),
) -> BookmarkOut:
    if body.type not in bookmarks.BOOKMARK_TYPES:
        raise HTTPException(status_code=422, detail=f"unknown type: {body.type}")
    bm_id = body.id or bookmarks.make_id(body.type, body.title, body.link)
    bm = bookmarks.Bookmark(
        id=bm_id, type=body.type, title=body.title,
        content=body.content, link=body.link, tags=body.tags,
        user_id=identity.user_id, workspace_id=identity.workspace_id,
        created_by=identity.user_id,
    )
    return BookmarkOut.from_bookmark(bookmarks.add(bm))


@router.patch("/{bm_id}", response_model=BookmarkOut)
def update_bookmark(bm_id: str, body: BookmarkUpdateIn) -> BookmarkOut:
    ok = bookmarks.update_content(
        bm_id, title=body.title, content=body.content, tags=body.tags
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"bookmark not found: {bm_id}")
    found = [b for b in bookmarks.list_all() if b.id == bm_id]
    return BookmarkOut.from_bookmark(found[0])


@router.post("/{bm_id}/status", response_model=BookmarkOut)
def set_status(bm_id: str, body: BookmarkStatusIn) -> BookmarkOut:
    try:
        ok = bookmarks.set_status(bm_id, body.status, note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail=f"bookmark not found: {bm_id}")
    found = [b for b in bookmarks.list_all() if b.id == bm_id]
    return BookmarkOut.from_bookmark(found[0])


@router.delete("/{bm_id}")
def delete_bookmark(bm_id: str) -> dict:
    if not bookmarks.remove(bm_id):
        raise HTTPException(status_code=404, detail=f"bookmark not found: {bm_id}")
    return {"deleted": True, "id": bm_id}
