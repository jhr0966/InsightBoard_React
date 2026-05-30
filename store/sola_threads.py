"""SOLA 대화 thread 메타데이터 영구 저장.

A.3 까지는 `chat_log.save_history(messages, chat_key="sola_main")` 단일 키로
모든 대화가 한 파일에 누적됐다. B.4 는 thread 별 분리를 지원한다:

  - 각 thread 는 자체 `chat_key`(=thread.id) 로 `chat_log` 에 메시지 영구화
  - thread 메타데이터(제목/생성·갱신 시각/메시지 수/고정)는 이 모듈이 관리
  - 메타데이터 단일 파일: `data/sola/threads.json` (재현성·읽기 단순성 우선)
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from config import SOLA_DIR, ensure_data_dirs


# 후방 호환: A.3 의 단일 sola_main chat_key 를 자동 import 할 때 쓰는 thread id.
LEGACY_MAIN_THREAD_ID = "sola_main"

# 새 thread 의 기본 제목 — 첫 user 메시지로 자동 교체됨.
_DEFAULT_TITLE = "새 대화"

# 자동 제목 max 길이 (UTF-8 문자 단위, 시안 thread item 폭 기준).
_TITLE_MAX = 36


@dataclass
class Thread:
    id: str
    title: str = _DEFAULT_TITLE
    created_at: str = ""
    updated_at: str = ""
    message_count: int = 0
    pinned: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Thread":
        return cls(
            id=str(d.get("id", "")),
            title=str(d.get("title", _DEFAULT_TITLE)),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
            message_count=int(d.get("message_count", 0) or 0),
            pinned=bool(d.get("pinned", False)),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _index_path() -> Path:
    ensure_data_dirs()
    return SOLA_DIR / "threads.json"


def _read_all() -> list[Thread]:
    p = _index_path()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [Thread.from_dict(d) for d in raw if isinstance(d, dict) and d.get("id")]


def _write_all(threads: list[Thread]) -> None:
    p = _index_path()
    p.write_text(
        json.dumps([asdict(t) for t in threads], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _slug_id() -> str:
    """thread id — chat_log._safe_key 통과 가능한 슬러그 형식."""
    return "th_" + uuid.uuid4().hex[:12]


# ── public API ──────────────────────────────────────────────

def list_threads() -> list[Thread]:
    """모든 thread — pinned 가 위, 동일 그룹 안에선 updated_at 내림차순."""
    threads = _read_all()
    return sorted(
        threads,
        key=lambda t: (
            0 if t.pinned else 1,
            -_ts_sort_key(t.updated_at or t.created_at),
        ),
    )


def _ts_sort_key(iso: str) -> int:
    """ISO 문자열 → 정수 정렬키 (없으면 0)."""
    if not iso:
        return 0
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def get(thread_id: str) -> Thread | None:
    for t in _read_all():
        if t.id == thread_id:
            return t
    return None


def create(title: str = "") -> Thread:
    """새 thread 생성 + 영구화. id 는 자동 슬러그."""
    now = _now_iso()
    th = Thread(
        id=_slug_id(),
        title=(title or _DEFAULT_TITLE)[:_TITLE_MAX],
        created_at=now,
        updated_at=now,
    )
    all_ = _read_all()
    all_.append(th)
    _write_all(all_)
    return th


def update(thread_id: str, *, title: str | None = None,
           message_count: int | None = None, pinned: bool | None = None,
           touch: bool = True) -> Thread | None:
    """일부 필드 갱신. touch=True 면 updated_at 도 현재 시각으로."""
    all_ = _read_all()
    found: Thread | None = None
    for t in all_:
        if t.id == thread_id:
            if title is not None:
                t.title = title[:_TITLE_MAX] or _DEFAULT_TITLE
            if message_count is not None:
                t.message_count = max(0, int(message_count))
            if pinned is not None:
                t.pinned = bool(pinned)
            if touch:
                t.updated_at = _now_iso()
            found = t
            break
    if found:
        _write_all(all_)
    return found


def delete(thread_id: str) -> bool:
    """thread 삭제 + 메시지 파일도 함께 제거. 반환=실제 지웠는지."""
    all_ = _read_all()
    kept = [t for t in all_ if t.id != thread_id]
    if len(kept) == len(all_):
        return False
    _write_all(kept)
    # chat_log 도 정리 (있으면)
    from store import chat_log
    try:
        chat_log.reset(thread_id)
    except Exception:
        pass
    return True


def title_from_first_user_message(content: str) -> str:
    """첫 user 메시지로부터 자동 제목 — 줄바꿈은 공백, 앞에서 N자."""
    flat = " ".join((content or "").split())
    return flat[:_TITLE_MAX] or _DEFAULT_TITLE


def ensure_active(active_id: str | None = None) -> Thread:
    """active thread 보장 — 지정 id 가 있고 존재하면 그걸, 없으면 가장 최근, 없으면 새로 생성.

    Returns: 활성 thread.
    """
    if active_id:
        t = get(active_id)
        if t:
            return t
    threads = list_threads()
    if threads:
        return threads[0]
    return create()


def migrate_legacy_main_if_needed() -> Thread | None:
    """A.3 의 단일 'sola_main' chat_key 에 누적된 메시지를 첫 thread 로 마이그.

    - threads.json 이 비어있고
    - chat_log.load_history('sola_main') 이 메시지 있으면
    호출 — 자동 thread 1개 생성, 첫 user 메시지로 제목 set.
    반환: 마이그된 thread (없으면 None).
    """
    if _read_all():
        return None
    from store import chat_log
    legacy = chat_log.load_history(LEGACY_MAIN_THREAD_ID)
    if not legacy:
        return None
    # 첫 user 메시지로 제목
    title = _DEFAULT_TITLE
    for m in legacy:
        if m.get("role") == "user" and m.get("content"):
            title = title_from_first_user_message(m["content"])
            break
    now = _now_iso()
    th = Thread(
        id=_slug_id(),
        title=title,
        created_at=now,
        updated_at=now,
        message_count=len(legacy),
    )
    _write_all([th])
    # 메시지를 새 thread chat_key 로 복사 (기존 sola_main 파일은 유지 — 안전)
    chat_log.save_history(legacy, th.id)
    return th
