"""api.routers.assistant — SSE 챗 스트리밍 (provider seam 경유)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from sola.providers.base import LLMNotConfigured

client = TestClient(app)


def test_chat_streams_sse_frames():
    def _fake_stream(messages, **kw):
        assert messages[0]["content"] == "안녕"
        yield "반"
        yield "가워"

    with patch("sola.client.chat_stream", _fake_stream):
        with client.stream(
            "POST", "/api/assistant/chat",
            json={"messages": [{"role": "user", "content": "안녕"}]},
        ) as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]
            text = "".join(r.iter_text())
    assert 'data: {"delta": "반"}' in text
    assert 'data: {"delta": "가워"}' in text
    assert 'data: {"done": true}' in text


def test_chat_emits_error_frame_when_not_configured():
    def _raise(messages, **kw):
        raise LLMNotConfigured("no key")
        yield  # pragma: no cover

    with patch("sola.client.chat_stream", _raise):
        with client.stream(
            "POST", "/api/assistant/chat",
            json={"messages": [{"role": "user", "content": "x"}]},
        ) as r:
            text = "".join(r.iter_text())
    assert '"error"' in text and "no key" in text


def test_status_endpoint():
    with patch("sola.client.is_configured", lambda: False):
        r = client.get("/api/assistant/status")
    assert r.status_code == 200
    assert r.json()["configured"] is False
    assert "provider" in r.json()
