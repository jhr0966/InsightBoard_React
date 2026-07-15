"""뉴스 API — `store.news_db` 위임 (수집된 기사 조회).

Parquet 합본 DataFrame 을 레코드로 변환해 노출. Phase 1 read-only(수집 실행은
후속 `/api/collect`).

목록/상세 계약 (Step 3 `feat-news-pagination`):
- 목록(`GET /api/news`)은 **경량 응답** — 전체 본문(content) 대신 발췌
  `excerpt`(≤ `_EXCERPT_MAX`)와 `content_available`(본문 확보 여부)만 싣는다.
  기사 300건 × 본문 4,000자 = 1MB+ 응답이 나오던 payload 문제 해소.
- 전체 본문·enrich 필드는 상세(`GET /api/news/detail`)로만.
- 목록은 **커서 페이지네이션**: 응답 `{items, next_cursor}`. 커서는 정렬키
  그대로 `"{sort_at}::{link}"` (I-14 결정적 정렬: sort_at desc·link asc 이므로
  offset 과 달리 수집이 끼어들어도 중복/누락 없이 이어진다).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from store import news_db

router = APIRouter(prefix="/api/news", tags=["news"])

# 목록 발췌(excerpt) 최대 길이 — 카드 2줄 클램프·데이터표 프리뷰에 충분한 크기.
_EXCERPT_MAX = 300
# 본문 '확보' 판정 최소 길이 — /content-rate 와 동일 기준.
_CONTENT_READY_MIN = 50

# 목록 응답 필드 — 본문(content)은 제외(excerpt/content_available 파생 필드로 대체).
# article_id 는 안정 식별자(정규화 URL 해시), sort_at 은 정렬·커서 키.
_LIST_FIELDS = (
    "title", "press", "date", "published_at", "link", "summary",
    "keywords", "source", "query", "image_url", "summary_llm", "collected_at",
    "article_id", "sort_at",
)
# 상세 응답 — 목록 + 전체 본문/enrich 필드.
_DETAIL_FIELDS = _LIST_FIELDS + ("content", "keywords_llm", "enriched_at")


def _records(df, fields=_LIST_FIELDS, *, excerpt: bool = False) -> list[dict]:
    if df.empty:
        return []
    cols = [c for c in fields if c in df.columns]
    rows = df[cols].to_dict(orient="records")
    if excerpt and "content" in df.columns:
        # 목록 경량화 — 본문은 발췌·확보 여부만 파생해 싣는다(전체는 /detail).
        contents = df["content"].astype(str).tolist()
        for r, c in zip(rows, contents):
            r["content_available"] = len(c) >= _CONTENT_READY_MIN
            r["excerpt"] = (c[:_EXCERPT_MAX].rstrip() + "…") if len(c) > _EXCERPT_MAX else c
    return rows


def _after_cursor(df, cursor: str):
    """커서(`"{sort_at}::{link}"`) **이후** 행만 남긴다 (정렬 계약 I-14 기준).

    정렬이 (sort_at desc, link asc) 이므로 '이후' = sort_at 이 더 작거나,
    같으면 link 가 더 큰 행. 커서 형식이 어긋나면 400.
    """
    parts = cursor.split("::", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="잘못된 커서 형식입니다.")
    c_sort, c_link = parts
    mask = (df["sort_at"] < c_sort) | ((df["sort_at"] == c_sort) & (df["link"] > c_link))
    return df[mask]


@router.get("")
def list_news(
    days: int = Query(default=7, ge=1, le=90, description="오늘 포함 최근 N일"),
    source: str | None = Query(default=None, description="출처 필터"),
    limit: int = Query(default=60, ge=1, le=500, description="페이지 크기"),
    cursor: str | None = Query(default=None, description="이전 응답의 next_cursor"),
) -> dict:
    """뉴스 목록 — 결정적 최신순 + 커서 페이지네이션.

    응답: `{"items": [...], "next_cursor": str | null}`.
    next_cursor 가 null 이면 마지막 페이지.
    """
    # load_news_for_days 는 결정적 최신순(sort_at desc)을 보장 — head(limit) 은
    # 항상 "커서 이후 가장 최신 limit 건"이다.
    df = news_db.load_news_for_days(days)
    if source and not df.empty and "source" in df.columns:
        df = df[df["source"] == source]
    if cursor and not df.empty:
        df = _after_cursor(df, cursor)
    page = df.head(limit) if not df.empty else df
    items = _records(page, excerpt=True)
    next_cursor = None
    if len(items) == limit and len(df) > limit:
        last = items[-1]
        next_cursor = f"{last.get('sort_at', '')}::{last.get('link', '')}"
    return {"items": items, "next_cursor": next_cursor}


@router.get("/detail")
def news_detail(
    link: str = Query(..., description="기사 URL(고유키)"),
    days: int = Query(default=30, ge=1, le=365, description="조회 윈도(이 안에서 link 매칭)"),
) -> dict:
    """단건 기사 상세 — 전체 본문(content)·enrich 필드 포함. 목록의 link 로 조회."""
    df = news_db.load_news_for_days(days)
    if df.empty or "link" not in df.columns:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    match = df[df["link"] == link]
    if match.empty:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return _records(match.head(1), _DETAIL_FIELDS)[0]


@router.get("/today")
def list_today() -> list[dict]:
    """오늘 수집분 전체 — 보드 탑 스토리·신선도 배지용(하루치라 페이지네이션 없음)."""
    return _records(news_db.load_all_today(), excerpt=True)


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
    ready = int((df["content"].astype(str).str.len() >= _CONTENT_READY_MIN).sum())
    return {"total": total, "ready": ready, "pct": round(ready / total * 100)}
