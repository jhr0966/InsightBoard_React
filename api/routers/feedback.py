"""피드백 이벤트 API — `store.feedback` 위임 (개편 Step 9, 계획 §12).

개인화 다이제스트의 노출/열람/저장/관련없음 이벤트를 기록한다. 랭킹 개선의
원자료 — impression 과 open 을 함께 기록해야 "노출됐지만 무시"를 구분할 수 있다.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import Identity, current_identity
from store import feedback

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackEventsIn(BaseModel):
    events: list[dict[str, Any]] = Field(
        ..., description="[{action_type, article_id?, process_id?, context?, ranking_version?}]")


@router.post("/events")
def record(body: FeedbackEventsIn, identity: Identity = Depends(current_identity)) -> dict:
    if not body.events:
        return {"saved": 0}
    try:
        n = feedback.record_events(
            body.events, user=identity.user_id, workspace=identity.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"saved": n}


@router.get("/summary")
def summary() -> dict:
    return feedback.summary()
