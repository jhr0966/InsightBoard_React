"""오늘의 보드 API — LLM 다이제스트(`sola.board_brief`) + 페르소나 라벨.

`brief()` 는 디스크 캐시 + LLM 미설정 시 룰 기반 폴백을 내장하므로, 키 없이도
안전하게 한 줄 요약을 돌려준다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import Identity, current_identity

from persona import store as persona_store
from sola.board_brief import brief as _brief
from store import news_db

router = APIRouter(prefix="/api/board", tags=["board"])

_ITEM_FIELDS = ("title", "source", "summary", "summary_llm", "link", "date")


def _ranked_digest(days: int, limit: int, persona, *, user: str = "local") -> list[dict]:
    """개인화 다이제스트 원자료 — links × 페르소나 랭킹 (Step 9).

    빈 결과여도 안전(신규 설치·수집 전) — 호출부가 최신순 폴백.
    """
    from roadmap import query as roadmap_query
    from store import feedback, links_db, rank

    news = news_db.load_news_for_days(days)
    if news.empty:
        return []
    roadmap = roadmap_query.load_latest()
    links = (links_db.matches_for_window(news, roadmap, days=days)
             if not roadmap.empty else None)
    return rank.rank_articles(
        news, persona, links, limit=limit,
        exclude_article_ids=feedback.dismissed_article_ids(user=user))


@router.get("/digest")
def board_digest(
    days: int = Query(default=3, ge=1, le=30, description="다이제스트 대상 기간"),
    limit: int = Query(default=5, ge=1, le=12),
    identity: Identity = Depends(current_identity),
) -> dict:
    """오늘의 개인화 다이제스트 — 기사 3~5건 + '왜 내 업무와 관련 있는가'.

    랭킹·이유는 links(저장된 매칭)와 페르소나의 규칙 조합(LLM 미사용,
    store/rank.py). '관련 없음'(dismiss) 처리한 기사는 제외된다.
    """
    persona = persona_store.load(identity.user_id)
    items = _ranked_digest(days, limit, persona, user=identity.user_id)
    from store.rank import RANKING_VERSION

    return {"items": items, "ranking_version": RANKING_VERSION,
            "persona_set": persona.is_set()}


@router.get("/brief")
def board_brief(
    days: int = Query(default=1, ge=1, le=30),
    limit: int = Query(default=12, ge=1, le=50),
    force: bool = Query(default=False, description="캐시 무시 재생성"),
    identity: Identity = Depends(current_identity),
) -> dict:
    df = news_db.load_news_for_days(days)
    items: list[dict] = []
    # 브리핑 입력 = 개인화 랭킹 상위(있으면) — board_brief 모듈을 교체하지 않고
    # 입력만 랭킹 기사 묶음으로 확장(계획 Phase5: 신규 모듈 중복 생성 금지).
    persona = persona_store.load(identity.user_id)
    ranked = _ranked_digest(max(days, 3), min(limit, 8), persona, user=identity.user_id)
    if ranked:
        items = [{"title": r.get("title", ""), "source": r.get("source", ""),
                  "summary": r.get("excerpt", ""), "link": r.get("link", ""),
                  "date": str(r.get("sort_at", ""))[:10]} for r in ranked]
    elif not df.empty:
        cols = [c for c in _ITEM_FIELDS if c in df.columns]
        items = df[cols].head(limit).to_dict(orient="records")
        # summary_llm 우선 → summary 로 폴백(브리프 입력 품질↑).
        for it in items:
            if not it.get("summary") and it.get("summary_llm"):
                it["summary"] = it["summary_llm"]

    label = persona.label()
    # 페르소나 관심 공정 작업정의를 브리핑에 주입 — 뉴스를 내 공정 맥락에 연결.
    from sola import task_context
    tctx, _ = task_context.persona_task_context(persona)
    text = _brief(
        items,
        persona_label=label if persona.is_set() else "",
        task_context=tctx,
        force=force,
    )
    return {"brief": text, "item_count": len(items), "persona_label": label}
