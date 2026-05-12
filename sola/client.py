"""OpenAI 호환 LLM 클라이언트.

`LLM_BACKEND` 에 따라 base_url 을 스위치하지만, SDK 호출 형태는 동일.
- groq    : https://api.groq.com/openai/v1 (임시 무료 기본)
- internal: 사내 API
- ollama  : http://localhost:11434/v1
"""
from __future__ import annotations

from functools import lru_cache

from config import llm_api_key, llm_backend, llm_base_url, llm_model


class LLMNotConfigured(RuntimeError):
    """API key 또는 base_url 미설정."""


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
    return OpenAI(base_url=base, api_key=key)


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = 1200,
) -> str:
    """단일 응답 chat completion. 오류는 그대로 던진다."""
    use_model = model or llm_model()
    if not use_model:
        raise LLMNotConfigured("LLM_MODEL 미지정.")
    resp = _client().chat.completions.create(
        model=use_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def is_configured() -> bool:
    try:
        _ = _client()
        return bool(llm_model())
    except LLMNotConfigured:
        return False
    except Exception:
        return False
