"""대화 스레드 + 메시지 영구화 API — `store.sola_threads` / `store.chat_log` 위임.

어시스턴트 드로어가 스레드를 만들고(`POST /api/threads`), 메시지를 저장/복원
(`/api/threads/{id}/messages`)해 새로고침 후에도 대화가 보존된다. 메시지는
`chat_log` 의 chat_key = thread id 로 분리 저장.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from store import chat_log
from store import sola_threads as threads_store

router = APIRouter(prefix="/api/threads", tags=["threads"])


class ThreadCreateIn(BaseModel):
    title: str = ""


class ThreadUpdateIn(BaseModel):
    title: str | None = None
    pinned: bool | None = None


class MessagesIn(BaseModel):
    messages: list[dict]


def _out(t) -> dict:
    return asdict(t)


@router.get("")
def list_threads() -> list[dict]:
    return [_out(t) for t in threads_store.list_threads()]


@router.post("")
def create_thread(body: ThreadCreateIn) -> dict:
    return _out(threads_store.create(body.title))


@router.get("/{thread_id}")
def get_thread(thread_id: str) -> dict:
    t = threads_store.get(thread_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
    return _out(t)


@router.patch("/{thread_id}")
def update_thread(thread_id: str, body: ThreadUpdateIn) -> dict:
    t = threads_store.update(thread_id, title=body.title, pinned=body.pinned)
    if t is None:
        raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
    return _out(t)


@router.delete("/{thread_id}")
def delete_thread(thread_id: str) -> dict:
    if not threads_store.delete(thread_id):
        raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
    chat_log.reset(thread_id)
    return {"deleted": True, "id": thread_id}


@router.get("/{thread_id}/messages")
def get_messages(thread_id: str) -> list[dict]:
    return chat_log.load_history(chat_key=thread_id)


@router.put("/{thread_id}/messages")
def put_messages(thread_id: str, body: MessagesIn) -> dict:
    chat_log.save_history(body.messages, chat_key=thread_id)
    # 스레드 메시지 수 동기화(존재할 때만).
    if threads_store.get(thread_id) is not None:
        threads_store.update(thread_id, message_count=len(body.messages))
    return {"ok": True, "count": len(body.messages)}
