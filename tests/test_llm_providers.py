"""LLM 제공자 추상화 — provider 선택 · OpenAI 스트리밍 · Anthropic 분기."""
from __future__ import annotations

from unittest.mock import patch

import pytest

import config
from sola import client as sola_client
from sola.providers import anthropic as anthropic_provider
from sola.providers.base import LLMNotConfigured, split_system


def test_provider_default_is_openai(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert config.llm_provider() == "openai"
    assert sola_client._provider_for() is sola_client._OpenAINS


@pytest.mark.parametrize("val", ["anthropic", "claude", "Claude", "ANTHROPIC"])
def test_provider_anthropic_aliases(monkeypatch, val):
    monkeypatch.setenv("LLM_PROVIDER", val)
    assert config.llm_provider() == "anthropic"
    assert sola_client._provider_for() is anthropic_provider


def test_split_system_extracts_and_joins():
    msgs = [
        {"role": "system", "content": "S1"},
        {"role": "user", "content": "U1"},
        {"role": "system", "content": "S2"},
        {"role": "assistant", "content": "A1"},
    ]
    system, rest = split_system(msgs)
    assert system == "S1\n\nS2"
    assert [m["role"] for m in rest] == ["user", "assistant"]


def test_openai_chat_stream_yields_pieces(monkeypatch):
    sola_client._client.cache_clear()
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_BACKEND", "groq")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "llama-3.3-70b-versatile")

    def _delta(text):
        return type("Chunk", (), {
            "choices": [type("C", (), {"delta": type("D", (), {"content": text})()})()]
        })()

    class _Completions:
        def create(self, **kw):
            assert kw["stream"] is True
            return iter([_delta("안녕"), _delta("하세요"), _delta(None)])

    class _FakeOpenAI:
        def __init__(self, **kw):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    with patch("openai.OpenAI", _FakeOpenAI):
        pieces = list(sola_client.chat_stream([{"role": "user", "content": "hi"}]))
    assert pieces == ["안녕", "하세요"]  # None 청크는 건너뜀
    sola_client._client.cache_clear()


def test_anthropic_is_configured_false_without_key(monkeypatch):
    anthropic_provider._client.cache_clear()
    monkeypatch.setenv("LLM_API_KEY", "")
    assert anthropic_provider.is_configured() is False


def test_anthropic_chat_maps_system_and_messages(monkeypatch):
    anthropic_provider._client.cache_clear()
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4-6")
    captured: dict = {}

    class _Block:
        type = "text"
        text = "응답"

    class _Resp:
        content = [_Block()]

    class _Messages:
        def create(self, **kw):
            captured.update(kw)
            return _Resp()

    class _FakeAnthropic:
        def __init__(self, **kw):
            self.messages = _Messages()

    import anthropic as _anthropic_sdk
    with patch.object(_anthropic_sdk, "Anthropic", _FakeAnthropic):
        out = anthropic_provider.chat([
            {"role": "system", "content": "너는 도우미"},
            {"role": "user", "content": "안녕"},
        ])
    assert out == "응답"
    assert captured["system"] == "너는 도우미"
    assert [m["role"] for m in captured["messages"]] == ["user"]
    anthropic_provider._client.cache_clear()
