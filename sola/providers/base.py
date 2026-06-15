"""LLM 제공자 공통 계약 — 프로토콜 + 예외 + 메시지 타입.

`LLMNotConfigured` 는 과거 `sola.client` 에 정의돼 있던 것을 옮긴 것이다. 하위호환을
위해 `sola.client` 가 이 클래스를 그대로 re-export 하므로 기존
`from sola.client import LLMNotConfigured` 는 **동일 객체**를 가리킨다.
"""
from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

#: chat 메시지 — OpenAI 포맷 {"role": "system|user|assistant", "content": str}.
Message = dict


class LLMNotConfigured(RuntimeError):
    """API key / base_url / 모델 / SDK 미설정."""


@runtime_checkable
class LLMProvider(Protocol):
    """제공자 구현이 만족해야 하는 최소 인터페이스."""

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = 1200,
    ) -> str:
        """단일 응답(블로킹). 미설정/오류는 예외로 던진다."""
        ...

    def chat_stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = 1200,
    ) -> Iterator[str]:
        """토큰/청크 스트림 — SSE 엔드포인트가 그대로 흘려보낸다."""
        ...

    def is_configured(self) -> bool:
        """호출 가능 상태면 True (네트워크 호출 없이 설정만 점검)."""
        ...


def split_system(messages: list[Message]) -> tuple[str, list[Message]]:
    """OpenAI 형식 messages 에서 system 을 분리.

    Anthropic 처럼 system 을 별도 파라미터로 받는 제공자용 헬퍼.
    여러 system 메시지는 줄바꿈으로 합친다.
    """
    systems = [str(m.get("content", "")) for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    return "\n\n".join(s for s in systems if s), rest
