"""로드맵 Parquet/SQLite 조회·집계 헬퍼.

PR-4 (M1 전환):
  - `load_latest()` 는 SQLite(`task_defs`) 가 비어있지 않으면 거기서 읽고,
    비어있으면 기존 Parquet 으로 fallback.
  - 반환 DataFrame 의 **컬럼 셋과 시그니처는 변경 없음** → 보드/인사이트/
    데이터관리/매칭 호출처 무변경.
  - `prefer="parquet"` 로 명시하면 기존 Parquet 경로만 사용 (테스트/마이그용).
"""
from __future__ import annotations

import pandas as pd

from roadmap.schema import ALL_COLUMNS
from store.paths import latest_parquet, roadmap_dir


def _load_parquet() -> pd.DataFrame:
    path = latest_parquet(roadmap_dir(), "roadmap_*.parquet")
    if not path:
        return pd.DataFrame()
    return pd.read_parquet(path)


def _load_sqlite() -> pd.DataFrame:
    """`task_defs` 테이블 → ALL_COLUMNS 모양 DataFrame. 비어있으면 빈 DF."""
    from store import task_defs_db

    rows = task_defs_db.list_all()
    if not rows:
        return pd.DataFrame()

    records: list[dict] = []
    for r in rows:
        obj = r.get("json_obj") or {}
        if not isinstance(obj, dict):
            obj = {}
        meta = obj.get("org_meta") if isinstance(obj.get("org_meta"), dict) else {}

        # org_meta 우선, scalar 미러로 보강. 빈 값은 빈 문자열로 (Parquet 모양 일치).
        team = str(meta.get("team") or r.get("team") or "")
        dept = str(meta.get("dept") or r.get("dept") or "")
        division = str(meta.get("division") or r.get("division") or "")
        process = str(meta.get("process") or r.get("process") or "")
        task = str(meta.get("task") or r.get("task") or "")
        sub_task = str(meta.get("sub_task") or task or "")

        # lv1/lv2/lv3 — org_meta 에 있으면 사용, 없으면 division/process/task fallback
        # (ingest.normalize_columns 의 동작과 동일).
        lv1 = str(meta.get("lv1") or division or "")
        lv2 = str(meta.get("lv2") or process or "")
        lv3 = str(meta.get("lv3") or task or "")

        records.append({
            "team": team, "dept": dept,
            "lv1": lv1, "lv2": lv2, "lv3": lv3,
            "task": task,
            "sub_task": sub_task,
            "task_def": r.get("task_def_text") or "",
            "task_def_json": r.get("json") or "",
            "division": division, "process": process,
            "process_id": r.get("process_id") or obj.get("process_id") or "",
            "sws_no": str(obj.get("sws_no") or ""),
            "sws_name": str(obj.get("sws_name") or ""),
        })

    df = pd.DataFrame(records)
    # ALL_COLUMNS 순서·완전성 보장 (누락 시 빈 컬럼 추가).
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[list(ALL_COLUMNS)].copy()


def load_latest(*, prefer: str = "sqlite") -> pd.DataFrame:
    """가장 최근 로드맵 데이터.

    Args:
        prefer: "sqlite"(기본) — SQLite 우선, 비면 Parquet fallback.
                "parquet" — Parquet 만 사용 (마이그/회귀 테스트용).
    """
    if prefer == "parquet":
        return _load_parquet()
    df = _load_sqlite()
    if df.empty:
        return _load_parquet()
    return df


def by_dept(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "dept" not in df.columns:
        return pd.DataFrame(columns=["dept", "count"])
    return (
        df.groupby("dept", dropna=False).size()
        .reset_index(name="count").sort_values("count", ascending=False, ignore_index=True)
    )


def by_lv(df: pd.DataFrame, level: str) -> pd.DataFrame:
    """level: 'lv1' | 'lv2' | 'lv3'."""
    if df.empty or level not in df.columns:
        return pd.DataFrame(columns=[level, "count"])
    return (
        df.groupby(level, dropna=False).size()
        .reset_index(name="count").sort_values("count", ascending=False, ignore_index=True)
    )


def filter_hierarchy(
    df: pd.DataFrame,
    *,
    team: str | None = None,
    dept: str | None = None,
    lv1: str | None = None,
    lv2: str | None = None,
    lv3: str | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    for col, val in (("team", team), ("dept", dept), ("lv1", lv1), ("lv2", lv2), ("lv3", lv3)):
        if val:
            mask &= df[col].astype(str) == val
    return df.loc[mask].reset_index(drop=True)
