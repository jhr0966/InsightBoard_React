"""북마크 영구화 (`data/bookmarks/items.jsonl`).

작은 데이터셋(수백~수천) 가정. 매 변경 시 전체 rewrite.

상태/만료 정책
---------------
제안서(`type == "proposal"`) 북마크는 의사결정 상태를 가진다:
  - `pending`  — 작성 후 검토 중 (기본값)
  - `adopted`  — 채택 (영구 보존)
  - `rejected` — 거절

`expire_old(days=N)` 는 `created_at` 기준 N일 지난 항목 중
`status != "adopted"` 인 것만 삭제한다. 즉 **채택된 제안서는 만료되지 않는다.**
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DATA_ROOT, ensure_data_dirs


BOOKMARK_TYPES = ("news", "proposal", "opportunity", "task")
BOOKMARK_STATUSES = ("pending", "adopted", "rejected")
DEFAULT_EXPIRE_DAYS = 30


@dataclass
class Bookmark:
    id: str
    type: str
    title: str
    content: str = ""
    link: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    # 의사결정 상태 (제안서 전용 의미를 가지지만 모든 타입에 존재).
    status: str = "pending"
    decision_note: str = ""
    decided_at: str = ""  # status 가 마지막으로 변한 시점 (UTC ISO)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Bookmark":
        status = str(data.get("status") or "pending")
        if status not in BOOKMARK_STATUSES:
            status = "pending"
        return cls(
            id=str(data.get("id", "")),
            type=str(data.get("type", "")),
            title=str(data.get("title", "")),
            content=str(data.get("content", "")),
            link=str(data.get("link", "")),
            tags=list(data.get("tags", []) or []),
            created_at=str(data.get("created_at", "")),
            status=status,
            decision_note=str(data.get("decision_note", "")),
            decided_at=str(data.get("decided_at", "")),
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


def summary_counts(items: list[Bookmark] | None = None) -> dict[str, dict[str, int] | int]:
    """Return lightweight archive counts by type and proposal decision status."""
    use_items = list_all() if items is None else items
    by_type = {typ: 0 for typ in BOOKMARK_TYPES}
    by_status = {status: 0 for status in BOOKMARK_STATUSES}
    for item in use_items:
        by_type[item.type] = by_type.get(item.type, 0) + 1
        if item.type == "proposal":
            by_status[item.status] = by_status.get(item.status, 0) + 1
    return {
        "total": len(use_items),
        "by_type": by_type,
        "proposal_status": by_status,
    }


def add(bm: Bookmark) -> Bookmark:
    if not bm.created_at:
        bm.created_at = _utc_now_iso()
    items = list_all()
    items = [it for it in items if it.id != bm.id]
    items.append(bm)
    _write_all(items)
    return bm


def update_content(
    bm_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Update editable bookmark fields in-place. Returns True when found."""
    items = list_all()
    changed = False
    for it in items:
        if it.id == bm_id:
            if title is not None:
                it.title = title
            if content is not None:
                it.content = content
            if tags is not None:
                it.tags = tags
            changed = True
            break
    if changed:
        _write_all(items)
    return changed


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


def list_adopted_proposals(*, limit: int = 5) -> list[Bookmark]:
    """채택된 제안서를 가장 최근 결정 순으로 N건 반환.

    채팅 컨텍스트에 "지난 사이클 결정"으로 자동 노출하기 위한 헬퍼.
    `decided_at` 우선, 없으면 `created_at` 으로 정렬.
    """
    items = [b for b in list_all(type_="proposal") if b.status == "adopted"]
    items.sort(key=lambda b: b.decided_at or b.created_at, reverse=True)
    return items[:limit]


def set_status(bm_id: str, status: str, *, note: str = "") -> bool:
    """북마크 의사결정 상태를 갱신. 변경되면 True.

    - `status` 가 BOOKMARK_STATUSES 밖이면 ValueError.
    - 동일 status 로 재설정하면 메모만 갱신. decided_at 은 항상 현재 시각으로 갱신.
    """
    if status not in BOOKMARK_STATUSES:
        raise ValueError(f"unknown status: {status!r}, expected one of {BOOKMARK_STATUSES}")
    items = list_all()
    changed = False
    for it in items:
        if it.id == bm_id:
            it.status = status
            it.decision_note = note
            it.decided_at = _utc_now_iso()
            changed = True
            break
    if changed:
        _write_all(items)
    return changed


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        # 표준 ISO 처리. 끝에 Z 가 붙은 옛 표기도 허용.
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def expire_old(
    *,
    days: int = DEFAULT_EXPIRE_DAYS,
    types: tuple[str, ...] = ("proposal",),
    now: datetime | None = None,
) -> int:
    """만료 정책: `created_at` 기준 `days` 일 지나고 `status != "adopted"` 인 항목 삭제.

    - `types` 가 주어지면 그 타입만 대상. 기본은 제안서만.
    - `created_at` 이 비어있거나 파싱 실패한 항목은 보존(만료 대상 아님).
    - `now` 는 테스트 주입용. 기본은 UTC 현재 시각.
    - 반환: 삭제된 항목 수.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    items = list_all()
    keep: list[Bookmark] = []
    removed = 0
    for it in items:
        if types and it.type not in types:
            keep.append(it)
            continue
        if it.status == "adopted":
            keep.append(it)
            continue
        created = _parse_iso(it.created_at)
        if created is None:
            # 파싱 불가 → 안전하게 보존
            keep.append(it)
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < cutoff:
            removed += 1
            continue
        keep.append(it)

    if removed:
        _write_all(keep)
    return removed
