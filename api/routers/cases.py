"""사례 라이브러리 API — `store.cases_db`·`sola.case_extract` 위임 (Step 12).

사례는 별도 엔터티(뉴스 북마크 아님): 자동 추출(pending_review) → 승인/제외.
**approved 사례만 제안서 주근거**로 쓰인다 — 목록 화면에서 검토·승인한다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import Identity, current_identity
from store import cases_db

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
def list_cases(
    status: str | None = Query(default=None, description="pending_review/approved/excluded"),
    technology_id: str | None = Query(default=None, description="기술 taxonomy ID 필터"),
    limit: int = Query(default=60, ge=1, le=200),
) -> list[dict]:
    if status and status not in cases_db.REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"unknown status: {status}")
    return cases_db.list_cases(status=status, technology_id=technology_id, limit=limit)


@router.get("/summary")
def cases_summary() -> dict:
    return cases_db.summary()


class CaseStatusIn(BaseModel):
    status: str = Field(..., description="pending_review | approved | excluded")


@router.post("/{case_id}/status")
def set_case_status(
    case_id: str, body: CaseStatusIn,
    _identity: Identity = Depends(current_identity),
) -> dict:
    """검토 상태 변경(§14-3) — approved 만 제안서 주근거가 된다."""
    try:
        ok = cases_db.set_status(case_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다.")
    return cases_db.get(case_id) or {}


class ExtractIn(BaseModel):
    days: int = Field(default=7, ge=1, le=30)
    limit: int = Field(default=10, ge=1, le=30, description="이번 배치 최대 LLM 호출 수")


@router.post("/extract")
def extract(body: ExtractIn, _identity: Identity = Depends(current_identity)) -> dict:
    """관리자 배치 — 최근 기사에서 사례 추출(수집과 분리, LLM 미설정 시 생략).

    (자동 경로는 일일 cron `scripts/daily_scrape.py` 말미 — §14 '별도 후처리 배치'.)
    """
    from sola.case_extract import extract_batch

    return extract_batch(days=body.days, limit=body.limit)
