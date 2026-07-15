"""기사↔작업 관계 저장소 (article_task_links, SQLite) — 개편 Step 6.

`store.match.score_matches` 결과(점수+**결정적 매칭 이유**)를 시스템 공통
자산으로 저장한다. 개인화 피드·"왜 내 업무 관련"·제안서 근거·히트맵·기회
매트릭스가 이 저장본을 공유 — 과거처럼 화면 요청마다 전체 코퍼스를 재계산하지
않는다.

동작 방식 — **write-through 캐시 + 버전 stale 재빌드**:
  `matches_for_window(news_df, roadmap_df, days=N)` 는 윈도우 시그니처
  (기사 article_id 집합 + 작업 키 집합 + MATCHING_VERSION + IDENTITY_VERSION)
  가 저장 상태와 같으면 **저장본을 읽고**, 다르면(새 수집·알고리즘/식별 규칙
  변경) 라이브로 계산해 저장한 뒤 반환한다. 따라서:
    - 수집 API 내부에서 동기 인덱싱을 하지 않는다(계획 §9-1) — 수집은 저장만.
    - 선워밍 경로: ① 일일 cron(`scripts/daily_scrape.py`) 말미 `rebuild()`
      ② 관리자 API `POST /api/matches/rebuild-links`.
    - 실패 복구: 저장 실패 시 라이브 결과를 그대로 반환(조회는 항상 성공),
      다음 호출이 재시도. 파생 데이터라 언제든 전체 재빌드 가능(원본 무손실).

저장 top_k 는 20(최대 소비자 기준) + `rank` 컬럼 — 소비자별 top_k 는
`slice_top_k()` 로 자른다(라이브 top_k=k 결과와 동일 순서 보장).
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from store import taxonomy
from store.article_id import IDENTITY_VERSION, article_id
from store.match import DEFAULT_SEMANTIC_WEIGHT, MATCHING_VERSION, score_matches
from store.paths import roadmap_dir

logger = logging.getLogger(__name__)

# 저장 top_k — 최대 소비자(히트맵 20) 기준. 소비자별로 slice_top_k 로 자른다.
STORE_TOP_K = 20

_JSON_COLS = ("score_components", "matched_terms", "matched_fields", "technology_ids")


def db_path() -> Path:
    """roadmap_dir() 를 호출 시점에 평가 — conftest 격리 안전 (task_defs_db 패턴)."""
    return roadmap_dir() / "article_task_links.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS article_task_links (
  window_days      INTEGER NOT NULL,
  task_key         TEXT NOT NULL,
  article_id       TEXT NOT NULL,
  link             TEXT NOT NULL,
  news_title       TEXT NOT NULL DEFAULT '',
  dept             TEXT NOT NULL DEFAULT '',
  lv1              TEXT NOT NULL DEFAULT '',
  lv2              TEXT NOT NULL DEFAULT '',
  lv3              TEXT NOT NULL DEFAULT '',
  task             TEXT NOT NULL DEFAULT '',
  sub_task         TEXT NOT NULL DEFAULT '',
  relevance_score  REAL NOT NULL DEFAULT 0,
  rank             INTEGER NOT NULL DEFAULT 0,
  score_components TEXT NOT NULL DEFAULT '{}',
  matched_terms    TEXT NOT NULL DEFAULT '[]',
  matched_fields   TEXT NOT NULL DEFAULT '[]',
  technology_ids   TEXT NOT NULL DEFAULT '[]',
  matching_version INTEGER NOT NULL,
  identity_version INTEGER NOT NULL,
  created_at       TEXT NOT NULL,
  PRIMARY KEY (window_days, task_key, article_id)
);
CREATE INDEX IF NOT EXISTS idx_links_article ON article_task_links(article_id);
CREATE TABLE IF NOT EXISTS links_index_state (
  window_days      INTEGER PRIMARY KEY,
  sig              TEXT NOT NULL,
  matching_version INTEGER NOT NULL,
  identity_version INTEGER NOT NULL,
  built_at         TEXT NOT NULL,
  article_count    INTEGER NOT NULL,
  link_count       INTEGER NOT NULL
);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    # 마이그레이션 — CREATE TABLE IF NOT EXISTS 는 기존 테이블에 새 컬럼을 못 넣는다.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(article_task_links)")}
    if "technology_ids" not in cols:
        conn.execute("ALTER TABLE article_task_links "
                     "ADD COLUMN technology_ids TEXT NOT NULL DEFAULT '[]'")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _task_key(row: dict) -> str:
    return "||".join(str(row.get(k, "") or "") for k in ("dept", "lv3", "task", "sub_task"))


def _window_sig(news_df: pd.DataFrame, roadmap_df: pd.DataFrame) -> str:
    """윈도우 시그니처 — 기사·작업 집합 또는 버전이 바뀌면 stale."""
    ids = (sorted(news_df["article_id"].astype(str))
           if "article_id" in news_df.columns
           else sorted(article_id(str(l)) for l in news_df.get("link", pd.Series(dtype=str))))
    tkeys = sorted(_task_key(r) for r in roadmap_df.to_dict("records"))
    payload = json.dumps(
        [ids, tkeys, MATCHING_VERSION, IDENTITY_VERSION,
         taxonomy.TAXONOMY_VERSION, STORE_TOP_K],
        ensure_ascii=False,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _store(days: int, sig: str, matches: pd.DataFrame,
           tech_tags: dict[str, list[str]] | None = None) -> None:
    """윈도우의 links 를 원자적으로 교체 저장 (파생 데이터 — 재실행 가능)."""
    now = _now_iso()
    tech_tags = tech_tags or {}
    rows = []
    if not matches.empty:
        rank = matches.groupby(["dept", "lv3", "task", "sub_task"]).cumcount() + 1
        for (_, m), rk in zip(matches.iterrows(), rank):
            link = str(m.get("link", ""))
            rows.append((
                days, _task_key(m), article_id(link), link,
                str(m.get("news_title", "")), str(m.get("dept", "")), str(m.get("lv1", "")),
                str(m.get("lv2", "")), str(m.get("lv3", "")), str(m.get("task", "")),
                str(m.get("sub_task", "")), float(m.get("score", 0) or 0), int(rk),
                json.dumps(m.get("score_components") or {}, ensure_ascii=False),
                json.dumps(list(m.get("matched_terms") or []), ensure_ascii=False),
                json.dumps(list(m.get("matched_fields") or []), ensure_ascii=False),
                json.dumps(tech_tags.get(link, []), ensure_ascii=False),
                MATCHING_VERSION, IDENTITY_VERSION, now,
            ))
    with _connect() as conn:
        conn.execute("DELETE FROM article_task_links WHERE window_days = ?", (days,))
        conn.executemany(
            "INSERT OR REPLACE INTO article_task_links VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        conn.execute(
            "INSERT OR REPLACE INTO links_index_state VALUES (?,?,?,?,?,?,?)",
            (days, sig, MATCHING_VERSION, IDENTITY_VERSION, now,
             int(matches["link"].nunique()) if not matches.empty else 0, len(rows)))


def _load(days: int) -> pd.DataFrame:
    with _connect() as conn:
        # rowid = 삽입 순서 = score_matches 방출 순서 — 라이브 결과와 순서 동일 보장.
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM article_task_links WHERE window_days = ? "
            "ORDER BY rowid", (days,))]
    for r in rows:
        for c in _JSON_COLS:
            try:
                r[c] = json.loads(r[c])
            except (TypeError, ValueError):
                r[c] = {} if c == "score_components" else []
        r["score"] = r.pop("relevance_score")
    return pd.DataFrame(rows)


def matches_for_window(
    news_df: pd.DataFrame,
    roadmap_df: pd.DataFrame,
    *,
    days: int,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
    force: bool = False,
) -> pd.DataFrame:
    """윈도우의 기사↔작업 매칭 — 저장본 우선, stale/미존재 시 계산·저장.

    반환: score_matches 컬럼 + `rank`(작업 내 순위 1..STORE_TOP_K).
    저장이 실패해도 라이브 결과를 반환한다(조회 불변식: 항상 성공).
    """
    if news_df.empty or roadmap_df.empty:
        return pd.DataFrame()
    sig = _window_sig(news_df, roadmap_df)
    if not force:
        try:
            with _connect() as conn:
                st = conn.execute(
                    "SELECT sig FROM links_index_state WHERE window_days = ?",
                    (days,)).fetchone()
            if st is not None and st["sig"] == sig:
                stored = _load(days)
                if not stored.empty:
                    return stored
        except sqlite3.Error:
            logger.warning("links 저장본 읽기 실패 — 라이브 계산으로 폴백", exc_info=True)
    live = score_matches(news_df, roadmap_df, top_k=STORE_TOP_K,
                         semantic_weight=semantic_weight)
    # 기술 태깅(taxonomy ID — 문자열 아님, 계획 §10) — 기사 텍스트에서 alias 매칭.
    tags: dict[str, list[str]] = {}
    if not live.empty:
        text_cols = [c for c in ("title", "summary", "keywords", "keywords_llm", "content")
                     if c in news_df.columns]
        for rec in news_df.to_dict("records"):
            link = str(rec.get("link", ""))
            if link:
                tags[link] = taxonomy.tag_text(" ".join(str(rec.get(c, "")) for c in text_cols))
    try:
        _store(days, sig, live, tags)
    except sqlite3.Error:
        logger.warning("links 저장 실패 — 다음 조회에서 재시도", exc_info=True)
    if live.empty:
        return live
    live = live.copy()
    live["rank"] = live.groupby(["dept", "lv3", "task", "sub_task"]).cumcount() + 1
    live["article_id"] = live["link"].map(lambda l: article_id(str(l)))
    live["technology_ids"] = live["link"].map(lambda l: tags.get(str(l), []))
    return live


def slice_top_k(matches: pd.DataFrame, top_k: int) -> pd.DataFrame:
    """저장 top_k(20) 결과에서 소비자별 상위 k 만 — 라이브 top_k=k 와 동일 순서."""
    if matches.empty or "rank" not in matches.columns:
        return matches
    return matches[matches["rank"] <= top_k]


def rebuild(days: int = 30) -> dict:
    """강제 재빌드 (일일 cron 말미·관리자 API 용). 결과 요약 dict 반환."""
    from roadmap import query as roadmap_query
    from store import news_db

    news = news_db.load_news_for_days(days)
    roadmap = roadmap_query.load_latest()
    if news.empty or roadmap.empty:
        return {"built": False, "reason": "뉴스 또는 작업정의 없음",
                "articles": int(len(news)), "tasks": int(len(roadmap))}
    df = matches_for_window(news, roadmap, days=days, force=True)
    return {"built": True, "days": days, "links": int(len(df)),
            "articles": int(news["article_id"].nunique() if "article_id" in news.columns else len(news)),
            "matching_version": MATCHING_VERSION, "identity_version": IDENTITY_VERSION}


def index_status() -> list[dict]:
    """윈도우별 인덱스 상태 — 관리 화면·헬스 점검용."""
    try:
        with _connect() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM links_index_state ORDER BY window_days")]
    except sqlite3.Error:
        return []
    for r in rows:
        r["stale"] = (r["matching_version"] != MATCHING_VERSION
                      or r["identity_version"] != IDENTITY_VERSION)
    return rows


def links_for_article(aid: str, *, days: int = 30, top_k: int = 5) -> list[dict]:
    """기사 1건이 연결된 작업 목록 — "왜 내 업무와 관련 있는가"(Step 9)의 원자료."""
    with _connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM article_task_links WHERE window_days = ? AND article_id = ? "
            "ORDER BY relevance_score DESC LIMIT ?", (days, aid, top_k))]
    for r in rows:
        for c in _JSON_COLS:
            try:
                r[c] = json.loads(r[c])
            except (TypeError, ValueError):
                r[c] = {} if c == "score_components" else []
    return rows
