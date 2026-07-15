"""자동화 과제 API — 생성(`sola.propose`) + **Proposal 엔터티**(Step 13, §15).

생성: 작업 × links 근거 → 제안서 초안(+근거·승인 사례).
보관: 범용 bookmark 가 아니라 `store.proposals_db` — 상태 확장
(idea→draft→reviewing→feasibility→poc_ready→poc_running→adopted/on_hold/rejected)
+ 전환 이력 보존 + PoC 결과 구조 필드. 구 bookmark 보관함은
`POST /api/proposals/migrate-bookmarks` 로 이관(원본 보존·멱등).
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
    cases: list[dict[str, Any]] = Field(default_factory=list, description="주입된 승인 사례")
    matching_version: int | None = None
    prompt_version: int | None = None


@router.post("/generate", response_model=ProposalOut)
def generate(
    body: ProposalGenerateIn,
    identity: Identity = Depends(current_identity),
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
    # 승인(approved) 사례만 주근거로 추가 주입(§14-3) — 근거 기사와 연결된 사례.
    from store import cases_db

    approved_cases = cases_db.approved_for_articles(
        [str(e.get("article_id", "")) for e in evidence])[:2]

    persona = persona_store.load(identity.user_id)
    text = _llm_or_http(
        lambda: propose_for_task(body.task, news_df, persona=persona,
                                 evidence=evidence, cases=approved_cases),
        what="제안서 생성",
    )
    pid = body.task.get("process_id") or (body.task.get("org_meta") or {}).get("process_id")
    return ProposalOut(
        proposal=text, task_process_id=pid, evidence=evidence, cases=approved_cases,
        matching_version=MATCHING_VERSION, prompt_version=PROPOSE_PROMPT_VERSION,
    )


class ProposalRefineIn(BaseModel):
    proposal: str = Field(..., min_length=1, description="현재 제안서 MD")
    instruction: str = Field(..., min_length=1, description="수정 지시(예: '리스크 강화', '더 짧게')")


@router.post("/refine", response_model=ProposalOut)
def refine(
    body: ProposalRefineIn,
    identity: Identity = Depends(current_identity),
) -> ProposalOut:
    """현재 제안서 MD + 사용자 지시 → 다듬은 제안서 MD (`sola.refine` 위임).

    SOLA 작업실의 '다시 생성/다듬기' — 처음부터 재생성 없이 기존 산출물을 반복 개선.
    """
    from sola.refine import refine_proposal

    persona = persona_store.load(identity.user_id)
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


# ── Proposal 엔터티 (Step 13) ──────────────────────────────────

from store import proposals_db  # noqa: E402


class ProposalSaveIn(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = ""
    task_id: str = ""
    article_ids: list[str] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)
    matching_version: int = 0
    prompt_version: int = 0
    status: str = Field(default="draft")


@router.post("/save")
def save_proposal(body: ProposalSaveIn,
                  identity: Identity = Depends(current_identity)) -> dict:
    """생성된 제안서를 Proposal 엔터티로 보관 — 근거 관계 포함(§11-3·§15)."""
    try:
        return proposals_db.create(
            title=body.title, content=body.content, task_id=body.task_id,
            article_ids=body.article_ids, case_ids=body.case_ids,
            matching_version=body.matching_version, prompt_version=body.prompt_version,
            status=body.status, user=identity.user_id, workspace=identity.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/list")
def list_proposals(status: str | None = None,
                   identity: Identity = Depends(current_identity)) -> list[dict]:
    if status and status not in proposals_db.STATUSES:
        raise HTTPException(status_code=422, detail=f"unknown status: {status}")
    return proposals_db.list_all(user=identity.user_id, status=status)


@router.get("/summary")
def proposals_summary(identity: Identity = Depends(current_identity)) -> dict:
    return proposals_db.summary(user=identity.user_id)


class ProposalStatusIn(BaseModel):
    status: str
    note: str = ""


@router.patch("/{proposal_id}/status")
def proposal_status(proposal_id: str, body: ProposalStatusIn,
                    identity: Identity = Depends(current_identity)) -> dict:
    """상태 전환 — proposal_history 에 이력 보존(§15)."""
    try:
        out = proposals_db.set_status(proposal_id, body.status, note=body.note,
                                      user=identity.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if out is None:
        raise HTTPException(status_code=404, detail="과제를 찾을 수 없습니다.")
    return out


class ProposalFieldsIn(BaseModel):
    fields: dict[str, Any] = Field(..., description="owner·partner_depts·준비도·비용/기간·expected_kpi·poc_result 등")


@router.patch("/{proposal_id}")
def proposal_fields(proposal_id: str, body: ProposalFieldsIn,
                    _identity: Identity = Depends(current_identity)) -> dict:
    out = proposals_db.update_fields(proposal_id, body.fields)
    if out is None:
        raise HTTPException(status_code=404, detail="과제를 찾을 수 없습니다.")
    return out


@router.get("/{proposal_id}/history")
def proposal_history(proposal_id: str) -> list[dict]:
    return proposals_db.history(proposal_id)


@router.delete("/{proposal_id}")
def delete_proposal(proposal_id: str,
                    _identity: Identity = Depends(current_identity)) -> dict:
    return {"deleted": proposals_db.delete(proposal_id)}


@router.post("/migrate-bookmarks")
def migrate_bookmarks(_identity: Identity = Depends(current_identity)) -> dict:
    """구 bookmark(type=proposal) → Proposal 엔터티 이관 (원본 보존·멱등).

    이관본은 legacy=true, 근거 meta 없으면 evidence_unavailable=true(§11-3).
    """
    return proposals_db.migrate_from_bookmarks()
