"""로드맵 정규화 DataFrame → `store.task_defs_db` SQLite 동기화 (PR-3).

`docs/TASK_DEF_PLAN.md` M1. 기존 Parquet 흐름은 그대로 두고(=PR-4 가 reader 전환),
ingest/마이그 시점에 행 단위로 task_def JSON 을 빌드해 SQLite 에 UPSERT 한다.

process_id 결정 우선순위:
  1. `process_id` 컬럼 (신버전 9 컬럼 폼 "공정ID")
  2. `task_def_json` 컬럼 안의 `process_id` 필드
둘 다 없으면 PK 가 없으므로 skip (마이그/ingest 가 카운트로 보고).

org_meta 주입: team/dept/division/process/task/sub_task/lv1/lv2/lv3.
team/dept 가 비면 그 행은 skip (SQLite NOT NULL 위반 방지).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from roadmap.task_def_json import (
    ORG_META_KEYS,
    TaskDefJsonError,
    ingest_org_meta,
)


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    @property
    def total_written(self) -> int:
        return self.created + self.updated


@dataclass
class DiffPreview:
    """엑셀 업로드 적용 전 변경 사항 미리보기 (PR-5).

    fields:
      added:   업로드에 있지만 DB 에 없는 process_id 리스트
      updated: 양쪽 모두 있으나 JSON 이 다른 항목 [(pid, name), ...]
      unchanged: 동일한 JSON
      kept:    DB 에 있지만 업로드에 없는 (유지될) 항목 [(pid, name), ...]
      skipped: process_id 추출 불가 또는 team/dept 누락
    """
    added: list[tuple[str, str]] | None = None
    updated: list[tuple[str, str]] | None = None
    unchanged: list[str] | None = None
    kept: list[tuple[str, str]] | None = None
    skipped: int = 0

    def __post_init__(self) -> None:
        if self.added is None:
            self.added = []
        if self.updated is None:
            self.updated = []
        if self.unchanged is None:
            self.unchanged = []
        if self.kept is None:
            self.kept = []

    @property
    def total_apply(self) -> int:
        return len(self.added) + len(self.updated)  # type: ignore[arg-type]


def _cell(row: Mapping[str, Any], key: str) -> str:
    v = row.get(key, "")
    if v is None:
        return ""
    return str(v).strip()


def _org_meta_from_row(row: Mapping[str, Any]) -> dict[str, str]:
    """행에서 ORG_META_KEYS 만 추출 (빈 값 제외)."""
    out: dict[str, str] = {}
    for k in ORG_META_KEYS:
        v = _cell(row, k)
        if v:
            out[k] = v
    return out


def _process_id_from_row(row: Mapping[str, Any], json_text: str) -> str:
    """process_id 결정 — 컬럼 우선, 없으면 JSON 내부."""
    pid = _cell(row, "process_id")
    if pid:
        return pid
    if json_text:
        try:
            obj = json.loads(json_text)
        except (json.JSONDecodeError, ValueError):
            return ""
        if isinstance(obj, dict):
            jp = obj.get("process_id")
            if isinstance(jp, str) and jp.strip():
                return jp.strip()
    return ""


def row_to_task_def(row: Mapping[str, Any]) -> tuple[str, str] | None:
    """정규화된 행 → (process_id, task_def_json_str). 불가능하면 None.

    - process_id 없음 → None
    - team/dept 없음 (org_meta 필수) → None (TaskDefJsonError 흡수)
    """
    json_text = _cell(row, "task_def_json")
    pid = _process_id_from_row(row, json_text)
    if not pid:
        return None
    org_meta = _org_meta_from_row(row)
    try:
        merged = ingest_org_meta(json_text, org_meta, process_id=pid)
    except TaskDefJsonError:
        return None
    return pid, merged


def _display_name(json_str: str, pid: str) -> str:
    """diff 미리보기 표시용 짧은 이름 — process_name 우선, 없으면 process_id."""
    try:
        obj = json.loads(json_str)
    except (json.JSONDecodeError, ValueError, TypeError):
        return pid
    if isinstance(obj, dict):
        for key in ("process_name", "process_id"):
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return pid


def compute_diff(df) -> DiffPreview:
    """업로드 DataFrame 의 변경 사항을 현재 SQLite 상태와 비교 (PR-5).

    실제 쓰기는 하지 않음. UI 미리보기 후 `sync_dataframe(df)` 호출이 적용.
    """
    from store import task_defs_db

    res = DiffPreview()
    if df is None or getattr(df, "empty", True):
        # 업로드는 비었지만 DB 가 비었는지에 따라 kept 채움
        for r in task_defs_db.list_all():
            res.kept.append(  # type: ignore[union-attr]
                (r["process_id"], _display_name(r.get("json") or "", r["process_id"]))
            )
        return res

    upload_pids: set[str] = set()
    for _, raw in df.iterrows():
        row = raw.to_dict()
        built = row_to_task_def(row)
        if built is None:
            res.skipped += 1
            continue
        pid, json_str = built
        upload_pids.add(pid)
        name = _display_name(json_str, pid)
        existing = task_defs_db.get(pid)
        if existing is None:
            res.added.append((pid, name))  # type: ignore[union-attr]
        else:
            if (existing.get("json") or "") == json_str:
                res.unchanged.append(pid)  # type: ignore[union-attr]
            else:
                res.updated.append((pid, name))  # type: ignore[union-attr]

    # DB 에는 있지만 이번 업로드에 없는 항목 → kept (유지될)
    for r in task_defs_db.list_all():
        if r["process_id"] not in upload_pids:
            res.kept.append(  # type: ignore[union-attr]
                (r["process_id"], _display_name(r.get("json") or "", r["process_id"]))
            )

    return res


def sync_dataframe(
    df,
    *,
    changed_by: str | None = None,
    source: str = "excel_upload",
    replace: bool = False,
) -> SyncResult:
    """정규화된 로드맵 DataFrame → SQLite UPSERT. import 는 함수 내부(순환 방지).

    replace=True (재업로드 교체): UPSERT 전에 `task_defs` 를 전부 비운다 → 직전
    업로드에 없던 process_id 가 남지 않고 데이터셋 전체가 교체된다.
    """
    from store import task_defs_db

    res = SyncResult()
    if df is None or getattr(df, "empty", True):
        return res

    if replace:
        task_defs_db.clear_all()

    for _, raw in df.iterrows():
        row = raw.to_dict()
        built = row_to_task_def(row)
        if built is None:
            res.skipped += 1
            continue
        pid, json_str = built
        task_def_text = _cell(row, "task_def") or None
        try:
            existed = task_defs_db.get(pid) is not None
            task_defs_db.upsert(
                pid, json_str,
                task_def_text=task_def_text,
                changed_by=changed_by, source=source,
            )
            if existed:
                res.updated += 1
            else:
                res.created += 1
        except ValueError as exc:  # task_defs_db 검증 실패
            res.skipped += 1
            res.errors.append(f"{pid}: {exc}")  # type: ignore[union-attr]
    return res
