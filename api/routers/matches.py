"""뉴스 × 작업정의 매칭 API — `store.match.score_matches` 위임.

보드 브리핑·탑스토리·인사이트 트렌드→공정 매핑의 근거. 최근 뉴스를 로드맵
작업정의에 매칭해 작업별 top 뉴스+점수를 낸다.
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Query

from roadmap import query as roadmap_query
from store import match, news_db

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("")
def matches(
    days: int = Query(default=7, ge=1, le=90),
    top_k: int = Query(default=5, ge=1, le=20),
    limit: int = Query(default=40, ge=1, le=200),
) -> list[dict]:
    news = news_db.load_news_for_days(days)
    roadmap = roadmap_query.load_latest()
    df = match.score_matches(news, roadmap, top_k=top_k)
    if df.empty:
        return []
    records = df.head(limit).to_dict(orient="records")
    for r in records:  # NaN/inf → None
        for k, v in r.items():
            if isinstance(v, float) and not math.isfinite(v):
                r[k] = None
    return records
