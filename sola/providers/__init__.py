"""LLM 제공자 추상화.

호출부(`sola/board_brief.py` 등)는 `sola.client.chat()`/`chat_stream()` 만 쓰고,
실제 제공자는 `config.llm_provider()` 로 결정된다:

- "openai"    → OpenAI 호환 (사내 SOLA(OpenAI 형식)·groq·ollama·openai) — `sola.client` 내장
- "anthropic" → 네이티브 Claude — `sola.providers.anthropic`

새 제공자는 `LLMProvider` 프로토콜(`chat`/`chat_stream`/`is_configured`)을 구현하고
`sola.client._provider_for()` 분기에 한 줄 추가하면 끝. 호출부·테스트는 불변.
"""
from sola.providers.base import LLMNotConfigured, LLMProvider, Message

__all__ = ["LLMNotConfigured", "LLMProvider", "Message"]
