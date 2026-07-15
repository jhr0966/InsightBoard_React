"""자동화 제안 API — `sola.propose` 위임 (작업 × 최근 뉴스 → 제안서 초안).

생성된 제안서의 보관/채택은 `/api/bookmarks?type=proposal` 로 처리(단일 저장소).
Phase 1 은 동기 생성. 스트리밍 제안서는 후속(`/api/assistant/chat` 패턴 재사용).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import Identity, current_identity
from persona import store as persona_store
from sola.client import LLMNotConfigured
from sola.propose import propose_for_task
from store import news_db

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _llm_or_http(fn, *, what: str):
    """LLM 산출 호출을 감싸 예외를 HTTP 로 변환.

    보드 브리핑과 달리 제안서/요약은 룰 폴백이 없어, LLM 미설정·호출 실패가
    그대로 500 으로 노출됐다(예: 호스트 차단·키 미설정). 미설정은 503, 그 외 LLM
    오류는 502 로 안내 메시지와 함께 돌려줘 화면이 깨지지 않게 한다.
    """
    try:
        return fn()
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail=f"LLM 미설정 — {what} 불가: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — 제공자(openai/anthropic) 오류를 502 로 표면화
        raise HTTPException(status_code=502, detail=f"{what} LLM 오류: {exc}") from exc


class ProposalGenerateIn(BaseModel):
    task: dict[str, Any] = Field(..., description="작업 정의(또는 매칭 셀) dict")
    days: int = Field(default=30, ge=1, le=90, description="제안 근거 뉴스 기간")
    max_news: int = Field(default=6, ge=1, le=50, description="근거 기사 최대 수")


class ProposalOut(BaseModel):
    proposal: str
    task_process_id: str | None = None
    # 근거 기사(Step 8) — 제목·링크·매칭 이유. 프런트 표시 + 보관 시 meta 저장용.
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    matching_version: int | None = None
    prompt_version: int | None = None


@router.post("/generate", response_model=ProposalOut)
def generate(
    body: ProposalGenerateIn,
    _identity: Identity = Depends(current_identity),
) -> ProposalOut:
    """제안서 생성 — 선택 작업과 **매칭된 근거 기사**(links)만 주입 (Step 8).

    과거엔 최근 뉴스 앞쪽 N건(작업과 무관)을 넣어 일반론 제안서가 나왔다.
    흐름: 작업 → links 조회 → 관련도·신선도·출처 다양성으로 근거 선정 →
    매칭 이유와 함께 프롬프트 주입 → 근거 목록을 응답에 포함(보관 시 관계 저장).
    """
    from roadmap import query as roadmap_query
    from sola.propose import select_evidence
    from sola.prompts import PROPOSE_PROMPT_VERSION
    from store import links_db
    from store.match import MATCHING_VERSION

    news_df = news_db.load_news_for_days(body.days)
    roadmap_df = roadmap_query.load_latest()
    links = (links_db.matches_for_window(news_df, roadmap_df, days=body.days)
             if not news_df.empty and not roadmap_df.empty else None)
    evidence = select_evidence(body.task, links, news_df, max_items=body.max_news)

    persona = persona_store.load()
    text = _llm_or_http(
        lambda: propose_for_task(body.task, news_df, persona=persona, evidence=evidence),
        what="제안서 생성",
    )
    pid = body.task.get("process_id") or (body.task.get("org_meta") or {}).get("process_id")
    return ProposalOut(
        proposal=text, task_process_id=pid, evidence=evidence,
        matching_version=MATCHING_VERSION, prompt_version=PROPOSE_PROMPT_VERSION,
    )


class ProposalRefineIn(BaseModel):
    proposal: str = Field(..., min_length=1, description="현재 제안서 MD")
    instruction: str = Field(..., min_length=1, description="수정 지시(예: '리스크 강화', '더 짧게')")


@router.post("/refine", response_model=ProposalOut)
def refine(
    body: ProposalRefineIn,
    _identity: Identity = Depends(current_identity),
) -> ProposalOut:
    """현재 제안서 MD + 사용자 지시 → 다듬은 제안서 MD (`sola.refine` 위임).

    SOLA 작업실의 '다시 생성/다듬기' — 처음부터 재생성 없이 기존 산출물을 반복 개선.
    """
    from sola.refine import refine_proposal

    persona = persona_store.load()
    text = _llm_or_http(
        lambda: refine_proposal(body.proposal, body.instruction, persona=persona),
        what="제안서 다듬기",
    )
    return ProposalOut(proposal=text)


class SummarizeIn(BaseModel):
    days: int = Field(default=3, ge=1, le=30)
    max_items: int = Field(default=20, ge=1, le=50)


@router.post("/summarize")
def summarize(body: SummarizeIn, _identity: Identity = Depends(current_identity)) -> dict:
    """최근 뉴스 요약 (SOLA 작업실 '뉴스 요약')."""
    from sola.summarize import summarize_news

    df = news_db.load_news_for_days(body.days)
    summary = _llm_or_http(
        lambda: summarize_news(df, max_items=body.max_items), what="뉴스 요약"
    )
    return {"summary": summary, "news_count": int(len(df))}
