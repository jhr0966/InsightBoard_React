"""사례 라이브러리 저장소 (SQLite) — 개편 Step 12 (계획 §14).

사례(case)는 **일반 뉴스 북마크가 아니라 별도 엔터티**다: 뉴스는 30일이면
뒤로 밀리지만, "○○사가 비전 AI 로 용접 검사를 자동화" 같은 사례는 정제해
쌓아두면 제안서의 근거 자산이 된다.

모델:
  - cases        : 정제된 사례 본문 + 검토 상태(review_status)
  - case_sources : 사례 ↔ 기사 **다대다** + 근거(evidence_text·evidence_type)
                   (MVP 추출은 기사 1건→사례 1건이지만 스키마는 다대다 —
                    같은 사례를 다룬 다른 기사를 나중에 붙일 수 있다)
  - 사례 ↔ 작업 연결은 별도 테이블 없이 **소스 기사의 links 를 경유**해 파생
    (기사→작업 매칭이 이미 article_task_links 에 있음 — 중복 저장 금지)

검토 상태 흐름(§14-3): pending_review(자동 추출 직후) → approved / excluded.
**approved 사례만 제안서의 주근거**로 주입된다(미검토는 화면 참고용).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from store.paths import roadmap_dir

REVIEW_STATUSES = ("pending_review", "approved", "excluded")
EVIDENCE_TYPES = ("source_fact", "system_summary", "shipyard_inference")

_JSON_COLS = ("technology_ids", "quantified_effects")


def db_path() -> Path:
    return roadmap_dir() / "cases.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  case_id             TEXT PRIMARY KEY,
  title               TEXT NOT NULL,
  industry            TEXT NOT NULL DEFAULT '',
  target_work         TEXT NOT NULL DEFAULT '',
  problem             TEXT NOT NULL DEFAULT '',
  solution            TEXT NOT NULL DEFAULT '',
  technology_ids      TEXT NOT NULL DEFAULT '[]',
  implementation      TEXT NOT NULL DEFAULT '',
  quantified_effects  TEXT NOT NULL DEFAULT '[]',
  shipyard_implications TEXT NOT NULL DEFAULT '',
  confidence          REAL NOT NULL DEFAULT 0,
  review_status       TEXT NOT NULL DEFAULT 'pending_review',
  extract_version     INTEGER NOT NULL DEFAULT 1,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_sources (
  case_id        TEXT NOT NULL,
  article_id     TEXT NOT NULL,
  link           TEXT NOT NULL DEFAULT '',
  title          TEXT NOT NULL DEFAULT '',
  evidence_text  TEXT NOT NULL DEFAULT '',
  evidence_type  TEXT NOT NULL DEFAULT 'system_summary',
  PRIMARY KEY (case_id, article_id)
);
CREATE INDEX IF NOT EXISTS idx_case_sources_article ON case_sources(article_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def case_id_for_article(article_id: str) -> str:
    """MVP 추출 단위 = 기사 1건 → 결정적 case_id (재실행 멱등)."""
    return "case-" + hashlib.md5(article_id.encode("utf-8")).hexdigest()[:12]


def _row_out(r: dict) -> dict:
    for c in _JSON_COLS:
        try:
            r[c] = json.loads(r[c])
        except (TypeError, ValueError):
            r[c] = []
    return r


def upsert_case(case: dict, sources: list[dict]) -> str:
    """사례 + 근거 소스 저장(멱등 — 같은 case_id 재추출 시 갱신, 상태는 보존).

    이미 검토(approved/excluded)된 사례는 재추출이 상태를 되돌리지 않는다.
    """
    now = _now()
    cid = str(case["case_id"])
    with _connect() as conn:
        prev = conn.execute("SELECT review_status, created_at FROM cases WHERE case_id = ?",
                            (cid,)).fetchone()
        status = prev["review_status"] if prev else str(
            case.get("review_status", "pending_review"))
        created = prev["created_at"] if prev else now
        conn.execute(
            "INSERT OR REPLACE INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, str(case.get("title", "")), str(case.get("industry", "")),
             str(case.get("target_work", "")), str(case.get("problem", "")),
             str(case.get("solution", "")),
             json.dumps(list(case.get("technology_ids") or []), ensure_ascii=False),
             str(case.get("implementation", "")),
             json.dumps(list(case.get("quantified_effects") or []), ensure_ascii=False),
             str(case.get("shipyard_implications", "")),
             float(case.get("confidence", 0) or 0), status,
             int(case.get("extract_version", 1) or 1), created, now))
        for s in sources:
            etype = s.get("evidence_type", "system_summary")
            if etype not in EVIDENCE_TYPES:
                etype = "system_summary"
            conn.execute(
                "INSERT OR REPLACE INTO case_sources VALUES (?,?,?,?,?,?)",
                (cid, str(s.get("article_id", "")), str(s.get("link", "")),
                 str(s.get("title", "")), str(s.get("evidence_text", "")), etype))
    return cid


def set_status(case_id: str, status: str) -> bool:
    if status not in REVIEW_STATUSES:
        raise ValueError(f"unknown review_status: {status}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE cases SET review_status = ?, updated_at = ? WHERE case_id = ?",
            (status, _now(), case_id))
        return cur.rowcount > 0


def get(case_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            return None
        out = _row_out(dict(row))
        out["sources"] = [dict(r) for r in conn.execute(
            "SELECT * FROM case_sources WHERE case_id = ?", (case_id,))]
    return out


def list_cases(*, status: str | None = None, technology_id: str | None = None,
               limit: int = 100) -> list[dict]:
    """사례 목록 — 최신 갱신순. status/기술 필터."""
    with _connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM cases ORDER BY updated_at DESC LIMIT ?", (max(limit * 3, limit),))]
        srcs: dict[str, list[dict]] = {}
        for r in conn.execute("SELECT * FROM case_sources"):
            srcs.setdefault(r["case_id"], []).append(dict(r))
    out = []
    for r in rows:
        r = _row_out(r)
        if status and r["review_status"] != status:
            continue
        if technology_id and technology_id not in r["technology_ids"]:
            continue
        r["sources"] = srcs.get(r["case_id"], [])
        out.append(r)
        if len(out) >= limit:
            break
    return out


def extracted_article_ids() -> set[str]:
    """이미 사례 추출을 시도한 기사 — 배치가 같은 기사를 다시 LLM 에 태우지 않게."""
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT article_id FROM case_sources").fetchall()
        rows2 = conn.execute("SELECT DISTINCT article_id FROM non_cases").fetchall() \
            if _table_exists(conn, "non_cases") else []
    return {r["article_id"] for r in rows} | {r["article_id"] for r in rows2}


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def mark_non_case(article_id: str) -> None:
    """LLM 이 '사례 아님' 판정한 기사 기록 — 재추출 낭비 방지."""
    with _connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS non_cases "
                     "(article_id TEXT PRIMARY KEY, decided_at TEXT NOT NULL)")
        conn.execute("INSERT OR REPLACE INTO non_cases VALUES (?, ?)", (article_id, _now()))


def approved_for_articles(article_ids: list[str]) -> list[dict]:
    """근거 기사 집합과 연결된 **승인** 사례 — 제안서 주근거 주입용(§14-3)."""
    if not article_ids:
        return []
    with _connect() as conn:
        q = ",".join("?" for _ in article_ids)
        rows = [dict(r) for r in conn.execute(
            f"SELECT DISTINCT c.* FROM cases c JOIN case_sources s ON c.case_id = s.case_id "
            f"WHERE s.article_id IN ({q}) AND c.review_status = 'approved' "
            f"ORDER BY c.confidence DESC", article_ids)]
    return [_row_out(r) for r in rows]


def summary() -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT review_status, COUNT(*) n FROM cases GROUP BY review_status").fetchall()
    by = {r["review_status"]: r["n"] for r in rows}
    return {"total": sum(by.values()), "by_status": by}
