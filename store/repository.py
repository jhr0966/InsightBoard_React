"""영구화 백엔드 추상화 (Phase 2 교체 seam).

Phase 1 은 파일(JSONL) 기반. Phase 2 에서 PostgreSQL 등으로 옮길 때, **이 한 곳**
(`get_repository`)만 바꾸면 도메인 store(`bookmarks` 등)는 손대지 않는다.

- `Repository` 프로토콜 = Phase 2 구현이 만족해야 하는 계약(id 기반 CRUD + 식별 스코프).
- `JsonlRepository` = 현행 파일 구현(레코드당 1줄 JSONL, 식별·감사 필드 자동 stamp).
- `get_repository(name)` = `INSIGHTBOARD_STORAGE` env 로 백엔드 선택(기본 "file").

식별 스코프: `list(user_id=, workspace_id=)` 로 테넌트 분리(Phase 1 은 단일 사용자라
보통 전체 반환, Phase 2 인증이 채우면 자동으로 스코프된다).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

import config
from store._audit import backfill, stamp


@runtime_checkable
class Repository(Protocol):
    """id 기반 레코드 컬렉션 — Phase 2 백엔드가 구현해야 하는 계약."""

    def read_all(self) -> list[dict]: ...
    def write_all(self, records: list[dict]) -> None: ...
    def get(self, rid: str) -> dict | None: ...
    def upsert(self, record: dict, *, user: str = ..., workspace: str = ...) -> dict: ...
    def delete(self, rid: str) -> bool: ...
    def list(self, *, user_id: str | None = ..., workspace_id: str | None = ...) -> list[dict]: ...


class JsonlRepository:
    """레코드당 1줄 JSONL 컬렉션 (`<DATA_ROOT>/<name>/items.jsonl`).

    `config.DATA_ROOT` 를 **호출 시점에** 참조하므로 테스트(conftest)의 monkeypatch 가
    그대로 적용된다. 읽기 시 누락 식별필드는 `backfill`, upsert 는 `stamp`.
    """

    def __init__(self, name: str, *, id_key: str = "id"):
        self.name = name
        self.id_key = id_key

    def _path(self) -> Path:
        config.ensure_data_dirs()
        d = config.DATA_ROOT / self.name
        d.mkdir(parents=True, exist_ok=True)
        return d / "items.jsonl"

    def read_all(self) -> list[dict]:
        p = self._path()
        if not p.exists():
            return []
        out: list[dict] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(backfill(json.loads(line)))
            except json.JSONDecodeError:
                continue
        return out

    def write_all(self, records: list[dict]) -> None:
        p = self._path()
        with p.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False))
                f.write("\n")

    def get(self, rid: str) -> dict | None:
        for r in self.read_all():
            if str(r.get(self.id_key)) == str(rid):
                return r
        return None

    def upsert(self, record: dict, *, user: str = "local", workspace: str = "default") -> dict:
        rid = str(record.get(self.id_key))
        rec = stamp(dict(record), user=user, workspace=workspace)
        items = [r for r in self.read_all() if str(r.get(self.id_key)) != rid]
        items.append(rec)
        self.write_all(items)
        return rec

    def delete(self, rid: str) -> bool:
        items = self.read_all()
        kept = [r for r in items if str(r.get(self.id_key)) != str(rid)]
        if len(kept) == len(items):
            return False
        self.write_all(kept)
        return True

    def list(
        self,
        *,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[dict]:
        rows = self.read_all()
        if user_id is not None:
            rows = [r for r in rows if r.get("user_id") == user_id]
        if workspace_id is not None:
            rows = [r for r in rows if r.get("workspace_id") == workspace_id]
        return rows


def get_repository(name: str, *, id_key: str = "id") -> Repository:
    """name 컬렉션의 Repository — `INSIGHTBOARD_STORAGE` 로 백엔드 선택.

    Phase 1: "file"(기본) → JsonlRepository. Phase 2: "postgres" 등을 여기서 분기.
    """
    backend = os.getenv("INSIGHTBOARD_STORAGE", "file").strip().lower()
    if backend in ("", "file"):
        return JsonlRepository(name, id_key=id_key)
    raise NotImplementedError(
        f"storage backend '{backend}' 미구현 — Phase 2 에서 추가(현재 'file'만)."
    )
