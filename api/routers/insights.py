"""인사이트 분석 보조 API — 공정×자동화기술 히트맵.

최근 뉴스에서 (공정 lv3 × 기술 키워드) 동시 출현 빈도를 집계. 행=score_cells 상위
공정, 열=고정 기술 7종(ui/insights_v2 승계).
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from roadmap import query as roadmap_query
from sola.opportunity import score_cells
from store import news_db

router = APIRouter(prefix="/api/insights", tags=["insights"])

TECHS = ["비전", "협동 로봇", "예지보전", "디지털 트윈", "AGV", "AI", "외골격"]


def _row_text(rec: dict) -> str:
    return " ".join(str(rec.get(c, "")) for c in ("title", "summary", "summary_llm", "keywords")).lower()


@router.get("/heatmap")
def heatmap(
    days: int = Query(default=30, ge=1, le=90),
    rows: int = Query(default=7, ge=1, le=20),
) -> dict:
    news = news_db.load_news_for_days(days)
    roadmap = roadmap_query.load_latest()
    cells = score_cells(news, roadmap)
    procs: list[str] = []
    if not cells.empty:
        for lv3 in cells["lv3"].tolist():
            if lv3 and lv3 not in procs:
                procs.append(lv3)
            if len(procs) >= rows:
                break

    records = news.to_dict("records") if not news.empty else []
    texts = [_row_text(r) for r in records]
    data: list[list[int]] = []
    for p in procs:
        pl = p.lower()
        row = []
        for t in TECHS:
            tl = t.lower()
            row.append(sum(1 for tx in texts if pl in tx and tl in tx))
        data.append(row)

    return {"rows": procs, "cols": TECHS, "data": data}
