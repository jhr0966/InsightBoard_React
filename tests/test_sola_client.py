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


def test_client_configured_with_timeout_and_retries(monkeypatch):
    """행 걸린 백엔드 방지 — 클라이언트에 명시 timeout + 재시도 설정 (백로그 4.4)."""
    sola_client._client.cache_clear()
    monkeypatch.setenv("LLM_BACKEND", "groq")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "llama-3.3-70b-versatile")

    captured: dict = {}

    class _Msg:
        content = "ok"

    class _Resp:
        choices = [type("C", (), {"message": _Msg()})()]

    class _Completions:
        def create(self, **kw):
            return _Resp()

    class _FakeOpenAI:
        def __init__(self, **kw):
            captured.update(kw)
            self.chat = type("Chat", (), {"completions": _Completions()})()

    with patch("openai.OpenAI", _FakeOpenAI):
        sola_client.chat([{"role": "user", "content": "hi"}])
    assert captured.get("timeout") == sola_client._CHAT_TIMEOUT
    assert captured.get("max_retries") == sola_client._MAX_RETRIES
    sola_client._client.cache_clear()  # 다른 테스트에 누수 방지
