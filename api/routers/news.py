"""뉴스 API — `store.news_db` 위임 (수집된 기사 조회).

Parquet 합본 DataFrame 을 레코드로 변환해 노출. Phase 1 read-only(수집 실행은
후속 `/api/collect`). 목록 응답은 경량 필드 셋만 — 본문(content)은 `/detail` 상세
조회로 분리(payload 절감).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from store import news_db

router = APIRouter(prefix="/api/news", tags=["news"])

# 목록 응답 경량 필드 (content 제외 — payload 절감).
_LIST_FIELDS = (
    "title", "press", "date", "published_at", "link", "summary",
    "keywords", "source", "query", "image_url", "summary_llm", "collected_at",
)
# 상세 응답 — 목록 + 본문/enrich 필드.
_DETAIL_FIELDS = _LIST_FIELDS + ("content", "keywords_llm", "enriched_at")


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


@router.get("/detail")
def news_detail(
    link: str = Query(..., description="기사 URL(고유키)"),
    days: int = Query(default=30, ge=1, le=365, description="조회 윈도(이 안에서 link 매칭)"),
) -> dict:
    """단건 기사 상세 — 본문(content)·enrich 필드 포함. 목록의 link 로 조회."""
    df = news_db.load_news_for_days(days)
    if df.empty or "link" not in df.columns:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    match = df[df["link"] == link]
    if match.empty:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return _records(match.head(1), _DETAIL_FIELDS)[0]


@router.get("/today")
def list_today() -> list[dict]:
    return _records(news_db.load_all_today())


@router.get("/content-rate")
def content_rate(days: int = Query(default=7, ge=1, le=90)) -> dict:
    """본문 확보율 — 최근 N일 기사 중 본문(content ≥ 50자)이 채워진 비율.

    Streamlit data_health 의 `enrich_percent`/`content_ready_count` 이식 —
    수집 설정 화면 헬스 카드가 소비(enrich/fetch 가 제대로 도는지 한눈에).
    """
    df = news_db.load_news_for_days(days)
    total = int(len(df))
    if total == 0 or "content" not in df.columns:
        return {"total": total, "ready": 0, "pct": 0}
    ready = int((df["content"].astype(str).str.len() >= 50).sum())
    return {"total": total, "ready": ready, "pct": round(ready / total * 100)}
