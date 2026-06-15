"""LLM 클라이언트 facade — 제공자 추상화 진입점.

호출부는 `chat()` / `chat_stream()` / `is_configured()` 만 쓴다. 실제 제공자는
`config.llm_provider()` 가 고른다:

- "openai"    : OpenAI 호환 (사내 SOLA(OpenAI 형식)·groq·ollama·openai) — 이 모듈 내장.
                `LLM_BACKEND` 가 base_url 을, `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` 가 세부를 정한다.
- "anthropic" : 네이티브 Claude — `sola.providers.anthropic` 로 위임.

새 제공자 추가는 `sola/providers/<name>.py` + `_provider_for()` 에 한 줄. 호출부 불변.

하위호환: `LLMNotConfigured` 는 `sola.providers.base` 의 것을 re-export(동일 객체),
`_client` lru_cache(OpenAI SDK)도 그대로 유지한다(테스트가 `_client.cache_clear()` 사용).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from config import llm_api_key, llm_backend, llm_base_url, llm_model, llm_provider
from sola.providers import anthropic as _anthropic
from sola.providers.base import LLMNotConfigured, Message

__all__ = ["LLMNotConfigured", "chat", "chat_stream", "is_configured"]


# 행이 걸린 LLM 백엔드가 Streamlit rerun 을 무한정 멈추지 않게 명시 타임아웃 +
# 일시 오류 자동 재시도(SDK 내장). scraping.http 의 단일-진입 회복력과 동일 철학.
_CHAT_TIMEOUT = 45.0
_MAX_RETRIES = 2


# ── OpenAI 호환 제공자 (내장) ──────────────────────────────

@lru_cache(maxsize=4)
def _client():
    """OpenAI SDK 클라이언트. backend 가 바뀌면 캐시 키도 바뀐다."""
    from openai import OpenAI  # 지연 import — 테스트에서 mock 용이

    base = llm_base_url()
    key = llm_api_key()
    if not base:
        raise LLMNotConfigured("LLM_BASE_URL 이 비어 있습니다 (.env 확인).")
    if not key:
        # ollama 처럼 키 없이도 동작하는 백엔드를 위해 더미 키 허용
        key = "ollama" if llm_backend() == "ollama" else ""
        if not key:
            raise LLMNotConfigured("LLM_API_KEY 가 비어 있습니다 (.env 확인).")
    return OpenAI(base_url=base, api_key=key, timeout=_CHAT_TIMEOUT, max_retries=_MAX_RETRIES)


def _openai_model(model: str | None) -> str:
    use_model = model or llm_model()
    if not use_model:
        raise LLMNotConfigured("LLM_MODEL 미지정.")
    return use_model


def _openai_chat(messages, *, model=None, temperature=0.3, max_tokens=1200) -> str:
    resp = _client().chat.completions.create(
        model=_openai_model(model),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def _openai_chat_stream(messages, *, model=None, temperature=0.3, max_tokens=1200) -> Iterator[str]:
    stream = _client().chat.completions.create(
        model=_openai_model(model),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        piece = chunk.choices[0].delta.content
        if piece:
            yield piece


def _openai_is_configured() -> bool:
    try:
        _ = _client()
        return bool(llm_model())
    except LLMNotConfigured:
        return False
    except Exception:  # noqa: BLE001
        return False


# ── 제공자 선택 + facade ───────────────────────────────────

def _provider_for():
    """현재 설정의 제공자 모듈/네임스페이스. openai 는 이 모듈 자신의 함수들."""
    if llm_provider() == "anthropic":
        return _anthropic
    return _OpenAINS


class _OpenAINS:
    """OpenAI 호환 함수들을 제공자 인터페이스로 노출하는 네임스페이스."""
    chat = staticmethod(_openai_chat)
    chat_stream = staticmethod(_openai_chat_stream)
    is_configured = staticmethod(_openai_is_configured)


def chat(
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = 1200,
) -> str:
    """단일 응답 chat completion. 오류는 그대로 던진다."""
    return _provider_for().chat(
        messages, model=model, temperature=temperature, max_tokens=max_tokens
    )


def chat_stream(
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = 1200,
) -> Iterator[str]:
    """스트리밍 chat — 토큰/청크 제너레이터 (SSE 엔드포인트가 흘려보냄)."""
    return _provider_for().chat_stream(
        messages, model=model, temperature=temperature, max_tokens=max_tokens
    )


def is_configured() -> bool:
    return _provider_for().is_configured()
