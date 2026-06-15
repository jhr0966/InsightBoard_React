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
