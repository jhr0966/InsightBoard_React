"""뉴스 × 작업정의 매칭 API — 저장된 links(`store.links_db`) 소비.

보드 브리핑·탑스토리·인사이트 트렌드→공정 매핑의 근거. 최근 뉴스를 로드맵
작업정의에 매칭해 작업별 top 뉴스+점수+**매칭 이유**(score_components·
matched_terms·matched_fields)를 낸다.

Step 6: 매 요청 라이브 재계산 → 저장본(write-through) 소비로 전환.
과거 이 엔드포인트만 의미유사도 없이(semantic_weight=0) 계산해 히트맵·기회
매트릭스와 결과가 미묘하게 달랐다 — 이제 셋 다 같은 저장본을 읽어 항상 일관.
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query

from api.deps import Identity, current_identity
from roadmap import query as roadmap_query
from store import links_db, news_db

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _clean(records: list[dict]) -> list[dict]:
    for r in records:  # NaN/inf → None (JSON 직렬화 안전)
        for k, v in r.items():
            if isinstance(v, float) and not math.isfinite(v):
                r[k] = None
    return records


@router.get("")
def matches(
    days: int = Query(default=7, ge=1, le=90),
    top_k: int = Query(default=5, ge=1, le=20),
    limit: int = Query(default=40, ge=1, le=200),
) -> list[dict]:
    news = news_db.load_news_for_days(days)
    roadmap = roadmap_query.load_latest()
    if news.empty or roadmap.empty:
        return []
    df = links_db.slice_top_k(
        links_db.matches_for_window(news, roadmap, days=days), top_k)
    if df.empty:
        return []
    return _clean(df.head(limit).to_dict(orient="records"))


@router.post("/rebuild-links")
def rebuild_links(
    days: int = Query(default=30, ge=1, le=90),
    _identity: Identity = Depends(current_identity),
) -> dict:
    """관리자 재빌드 — 알고리즘/식별 버전 변경·수집 직후 인덱스 선워밍.

    (계획 §9-1 실행 방식 ②. ①은 일일 cron `scripts/daily_scrape.py` 말미.)
    """
    return links_db.rebuild(days)


@router.get("/links-status")
def links_status() -> list[dict]:
    """윈도우별 links 인덱스 상태 — built_at·건수·버전·stale 여부."""
    return links_db.index_status()
