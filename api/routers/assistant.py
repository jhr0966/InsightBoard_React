"""어시스턴트 챗 API — SSE 스트리밍 (`REACT_MIGRATION_PLAN` 0.5-C 결정).

`sola.client.chat_stream()` 으로 제공자(OpenAI 호환 / Claude)에 무관하게 토큰을
흘려보낸다. 프런트(React)는 `EventSource`/fetch-stream 으로 소비한다.

SSE 프레임:
  data: {"delta": "..."}   # 토큰 조각 (여러 번)
  data: {"done": true}     # 정상 종료
  data: {"error": "..."}   # 스트림 도중 오류
"""
from __future__ import annotations

import json
from typing import Iterator, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.deps import Identity, current_identity
from sola import client as llm
from sola.providers.base import LLMNotConfigured

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="system | user | assistant")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: Optional[int] = 1200


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat", response_class=StreamingResponse)
def chat_stream(
    body: ChatRequest,
    _identity: Identity = Depends(current_identity),
) -> StreamingResponse:
    """챗 응답을 SSE 로 스트리밍. 제공자는 `config.llm_provider()` 가 결정."""
    messages = [m.model_dump() for m in body.messages]

    def _gen() -> Iterator[str]:
        try:
            for piece in llm.chat_stream(
                messages,
                model=body.model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            ):
                yield _sse({"delta": piece})
            yield _sse({"done": True})
        except LLMNotConfigured as exc:
            yield _sse({"error": f"LLM 미설정: {exc}"})
        except Exception as exc:  # noqa: BLE001 — 스트림 도중 오류도 클라이언트에 전달
            yield _sse({"error": str(exc)})

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/status", tags=["assistant"])
def status() -> dict:
    """LLM 설정 상태 — 프런트가 챗 활성화 여부 판단."""
    from config import llm_provider

    return {"configured": llm.is_configured(), "provider": llm_provider()}


# 화면별 컨텍스트 — UI 의 chat_context_block 일반화(서버 데이터 기반).
_SCREENS = ("board", "insights", "collect", "taskdefs", "proposals")


def _screen_digest(screen: str, days: int) -> tuple[str, int]:
    """화면별 데이터 다이제스트 — '현재 화면에 떠있는 것' Q&A 근거. (텍스트, 뉴스건수).

    가벼운 소스만(뉴스 키워드 + 보관함 요약 + 작업정의 수). 무거운 기회 재계산은
    매 전송마다 돌면 느려지므로 제외하고, 관심 작업정의(아래 task_context)가 보드/
    인사이트 화면의 풍부한 근거를 대신한다.
    """
    from store import news_db, trends

    df = news_db.load_news_for_days(days)
    n = int(len(df))
    lines = [
        f"## 현재 화면: {screen}",
        f"## 최근 {days}일 뉴스 {n}건",
    ]
    kw = trends.top_keywords(df, top_n=10)
    kw_line = ", ".join(f"{r['keyword']}({r['count']})" for r in kw.to_dict("records"))
    lines.append(f"## 상위 키워드: {kw_line or '없음'}")

    if screen == "proposals":
        from store import proposals_db
        try:
            sc = proposals_db.summary()
            by = sc.get("by_status", {})
            lines.append(
                f"## 과제 보관함: 총 {sc.get('total', 0)} · 검토중 {by.get('reviewing', 0)}"
                f" · PoC {by.get('poc_running', 0)} · 채택 {by.get('adopted', 0)}"
            )
        except Exception:  # noqa: BLE001
            pass
    elif screen == "taskdefs":
        from store import task_defs_db
        try:
            lines.append(f"## 등록된 작업정의 {task_defs_db.count()}건")
        except Exception:  # noqa: BLE001
            pass
    return "\n".join(lines), n


@router.get("/context")
def context(
    screen: str = "board",
    days: int = 7,
    query: str = "",
    identity: Identity = Depends(current_identity),
) -> dict:
    """현재 화면 컨텍스트를 system 메시지용 문자열로 패키징.

    포함(과부하 방지 캡 적용):
      1. 페르소나 안내
      2. 현재 화면 데이터 다이제스트(뉴스 키워드 + 화면별 요약)
      3. 페르소나 관심 공정 작업정의(matched_processes 로 좁힌 baseline)
      4. 사용자 질의(query)에 언급된 작업의 작업정의

    `labels` 는 드로어가 "📎 주입된 컨텍스트" 로 노출해 무엇이 들어갔는지 보이게 한다.
    """
    from persona import context as persona_ctx
    from persona import store as persona_store
    from sola import task_context

    persona = persona_store.load(identity.user_id)
    parts: list[str] = []
    labels: list[str] = []

    pblock = persona_ctx.system_block(persona)
    if pblock:
        parts.append(pblock)
        if persona.is_set():
            labels.append(f"페르소나·{persona.dept or '-'}")

    digest, news_count = _screen_digest(screen, days)
    parts.append(digest)
    labels.append("현재 화면")

    # 페르소나 관심 공정 작업정의 baseline (matched_processes → 캡 주입)
    tctx, tlabels = task_context.persona_task_context(persona)
    if tctx:
        parts.append(tctx)
        labels.append(f"관심 작업정의 {len(tlabels)}건")

    # 질의에 언급된 작업의 작업정의 (특정 작업 질문 시)
    if query.strip():
        mctx, mlabels = task_context.mentioned_task_context(query)
        if mctx:
            parts.append(mctx)
            labels.append("언급 작업·" + ", ".join(mlabels[:2]))

    return {
        "screen": screen if screen in _SCREENS else "board",
        "context": "\n\n".join(p for p in parts if p),
        "labels": labels,
        "news_count": news_count,
    }
