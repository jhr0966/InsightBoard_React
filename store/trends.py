"""뉴스 트렌드 집계 — 일자별·소스별·키워드별 + 다중 일자 비교."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

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
    tokens = _all_keyword_tokens(df)
    if not tokens:
        return pd.DataFrame(columns=["keyword", "count"])
    return pd.DataFrame(Counter(tokens).most_common(top_n), columns=["keyword", "count"])


# ── 다중 일자 트렌드 ──────────────────────────────────────────

def _all_keyword_tokens(df: pd.DataFrame) -> list[str]:
    """LLM 키워드 우선, 없으면 룰 키워드. 둘 다 합쳐서 중복 제거."""
    tokens: list[str] = []
    for col in ("keywords_llm", "keywords"):
        if col in df.columns:
            for cell in df[col].fillna("").astype(str):
                tokens.extend(t.strip() for t in cell.split(",") if t.strip())
    return tokens


def daily_volume(df: pd.DataFrame, days: int = 7, *, now: datetime | None = None) -> pd.DataFrame:
    """최근 `days` 일 일자별 기사 수. 데이터 없는 일자도 0 으로 채워 반환.

    Returns 컬럼: date(YYYY-MM-DD, 오름차순), count.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    cur = now or datetime.now(timezone.utc)
    date_index = [(cur - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    base = pd.DataFrame({"date": date_index, "count": 0})

    if df.empty:
        return base

    actual = by_date(df)
    if actual.empty:
        return base
    merged = base.merge(actual, on="date", how="left", suffixes=("_zero", ""))
    merged["count"] = merged["count"].fillna(0).astype(int)
    return merged[["date", "count"]]


def keyword_emergence(
    today_df: pd.DataFrame,
    base_df: pd.DataFrame,
    *,
    top_n: int = 10,
    min_count: int = 1,
) -> dict[str, pd.DataFrame]:
    """today 와 base(이전 기간) 키워드 집합 차이.

    Returns dict:
        - "new"        : today 에는 있고 base 에는 없는 키워드 (등장)
        - "gone"       : base 에는 있고 today 에는 없는 키워드 (사라짐)
        - "rising"     : 둘 다 있지만 today 가 더 큰 키워드 (delta 내림차순)
    각 DataFrame 컬럼: keyword, today, base, delta (rising 만)
                      또는 keyword, count (new/gone).
    """
    today_kw = pd.DataFrame(
        Counter(_all_keyword_tokens(today_df)).items(), columns=["keyword", "today"]
    )
    base_kw = pd.DataFrame(
        Counter(_all_keyword_tokens(base_df)).items(), columns=["keyword", "base"]
    )

    if today_kw.empty and base_kw.empty:
        empty = pd.DataFrame(columns=["keyword", "count"])
        return {
            "new": empty.copy(),
            "gone": empty.copy(),
            "rising": pd.DataFrame(columns=["keyword", "today", "base", "delta"]),
        }

    merged = today_kw.merge(base_kw, on="keyword", how="outer").fillna(0)
    merged["today"] = merged["today"].astype(int)
    merged["base"] = merged["base"].astype(int)

    new_df = (
        merged[(merged["base"] == 0) & (merged["today"] >= min_count)]
        .rename(columns={"today": "count"})[["keyword", "count"]]
        .sort_values("count", ascending=False, ignore_index=True)
        .head(top_n)
    )
    gone_df = (
        merged[(merged["today"] == 0) & (merged["base"] >= min_count)]
        .rename(columns={"base": "count"})[["keyword", "count"]]
        .sort_values("count", ascending=False, ignore_index=True)
        .head(top_n)
    )
    rising = merged[(merged["today"] > 0) & (merged["base"] > 0)].copy()
    rising["delta"] = rising["today"] - rising["base"]
    rising_df = (
        rising[rising["delta"] > 0]
        .sort_values("delta", ascending=False, ignore_index=True)
        [["keyword", "today", "base", "delta"]]
        .head(top_n)
    )

    return {"new": new_df, "gone": gone_df, "rising": rising_df}


def compare_distribution(
    today_df: pd.DataFrame,
    base_df: pd.DataFrame,
    *,
    key: str = "press",
    top_n: int = 10,
) -> pd.DataFrame:
    """today vs base 분포 비교. 컬럼: key, today, base, delta (내림차순)."""
    if key not in today_df.columns and key not in base_df.columns:
        return pd.DataFrame(columns=[key, "today", "base", "delta"])
    t = today_df.groupby(key, dropna=False).size().reset_index(name="today") if key in today_df.columns else pd.DataFrame(columns=[key, "today"])
    b = base_df.groupby(key, dropna=False).size().reset_index(name="base") if key in base_df.columns else pd.DataFrame(columns=[key, "base"])
    merged = t.merge(b, on=key, how="outer").fillna(0)
    merged["today"] = merged["today"].astype(int)
    merged["base"] = merged["base"].astype(int)
    merged["delta"] = merged["today"] - merged["base"]
    return merged.sort_values("delta", ascending=False, ignore_index=True).head(top_n)
