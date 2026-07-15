"""인사이트 분석 보조 API — 공정×자동화기술 히트맵.

행=`score_cells` 상위 공정(Lv3), 열=고정 기술 7종(ui/insights_v2 승계).
셀 값 = "그 공정에 매칭된 뉴스" 중 해당 기술 키워드를 언급한 기사 수.

⚠ 공정↔뉴스 연결은 `store.match.score_matches`(토큰/의미유사도) 를 재사용한다.
과거엔 공정명(lv3) 문자열을 뉴스 본문에서 그대로 substring 검색했는데, 실데이터의
공정명이 다단어(`용접 작업`·`절단작업`·`LUG 제거 작업`)라 본문에 그 전체 문자열이
거의 안 나와 히트맵이 비어 보였다(자동화 기회 매트릭스는 토큰 매칭이라 강하게 뜨는데
히트맵만 0 → 불일치). 이제 둘 다 동일한 매칭을 써서 일관된다.
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query

from roadmap import query as roadmap_query
from sola.opportunity import score_cells
from store import news_db

router = APIRouter(prefix="/api/insights", tags=["insights"])

TECHS = ["비전", "협동 로봇", "예지보전", "디지털 트윈", "AGV", "AI", "외골격"]

# 공정당 연결할 뉴스 상한 — 히트맵은 '관련 여부' 집계라 랭킹용(5)보다 넉넉히 잡아
# 신호를 충분히 모은다(일자별 뉴스 수가 상한이라 비용은 제한적).
_TOP_K_PER_TASK = 20


def _row_text(rec: dict) -> str:
    # enrich 가 채우는 keywords_llm·content 까지 포함(legacy _hm_count_in_news 와 동일 범위).
    cols = ("title", "summary", "summary_llm", "keywords", "keywords_llm", "content")
    return " ".join(str(rec.get(c, "")) for c in cols).lower()


def _matched_news_by_lv3(
    news_df: pd.DataFrame, roadmap_df: pd.DataFrame, *, days: int = 30,
) -> dict[str, list[dict]]:
    """공정(lv3) → 매칭된 뉴스 레코드 목록. 자동화 기회 매트릭스와 동일한 매칭 사용.

    link(없으면 title) 를 키로 뉴스 레코드를 복원하고, lv3 별로 중복 제거해 모은다.
    매칭은 저장된 links(Step 6) 소비 — 셀 클릭마다 전체 재계산하던 비용 제거.
    """
    if news_df.empty or roadmap_df.empty:
        return {}
    from store import links_db

    matches = links_db.slice_top_k(
        links_db.matches_for_window(news_df, roadmap_df, days=days), _TOP_K_PER_TASK)
    if matches.empty:
        return {}
    by_key = {str(r.get("link") or r.get("title") or ""): r for r in news_df.to_dict("records")}
    out: dict[str, list[dict]] = {}
    for lv3, grp in matches.groupby("lv3"):
        if not lv3:
            continue
        recs: list[dict] = []
        seen: set[str] = set()
        for key in grp["link"].fillna("").astype(str).tolist():
            if not key or key in seen:
                continue
            seen.add(key)
            rec = by_key.get(key)
            if rec is not None:
                recs.append(rec)
        out[str(lv3)] = recs
    return out


@router.get("/process-map")
def process_map(
    keyword: str = Query("", description="트렌드 키워드(빈 값=전체 뉴스)"),
    days: int = Query(default=30, ge=1, le=90),
    top: int = Query(default=3, ge=1, le=10),
) -> list[dict]:
    """선택한 트렌드 키워드 → 연결되는 상위 공정(Lv3) 카드.

    그 키워드를 언급한 최근 뉴스만으로 `score_cells` 를 돌려, 키워드가 어떤 공정에
    자동화 기회로 이어지는지(적합도·샘플작업·근거뉴스 수·목표·PoC 태그)를 낸다.
    Streamlit `_ia_process_map_html` 의 React 이식 — '트렌드 → 공정 연결' 섹션 본체.
    """
    news = news_db.load_news_for_days(days)
    if news.empty:
        return []
    if keyword.strip():
        kw = keyword.strip().lower()
        news = news[news.apply(lambda r: kw in _row_text(r), axis=1)]
        if news.empty:
            return []
    roadmap = roadmap_query.load_latest()
    cells = score_cells(news, roadmap).head(top)
    if cells.empty:
        return []
    scores = [float(s or 0) for s in cells["cell_score"].tolist()]
    top_score = max(scores) or 1.0
    out: list[dict] = []
    for _, c in cells.iterrows():
        score = float(c.get("cell_score") or 0)
        out.append({
            "dept": str(c.get("dept", "") or ""),
            "lv3": str(c.get("lv3", "") or ""),
            "fit": round(min(1.0, score / top_score), 3),     # 0~1 상대 적합도
            "matched_news": int(c.get("matched_news") or 0),
            "sample_task": str(c.get("sample_tasks", "") or ""),
            "objective": str(c.get("sample_objectives", "") or ""),
            "signal": str(c.get("sample_news", "") or ""),
            "tag": "PoC 후보" if score >= top_score * 0.6 else "관찰 대상",
        })
    return out


@router.get("/heatmap")
def heatmap(
    days: int = Query(default=30, ge=1, le=90),
    rows: int = Query(default=7, ge=1, le=20),
) -> dict:
    news = news_db.load_news_for_days(days)
    roadmap = roadmap_query.load_latest()
    from store import links_db

    stored = (links_db.matches_for_window(news, roadmap, days=days)
              if not news.empty and not roadmap.empty else pd.DataFrame())
    cells = score_cells(news, roadmap, matches=stored)
    procs: list[str] = []
    if not cells.empty:
        for lv3 in cells["lv3"].tolist():
            if lv3 and lv3 not in procs:
                procs.append(lv3)
            if len(procs) >= rows:
                break

    by_lv3 = _matched_news_by_lv3(news, roadmap, days=days)
    data: list[list[int]] = []
    for p in procs:
        texts = [_row_text(r) for r in by_lv3.get(p, [])]
        data.append([sum(1 for tx in texts if t.lower() in tx) for t in TECHS])

    return {"rows": procs, "cols": TECHS, "data": data}


@router.get("/heatmap-cell")
def heatmap_cell(
    row: str = Query(..., description="공정(lv3) 이름"),
    col: str = Query(..., description="기술 키워드"),
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[dict]:
    """선택 셀(공정 × 기술)의 근거 뉴스 — 상세 strip 미리보기용.

    `/heatmap` 과 동일한 매칭(공정→뉴스)을 써서, 불 켜진 셀을 누르면 반드시 그 기사가
    나온다(과거 공정명 substring 방식은 다단어 공정명에서 빈 결과를 줬다).
    """
    news = news_db.load_news_for_days(days)
    if news.empty:
        return []
    roadmap = roadmap_query.load_latest()
    recs = _matched_news_by_lv3(news, roadmap, days=days).get(row, [])
    cl = col.lower()
    out: list[dict] = []
    for rec in recs:
        if cl in _row_text(rec):
            out.append({
                "title": rec.get("title", ""), "link": rec.get("link", ""),
                "press": rec.get("press", ""), "source": rec.get("source", ""),
                "date": rec.get("date", ""), "summary_llm": rec.get("summary_llm", ""),
            })
            if len(out) >= limit:
                break
    return out
