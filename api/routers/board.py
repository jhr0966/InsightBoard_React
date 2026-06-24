"""오늘의 보드 API — LLM 다이제스트(`sola.board_brief`) + 페르소나 라벨.

`brief()` 는 디스크 캐시 + LLM 미설정 시 룰 기반 폴백을 내장하므로, 키 없이도
안전하게 한 줄 요약을 돌려준다.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from persona import store as persona_store
from sola.board_brief import brief as _brief
from store import news_db

router = APIRouter(prefix="/api/board", tags=["board"])

_ITEM_FIELDS = ("title", "source", "summary", "summary_llm", "link", "date")


@router.get("/brief")
def board_brief(
    days: int = Query(default=1, ge=1, le=30),
    limit: int = Query(default=12, ge=1, le=50),
    force: bool = Query(default=False, description="캐시 무시 재생성"),
) -> dict:
    df = news_db.load_news_for_days(days)
    items: list[dict] = []
    if not df.empty:
        cols = [c for c in _ITEM_FIELDS if c in df.columns]
        items = df[cols].head(limit).to_dict(orient="records")
        # summary_llm 우선 → summary 로 폴백(브리프 입력 품질↑).
        for it in items:
            if not it.get("summary") and it.get("summary_llm"):
                it["summary"] = it["summary_llm"]

    persona = persona_store.load()
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
