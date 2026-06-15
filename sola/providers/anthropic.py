"""네이티브 Claude(Anthropic) 제공자.

`LLM_PROVIDER=anthropic`(또는 `claude`) 일 때 사용. OpenAI 형식 messages 를
Anthropic Messages API 형태(system 분리)로 변환한다. `anthropic` SDK 는 지연
import — 미설치/미설정이면 `LLMNotConfigured`.

설정(env/secrets):
  LLM_API_KEY   Anthropic API key (또는 사내 Claude 프록시 키)
  LLM_MODEL     모델 (기본 claude-sonnet-4-6)
  LLM_BASE_URL  (선택) 사내 프록시 base_url
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from config import llm_api_key, llm_base_url, llm_model
from sola.providers.base import LLMNotConfigured, Message, split_system

_DEFAULT_MODEL = "claude-sonnet-4-6"
_TIMEOUT = 45.0
_MAX_RETRIES = 2


@lru_cache(maxsize=2)
def _client():
    try:
        import anthropic  # noqa: F401 — 지연 import (선택 의존성)
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise LLMNotConfigured(
            "anthropic SDK 미설치 — `pip install anthropic` (LLM_PROVIDER=anthropic)"
        ) from exc
    key = llm_api_key()
    if not key:
        raise LLMNotConfigured("LLM_API_KEY 가 비어 있습니다 (Anthropic).")
    kwargs = {"api_key": key, "timeout": _TIMEOUT, "max_retries": _MAX_RETRIES}
    base = llm_base_url()
    if base:
        kwargs["base_url"] = base
    return anthropic.Anthropic(**kwargs)


def _model() -> str:
    return llm_model() or _DEFAULT_MODEL


def chat(
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = 1200,
) -> str:
    system, convo = split_system(messages)
    resp = _client().messages.create(
        model=model or _model(),
        max_tokens=max_tokens or 1200,
        temperature=temperature,
        system=system or None,
        messages=convo,  # type: ignore[arg-type]
    )
    parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return "".join(parts).strip()


def chat_stream(
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = 1200,
) -> Iterator[str]:
    system, convo = split_system(messages)
    with _client().messages.stream(
        model=model or _model(),
        max_tokens=max_tokens or 1200,
        temperature=temperature,
        system=system or None,
        messages=convo,  # type: ignore[arg-type]
    ) as stream:
        for text in stream.text_stream:
            if text:
                yield text


def is_configured() -> bool:
    try:
        _ = _client()
        return bool(_model())
    except LLMNotConfigured:
        return False
    except Exception:  # noqa: BLE001
        return False
