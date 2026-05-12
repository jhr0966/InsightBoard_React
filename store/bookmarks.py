"""북마크 영구화 (`data/bookmarks/items.jsonl`).

작은 데이터셋(수백~수천) 가정. 매 변경 시 전체 rewrite.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_ROOT, ensure_data_dirs


BOOKMARK_TYPES = ("news", "proposal", "opportunity", "task")


@dataclass
class Bookmark:
    id: str
    type: str
    title: str
    content: str = ""
    link: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Bookmark":
        return cls(
            id=str(data.get("id", "")),
            type=str(data.get("type", "")),
            title=str(data.get("title", "")),
            content=str(data.get("content", "")),
            link=str(data.get("link", "")),
            tags=list(data.get("tags", []) or []),
            created_at=str(data.get("created_at", "")),
        )


def _path() -> Path:
    ensure_data_dirs()
    d = DATA_ROOT / "bookmarks"
    d.mkdir(parents=True, exist_ok=True)
    return d / "items.jsonl"


def make_id(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def list_all(*, type_: str | None = None) -> list[Bookmark]:
    p = _path()
    if not p.exists():
        return []
    items: list[Bookmark] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        bm = Bookmark.from_dict(obj)
        if type_ is None or bm.type == type_:
            items.append(bm)
    return items


def _write_all(items: list[Bookmark]) -> None:
    p = _path()
    with p.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it.to_dict(), ensure_ascii=False))
            f.write("\n")


def add(bm: Bookmark) -> Bookmark:
    if not bm.created_at:
        bm.created_at = _utc_now_iso()
    items = list_all()
    items = [it for it in items if it.id != bm.id]
    items.append(bm)
    _write_all(items)
    return bm


def remove(bm_id: str) -> bool:
    items = list_all()
    new_items = [it for it in items if it.id != bm_id]
    if len(new_items) == len(items):
        return False
    _write_all(new_items)
    return True


def has(bm_id: str) -> bool:
    return any(it.id == bm_id for it in list_all())


def clear() -> int:
    items = list_all()
    _write_all([])
    return len(items)
