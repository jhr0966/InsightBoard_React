"""뉴스 API — `store.news_db` 위임 (수집된 기사 조회).

Parquet 합본 DataFrame 을 레코드로 변환해 노출. Phase 1 read-only(수집 실행은
후속 `/api/collect`). 응답은 경량 필드 셋만 — 본문(content)은 상세 조회로 분리.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from store import news_db

router = APIRouter(prefix="/api/news", tags=["news"])

# 목록 응답 경량 필드 (content 제외 — payload 절감).
_LIST_FIELDS = (
    "title", "press", "date", "published_at", "link", "summary",
    "keywords", "source", "query", "image_url", "summary_llm", "collected_at",
)


def _records(df, fields=_LIST_FIELDS) -> list[dict]:
    if df.empty:
        return []
    cols = [c for c in fields if c in df.columns]
    return df[cols].to_dict(orient="records")


@router.get("")
def list_news(
    days: int = Query(default=7, ge=1, le=90, description="오늘 포함 최근 N일"),
    source: str | None = Query(default=None, description="출처 필터"),
    limit: int | None = Query(default=200, ge=1, le=2000),
) -> list[dict]:
    df = news_db.load_news_for_days(days)
    if source and not df.empty and "source" in df.columns:
        df = df[df["source"] == source]
    if limit and not df.empty:
        df = df.head(limit)
    return _records(df)


@router.get("/today")
def list_today() -> list[dict]:
    return _records(news_db.load_all_today())
