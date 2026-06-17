"""트렌드 API — `store.trends` 위임 (최근 뉴스에서 파생 집계).

키워드 빈도 · 일자별 볼륨 · 출처별 분포. 모두 read-only 집계.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from store import news_db, trends

router = APIRouter(prefix="/api/trends", tags=["trends"])


def _df(days: int):
    return news_db.load_news_for_days(days)


@router.get("/keywords")
def keywords(
    days: int = Query(default=7, ge=1, le=90),
    top: int = Query(default=20, ge=1, le=200),
) -> list[dict]:
    return trends.top_keywords(_df(days), top_n=top).to_dict(orient="records")


@router.get("/volume")
def volume(days: int = Query(default=7, ge=1, le=90)) -> list[dict]:
    return trends.daily_volume(_df(days), days=days).to_dict(orient="records")


@router.get("/sources")
def sources(days: int = Query(default=7, ge=1, le=90)) -> list[dict]:
    return trends.by_source(_df(days)).to_dict(orient="records")


@router.get("/keyword-series")
def keyword_series() -> dict:
    """보드 ⑤ 적응형 키워드 트렌드 — 주간 8칸(기본) / 일간 14칸(누적 부족 시).

    응답: {mode, labels, series:[{keyword,counts,total,delta,is_new}], anno|None}
    """
    return trends.adaptive_keyword_trend(_df(56))


@router.get("/emergence")
def emergence(
    base_days: int = Query(default=30, ge=2, le=90),
    top: int = Query(default=20, ge=1, le=100),
) -> dict:
    """신규/급상승 키워드 — 오늘 vs 직전 기간(`store.trends.keyword_emergence`).

    base 는 **오늘을 제외**한 직전 기간(어제 기준 N일) — base 가 오늘을 포함하면
    오늘 등장 키워드가 base 에도 잡혀 `new` 가 항상 비게 된다.
    """
    today = news_db.load_news_for_days(1)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    base = news_db.load_news_for_days(base_days, now=yesterday)
    em = trends.keyword_emergence(today, base, top_n=top)
    return {k: v.to_dict(orient="records") for k, v in em.items()}
