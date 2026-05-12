"""로드맵 Parquet 조회·집계 헬퍼."""
from __future__ import annotations

import pandas as pd

from store.paths import latest_parquet, roadmap_dir


def load_latest() -> pd.DataFrame:
    """가장 최근 Parquet 로드. 없으면 빈 DataFrame."""
    path = latest_parquet(roadmap_dir(), "roadmap_*.parquet")
    if not path:
        return pd.DataFrame()
    return pd.read_parquet(path)


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
