"""sola.client 의 설정 검증 분기 (실제 OpenAI 호출은 하지 않음)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from sola import client as sola_client


def test_chat_raises_when_base_url_missing(monkeypatch):
    sola_client._client.cache_clear()
    monkeypatch.setenv("LLM_BACKEND", "internal")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.setenv("LLM_MODEL", "anything")
    with pytest.raises(sola_client.LLMNotConfigured):
        sola_client.chat([{"role": "user", "content": "hi"}])


def test_chat_raises_when_api_key_missing_for_remote(monkeypatch):
    sola_client._client.cache_clear()
    monkeypatch.setenv("LLM_BACKEND", "groq")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "llama-3.3-70b-versatile")
    with pytest.raises(sola_client.LLMNotConfigured):
        sola_client.chat([{"role": "user", "content": "hi"}])


def test_is_configured_false_without_env(monkeypatch):
    sola_client._client.cache_clear()
    monkeypatch.setenv("LLM_BACKEND", "internal")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    assert sola_client.is_configured() is False


def test_chat_calls_openai_when_configured(monkeypatch):
    sola_client._client.cache_clear()
    monkeypatch.setenv("LLM_BACKEND", "groq")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "llama-3.3-70b-versatile")

    class _Msg:
        content = "안녕하세요."

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kw):
            assert kw["model"] == "llama-3.3-70b-versatile"
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **kw):
            self.chat = _Chat()

    with patch("openai.OpenAI", _FakeOpenAI):
        out = sola_client.chat([{"role": "user", "content": "hi"}])
    assert out == "안녕하세요."
