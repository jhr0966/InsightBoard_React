"""뉴스 article dict 리스트 ↔ 일자별 Parquet 저장소."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from store.paths import latest_parquet, news_dir_for


_ARTICLE_COLS = (
    "title", "press", "date", "published_at", "link",
    "summary", "keywords", "source", "query",
    # M4-α enrich 컬럼 — 본문/LLM 키워드·요약/타임스탬프
    "content", "keywords_llm", "summary_llm", "enriched_at",
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


def _normalize_loaded(df: pd.DataFrame) -> pd.DataFrame:
    """과거 스키마(컬럼 부족) Parquet 도 신규 컬럼을 빈값으로 채워 안전."""
    for col in _ARTICLE_COLS:
        if col not in df.columns:
            df[col] = ""
    return df[list(_ARTICLE_COLS)]


def load_latest(source: str | None = None) -> pd.DataFrame:
    """가장 최근 일자 디렉토리의 source(또는 전체) Parquet 로드."""
    today_dir = news_dir_for()
    pattern = f"{source}_*.parquet" if source else "*.parquet"
    latest = latest_parquet(today_dir, pattern)
    if not latest:
        return pd.DataFrame(columns=list(_ARTICLE_COLS))
    return _normalize_loaded(pd.read_parquet(latest))


def load_all_today() -> pd.DataFrame:
    """오늘자 디렉토리의 모든 Parquet을 합쳐서 반환."""
    today_dir = news_dir_for()
    frames = [_normalize_loaded(pd.read_parquet(p)) for p in sorted(today_dir.glob("*.parquet"))]
    if not frames:
        return pd.DataFrame(columns=list(_ARTICLE_COLS))
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["link"], keep="last")


def upsert_articles(articles: list[dict], *, source: str) -> Path | None:
    """enrich 후 갱신된 article dict 리스트를 동일 파일명 규칙으로 새로 저장.

    중복 link 는 (저장 시점 기준 최신) article 로 덮어쓰기 효과 — 별도 파일로 추가되지만
    load_all_today 의 drop_duplicates(subset=['link']) 에서 마지막 항목이 남음.
    """
    return save_articles(articles, source=source)
