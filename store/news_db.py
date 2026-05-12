"""뉴스 article dict 리스트 ↔ 일자별 Parquet 저장소."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from store.paths import latest_parquet, news_dir_for


_ARTICLE_COLS = (
    "title", "press", "date", "published_at", "link",
    "summary", "keywords", "source", "query",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%SZ")


def _to_df(articles: list[dict]) -> pd.DataFrame:
    if not articles:
        return pd.DataFrame(columns=list(_ARTICLE_COLS))
    df = pd.DataFrame(articles)
    for col in _ARTICLE_COLS:
        if col not in df.columns:
            df[col] = ""
    return df[list(_ARTICLE_COLS)].astype(str)


def save_articles(articles: list[dict], *, source: str) -> Path | None:
    """오늘자 디렉토리에 source 별 Parquet로 저장. 빈 리스트는 저장 안 함."""
    if not articles:
        return None
    df = _to_df(articles)
    path = news_dir_for() / f"{source}_{_utc_stamp()}.parquet"
    df.to_parquet(path, index=False)
    return path


def load_latest(source: str | None = None) -> pd.DataFrame:
    """가장 최근 일자 디렉토리의 source(또는 전체) Parquet 로드."""
    today_dir = news_dir_for()
    pattern = f"{source}_*.parquet" if source else "*.parquet"
    latest = latest_parquet(today_dir, pattern)
    if not latest:
        return pd.DataFrame(columns=list(_ARTICLE_COLS))
    return pd.read_parquet(latest)


def load_all_today() -> pd.DataFrame:
    """오늘자 디렉토리의 모든 Parquet을 합쳐서 반환."""
    today_dir = news_dir_for()
    frames = [pd.read_parquet(p) for p in sorted(today_dir.glob("*.parquet"))]
    if not frames:
        return pd.DataFrame(columns=list(_ARTICLE_COLS))
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["link"])
