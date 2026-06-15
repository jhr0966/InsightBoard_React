"""자동화 기회 매트릭스 API — `sola.opportunity.score_cells` 위임.

최근 뉴스 × 로드맵(작업정의) 매칭으로 부서×공정(lv3) 셀 점수를 낸다. read-only.
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Query

from roadmap import query as roadmap_query
from sola.opportunity import score_cells
from store import news_db

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


def _clean(records: list[dict]) -> list[dict]:
    # NaN/inf → None (JSON 직렬화 안전).
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and not math.isfinite(v):
                r[k] = None
    return records


@router.get("")
def opportunities(
    days: int = Query(default=30, ge=1, le=90),
    top: int = Query(default=20, ge=1, le=200),
) -> list[dict]:
    news = news_db.load_news_for_days(days)
    roadmap = roadmap_query.load_latest()
    cells = score_cells(news, roadmap).head(top)
    return _clean(cells.to_dict(orient="records"))
