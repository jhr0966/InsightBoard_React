"""작업 정의(Task Definition) SQLite 저장소.

PR-1 — `docs/TASK_DEF_PLAN.md` Milestone M1 의 첫 번째 단계.

데이터 모델:
  - `task_defs`        — 작업 정의 본문 (process_id PK, json 전체 + scalar 미러)
  - `task_def_history` — 변경 이력 (create/update/delete + json_before/after)

설계 원칙:
  - JSON 컬럼이 single source of truth. scalar 컬럼(team/dept/...)은 index 용 미러.
  - `_connect()` 가 매 호출 새 연결을 열고 schema migration 을 호출 → 테스트 격리
    (conftest 의 `ROADMAP_DIR` monkeypatch 가 그대로 적용된다).
  - history 는 무한 누적. 정리는 future work.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from store.paths import roadmap_dir


# ── path & connection ──────────────────────────────────────

def db_path() -> Path:
    """SQLite 파일 경로. roadmap_dir() 가 호출 시점에 평가되므로 conftest 격리 안전."""
    return roadmap_dir() / "task_defs.db"


def _connect() -> sqlite3.Connection:
    """새 연결 + schema 보장. row_factory=Row 로 dict-like 접근."""
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(conn)
    return conn


# ── schema ─────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS task_defs (
  process_id    TEXT PRIMARY KEY,
  team          TEXT NOT NULL,
  dept          TEXT NOT NULL,
  division      TEXT,
  process       TEXT,
  task          TEXT,
  json          TEXT NOT NULL,
  task_def_text TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  created_by    TEXT,
  updated_by    TEXT
);
CREATE INDEX IF NOT EXISTS idx_task_defs_dept    ON task_defs(dept);
CREATE INDEX IF NOT EXISTS idx_task_defs_team    ON task_defs(team);
CREATE INDEX IF NOT EXISTS idx_task_defs_process ON task_defs(process);

CREATE TABLE IF NOT EXISTS task_def_history (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  process_id  TEXT NOT NULL,
  json_before TEXT,
  json_after  TEXT NOT NULL,
  action      TEXT NOT NULL,
  changed_at  TEXT NOT NULL,
  changed_by  TEXT,
  source      TEXT
);
CREATE INDEX IF NOT EXISTS idx_history_process ON task_def_history(process_id, changed_at DESC);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── validation helpers ─────────────────────────────────────

_ALLOWED_ACTIONS = frozenset({"create", "update", "delete"})

_REQUIRED_ORG_KEYS = ("team", "dept")  # NOT NULL in schema


def _parse_json(json_str: str) -> dict[str, Any]:
    try:
        obj = json.loads(json_str)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("task def JSON must be an object")
    return obj


def _scalars_from_json(json_str: str, process_id: str) -> dict[str, str | None]:
    """JSON.org_meta 에서 scalar 미러 필드를 추출. mismatch 검증."""
    obj = _parse_json(json_str)
    # process_id 동기화 확인
    json_pid = obj.get("process_id")
    if json_pid and json_pid != process_id:
        raise ValueError(
            f"process_id mismatch: arg={process_id!r} vs json.process_id={json_pid!r}"
        )
    meta = obj.get("org_meta")
    if not isinstance(meta, dict):
        raise ValueError("task def JSON must contain 'org_meta' object")
    for key in _REQUIRED_ORG_KEYS:
        if not meta.get(key):
            raise ValueError(f"org_meta.{key} is required (got {meta.get(key)!r})")
    return {
        "team":     str(meta.get("team") or ""),
        "dept":     str(meta.get("dept") or ""),
        "division": _opt(meta.get("division")),
        "process":  _opt(meta.get("process")),
        "task":     _opt(meta.get("task")),
    }


def _opt(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# ── public API ─────────────────────────────────────────────

def get(process_id: str) -> dict[str, Any] | None:
    """단일 작업 정의 — 없으면 None. json 필드는 dict 로 디코드해서 반환."""
    if not process_id:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM task_defs WHERE process_id = ?", (process_id,)
        ).fetchone()
    return _row_to_dict(row)


def upsert(
    process_id: str,
    json_str: str,
    *,
    task_def_text: str | None = None,
    changed_by: str | None = None,
    source: str = "ui_edit",
) -> dict[str, Any]:
    """작업 정의 신규 등록 또는 갱신. history 1건 자동 기록.

    Returns: 저장 후의 row(dict). action 은 'create' 또는 'update'.
    """
    if not process_id:
        raise ValueError("process_id is required")
    scalars = _scalars_from_json(json_str, process_id)
    now = _now_iso()
    with _connect() as conn:
        prev = conn.execute(
            "SELECT json, created_at, created_by FROM task_defs WHERE process_id = ?",
            (process_id,),
        ).fetchone()
        if prev is None:
            action = "create"
            conn.execute(
                """
                INSERT INTO task_defs
                  (process_id, team, dept, division, process, task,
                   json, task_def_text, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    process_id,
                    scalars["team"], scalars["dept"], scalars["division"],
                    scalars["process"], scalars["task"],
                    json_str, task_def_text,
                    now, now, changed_by, changed_by,
                ),
            )
            json_before = None
        else:
            action = "update"
            conn.execute(
                """
                UPDATE task_defs SET
                  team = ?, dept = ?, division = ?, process = ?, task = ?,
                  json = ?, task_def_text = ?, updated_at = ?, updated_by = ?
                WHERE process_id = ?
                """,
                (
                    scalars["team"], scalars["dept"], scalars["division"],
                    scalars["process"], scalars["task"],
                    json_str, task_def_text, now, changed_by,
                    process_id,
                ),
            )
            json_before = prev["json"]
        _record_history(
            conn, process_id,
            json_before=json_before, json_after=json_str,
            action=action, changed_at=now, changed_by=changed_by, source=source,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM task_defs WHERE process_id = ?", (process_id,)
        ).fetchone()
    return _row_to_dict(row)  # type: ignore[return-value]


