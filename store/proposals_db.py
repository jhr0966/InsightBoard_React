"""자동화 과제(Proposal) 엔터티 저장소 (SQLite) — 개편 Step 13 (계획 §15).

과거 제안서는 범용 bookmark(마크다운 문자열)에 저장돼 ①근거 복원 불가
②상태가 pending/adopted/rejected 3종뿐 ③전환 이력 없음이었다. 이제:

- **별도 엔터티**: 제안 내용(문서)과 실행 관리 필드를 논리 구분해 한 테이블에
  담되, 향후 Initiative(실행 과제) 분리가 가능하도록 `proposal_id` 는 안정적이고
  실행 필드는 독립 컬럼이다(§15 — MVP 단일 엔터티 허용 조건 준수).
- **상태 확장**: idea → draft → reviewing → feasibility → poc_ready →
  poc_running → adopted / on_hold / rejected.
- **전환 이력 보존**: `proposal_history` 에 모든 상태 변경 기록.
- **PoC 결과는 본문 문자열이 아닌 구조 필드**(poc_result·actual_effect).
- 기존 bookmark(type=proposal) 이관: `migrate_from_bookmarks()` — 원본 보존,
  `legacy=1`, 근거 meta 가 없으면 `evidence_unavailable=1` 표시(§11-3).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from store._audit import DEFAULT_USER, DEFAULT_WORKSPACE
from store.paths import roadmap_dir

# 제안 단계(proposal phase) → 실행 단계(execution phase) — Initiative 분리 대비 그룹.
PROPOSAL_PHASE = ("idea", "draft", "reviewing")
EXECUTION_PHASE = ("feasibility", "poc_ready", "poc_running", "adopted", "on_hold", "rejected")
STATUSES = PROPOSAL_PHASE + EXECUTION_PHASE

# 구 bookmark 3상태 → 신 상태 매핑(이관용).
_LEGACY_STATUS_MAP = {"pending": "reviewing", "adopted": "adopted", "rejected": "rejected"}

_JSON_COLS = ("article_ids", "case_ids", "expected_kpi")


def db_path() -> Path:
    return roadmap_dir() / "proposals.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
  proposal_id      TEXT PRIMARY KEY,
  title            TEXT NOT NULL,
  content          TEXT NOT NULL DEFAULT '',
  task_id          TEXT NOT NULL DEFAULT '',
  article_ids      TEXT NOT NULL DEFAULT '[]',
  case_ids         TEXT NOT NULL DEFAULT '[]',
  matching_version INTEGER NOT NULL DEFAULT 0,
  prompt_version   INTEGER NOT NULL DEFAULT 0,
  status           TEXT NOT NULL DEFAULT 'draft',
  owner            TEXT NOT NULL DEFAULT '',
  partner_depts    TEXT NOT NULL DEFAULT '',
  data_readiness   TEXT NOT NULL DEFAULT '',
  tech_readiness   TEXT NOT NULL DEFAULT '',
  est_cost         TEXT NOT NULL DEFAULT '',
  est_duration     TEXT NOT NULL DEFAULT '',
  expected_kpi     TEXT NOT NULL DEFAULT '[]',
  review_note      TEXT NOT NULL DEFAULT '',
  poc_result       TEXT NOT NULL DEFAULT '',
  actual_effect    TEXT NOT NULL DEFAULT '',
  legacy           INTEGER NOT NULL DEFAULT 0,
  evidence_unavailable INTEGER NOT NULL DEFAULT 0,
  user_id          TEXT NOT NULL DEFAULT 'local',
  workspace_id     TEXT NOT NULL DEFAULT 'default',
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposal_history (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  proposal_id  TEXT NOT NULL,
  from_status  TEXT NOT NULL,
  to_status    TEXT NOT NULL,
  note         TEXT NOT NULL DEFAULT '',
  changed_by   TEXT NOT NULL DEFAULT '',
  changed_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prop_hist ON proposal_history(proposal_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_out(r: dict) -> dict:
    for c in _JSON_COLS:
        try:
            r[c] = json.loads(r[c])
        except (TypeError, ValueError):
            r[c] = []
    r["legacy"] = bool(r.get("legacy"))
    r["evidence_unavailable"] = bool(r.get("evidence_unavailable"))
    return r


def create(
    *, title: str, content: str, task_id: str = "",
    article_ids: list[str] | None = None, case_ids: list[str] | None = None,
    matching_version: int = 0, prompt_version: int = 0,
    status: str = "draft", user: str = DEFAULT_USER, workspace: str = DEFAULT_WORKSPACE,
    legacy: bool = False, evidence_unavailable: bool = False,
    proposal_id: str | None = None, created_at: str | None = None,
) -> dict:
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    now = _now()
    pid = proposal_id or ("prop-" + uuid.uuid4().hex[:12])
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO proposals (proposal_id, title, content, task_id, "
            "article_ids, case_ids, matching_version, prompt_version, status, "
            "legacy, evidence_unavailable, user_id, workspace_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, title[:120], content, task_id,
             json.dumps(article_ids or [], ensure_ascii=False),
             json.dumps(case_ids or [], ensure_ascii=False),
             matching_version, prompt_version, status,
             int(legacy), int(evidence_unavailable), user, workspace,
             created_at or now, now))
        conn.execute(
            "INSERT INTO proposal_history (proposal_id, from_status, to_status, note, "
            "changed_by, changed_at) VALUES (?,?,?,?,?,?)",
            (pid, "", status, "생성", user, now))
    return get(pid)  # type: ignore[return-value]


def set_status(proposal_id: str, status: str, *, note: str = "",
               user: str = DEFAULT_USER) -> dict | None:
    """상태 전환 — 이력 보존(§15). 동일 상태로의 전환은 이력을 남기지 않는다."""
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    now = _now()
    with _connect() as conn:
        row = conn.execute("SELECT status FROM proposals WHERE proposal_id = ?",
                           (proposal_id,)).fetchone()
        if row is None:
            return None
        if row["status"] != status:
            conn.execute(
                "UPDATE proposals SET status = ?, review_note = CASE WHEN ? != '' THEN ? "
                "ELSE review_note END, updated_at = ? WHERE proposal_id = ?",
                (status, note, note, now, proposal_id))
            conn.execute(
                "INSERT INTO proposal_history (proposal_id, from_status, to_status, note, "
                "changed_by, changed_at) VALUES (?,?,?,?,?,?)",
                (proposal_id, row["status"], status, note, user, now))
    return get(proposal_id)


def update_fields(proposal_id: str, fields: dict) -> dict | None:
    """실행 관리 필드 갱신 — owner·협업부서·준비도·비용/기간·KPI·PoC 결과 등.

    PoC 결과는 본문(content)이 아니라 poc_result/actual_effect 구조 필드에(§15).
    """
    allowed = {"owner", "partner_depts", "data_readiness", "tech_readiness",
               "est_cost", "est_duration", "review_note", "poc_result",
               "actual_effect", "title", "content"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = ?")
        vals.append(str(v))
    if "expected_kpi" in fields and isinstance(fields["expected_kpi"], list):
        sets.append("expected_kpi = ?")
        vals.append(json.dumps(fields["expected_kpi"], ensure_ascii=False))
    if not sets:
        return get(proposal_id)
    vals += [_now(), proposal_id]
    with _connect() as conn:
        conn.execute(f"UPDATE proposals SET {', '.join(sets)}, updated_at = ? "
                     "WHERE proposal_id = ?", vals)
    return get(proposal_id)


def get(proposal_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM proposals WHERE proposal_id = ?",
                           (proposal_id,)).fetchone()
    return _row_out(dict(row)) if row else None


def list_all(*, user: str | None = None, status: str | None = None,
             limit: int = 200) -> list[dict]:
    q = "SELECT * FROM proposals"
    conds, vals = [], []
    if user is not None:
        conds.append("user_id = ?"); vals.append(user)
    if status is not None:
        conds.append("status = ?"); vals.append(status)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY updated_at DESC LIMIT ?"
    vals.append(limit)
    with _connect() as conn:
        return [_row_out(dict(r)) for r in conn.execute(q, vals)]


def history(proposal_id: str) -> list[dict]:
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM proposal_history WHERE proposal_id = ? ORDER BY id",
            (proposal_id,))]


def delete(proposal_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM proposals WHERE proposal_id = ?", (proposal_id,))
        conn.execute("DELETE FROM proposal_history WHERE proposal_id = ?", (proposal_id,))
        return cur.rowcount > 0


def summary(*, user: str | None = None) -> dict:
    items = list_all(user=user, limit=1000)
    by: dict[str, int] = {}
    for it in items:
        by[it["status"]] = by.get(it["status"], 0) + 1
    return {"total": len(items), "by_status": by,
            "reviewing": by.get("reviewing", 0), "adopted": by.get("adopted", 0)}


def migrate_from_bookmarks() -> dict:
    """기존 bookmark(type=proposal) → Proposal 엔터티 이관 (§11-3·§15).

    - 원본 bookmark 는 삭제하지 않는다(보존 — 재실행 가능).
    - proposal_id 를 bookmark id 에서 결정적으로 파생 → **재실행 멱등**.
    - Step 8 이후 meta 가 있으면 근거(article_ids 등) 복원, 없으면
      legacy=1 + evidence_unavailable=1 표시.
    """
    from store import bookmarks as bm_store

    migrated = skipped = 0
    for bm in bm_store.list_all(type_="proposal"):
        pid = "prop-bm-" + bm.id[-12:]
        if get(pid) is not None:
            skipped += 1
            continue
        meta = getattr(bm, "meta", {}) or {}
        has_evidence = bool(meta.get("article_ids"))
        create(
            proposal_id=pid,
            title=bm.title, content=bm.content,
            task_id=str(meta.get("task_id", "")),
            article_ids=[str(a) for a in (meta.get("article_ids") or [])],
            matching_version=int(meta.get("matching_version", 0) or 0),
            prompt_version=int(meta.get("prompt_version", 0) or 0),
            status=_LEGACY_STATUS_MAP.get(bm.status, "reviewing"),
            user=bm.user_id, workspace=bm.workspace_id,
            legacy=True, evidence_unavailable=not has_evidence,
            created_at=bm.created_at or None,
        )
        migrated += 1
    return {"migrated": migrated, "skipped": skipped}
