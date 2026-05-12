"""뉴스 트렌드 집계 — 일자별·소스별·키워드별."""
from __future__ import annotations

from collections import Counter

import pandas as pd


def _date_col(df: pd.DataFrame) -> pd.Series:
    """published_at 이 있으면 우선, 없으면 date 사용. 'YYYY-MM-DD' 로 정규화."""
    if "published_at" in df.columns:
        s = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
        out = s.dt.strftime("%Y-%m-%d")
        return out.fillna(df.get("date", pd.Series("", index=df.index)).astype(str))
    return df.get("date", pd.Series("", index=df.index)).astype(str)


def by_date(df: pd.DataFrame) -> pd.DataFrame:
    """일자별 기사 수. 컬럼: date, count (오름차순)."""
    if df.empty:
        return pd.DataFrame(columns=["date", "count"])
    dates = _date_col(df)
    dates = dates[dates.ne("")]
    if dates.empty:
        return pd.DataFrame(columns=["date", "count"])
    return (
        dates.value_counts().rename_axis("date").reset_index(name="count")
        .sort_values("date", ignore_index=True)
    )


def by_source(df: pd.DataFrame) -> pd.DataFrame:
    """소스별 기사 수. 컬럼: source, count."""
    if df.empty or "source" not in df.columns:
        return pd.DataFrame(columns=["source", "count"])
    return (
        df.groupby("source", dropna=False).size()
        .reset_index(name="count").sort_values("count", ascending=False, ignore_index=True)
    )


def top_keywords(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """키워드(컬럼 'keywords', comma-separated) 빈도 상위 N."""
    if df.empty or "keywords" not in df.columns:
        return pd.DataFrame(columns=["keyword", "count"])
    tokens: list[str] = []
    for cell in df["keywords"].fillna("").astype(str):
        tokens.extend(t.strip() for t in cell.split(",") if t.strip())
    if not tokens:
        return pd.DataFrame(columns=["keyword", "count"])
    return pd.DataFrame(Counter(tokens).most_common(top_n), columns=["keyword", "count"])