def delete(
    process_id: str,
    *,
    changed_by: str | None = None,
    source: str = "ui_edit",
) -> bool:
    """삭제 — 존재하면 True, 없으면 False. history 에 'delete' 기록."""
    if not process_id:
        return False
    with _connect() as conn:
        prev = conn.execute(
            "SELECT json FROM task_defs WHERE process_id = ?", (process_id,)
        ).fetchone()
        if prev is None:
            return False
        now = _now_iso()
        _record_history(
            conn, process_id,
            json_before=prev["json"], json_after=prev["json"],
            action="delete", changed_at=now, changed_by=changed_by, source=source,
        )
        conn.execute("DELETE FROM task_defs WHERE process_id = ?", (process_id,))
        conn.commit()
    return True


def list_all(
    *,
    team: str | None = None,
    dept: str | None = None,
    process: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """필터 조합으로 작업 정의 목록 — updated_at 내림차순."""
    clauses: list[str] = []
    params: list[Any] = []
    if team:
        clauses.append("team = ?")
        params.append(team)
    if dept:
        clauses.append("dept = ?")
        params.append(dept)
    if process:
        clauses.append("process = ?")
        params.append(process)
    sql = "SELECT * FROM task_defs"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY updated_at DESC"
    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]  # type: ignore[misc]


def search(query: str, *, limit: int | None = 50) -> list[dict[str, Any]]:
    """text 검색 — process_id / process / task / json / task_def_text 매칭."""
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    sql = """
        SELECT * FROM task_defs
        WHERE process_id   LIKE ?
           OR process      LIKE ?
           OR task         LIKE ?
           OR json         LIKE ?
           OR task_def_text LIKE ?
        ORDER BY updated_at DESC
    """
    params: list[Any] = [like, like, like, like, like]
    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]  # type: ignore[misc]


def history(
    process_id: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """특정 process_id 의 history — 최신순."""
    if not process_id:
        return []
    sql = (
        "SELECT * FROM task_def_history WHERE process_id = ? "
        "ORDER BY changed_at DESC, id DESC"
    )
    params: list[Any] = [process_id]
    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count() -> int:
    """저장된 작업 정의 총 개수."""
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM task_defs").fetchone()
    return int(row["c"]) if row else 0


# ── internal helpers ───────────────────────────────────────

def _record_history(
    conn: sqlite3.Connection,
    process_id: str,
    *,
    json_before: str | None,
    json_after: str,
    action: str,
    changed_at: str,
    changed_by: str | None,
    source: str | None,
) -> None:
    if action not in _ALLOWED_ACTIONS:
        raise ValueError(f"invalid action: {action!r}")
    conn.execute(
        """
        INSERT INTO task_def_history
          (process_id, json_before, json_after, action, changed_at, changed_by, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (process_id, json_before, json_after, action, changed_at, changed_by, source),
    )


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    # json 컬럼은 디코드해서 별도 필드 'json_obj' 제공 (raw 'json' 도 유지)
    try:
        d["json_obj"] = json.loads(d["json"])
    except (TypeError, ValueError):
        d["json_obj"] = None
    return d
