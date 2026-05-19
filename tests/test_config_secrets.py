"""config — 환경변수 / Streamlit Secrets fallback 우선순위."""
from __future__ import annotations

import sys
import types

import pytest

import config


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """LLM_* 환경변수 4종을 비운다 (호스트 환경 의존 제거)."""
    for k in ("LLM_BACKEND", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)


def _install_fake_streamlit(monkeypatch, secrets: dict | None) -> None:
    """st.secrets 동작을 흉내내는 fake module 주입."""
    fake = types.ModuleType("streamlit")
    if secrets is None:
        # secrets 속성 없는 streamlit 도 흉내낼 수 있게.
        pass
    else:
        class _Secrets(dict):
            def get(self, k, default=None):
                return dict.get(self, k, default)

        fake.secrets = _Secrets(secrets)
    monkeypatch.setitem(sys.modules, "streamlit", fake)


def test_env_takes_precedence_over_secrets(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "env_key")
    _install_fake_streamlit(monkeypatch, {"LLM_API_KEY": "secret_key"})
    assert config.llm_api_key() == "env_key"


def test_secrets_fallback_when_env_missing(monkeypatch):
    _install_fake_streamlit(monkeypatch, {"LLM_API_KEY": "gsk_from_secrets"})
    assert config.llm_api_key() == "gsk_from_secrets"


def test_empty_when_neither_set(monkeypatch):
    _install_fake_streamlit(monkeypatch, {})
    assert config.llm_api_key() == ""


def test_backend_default_groq_when_nothing_set(monkeypatch):
    _install_fake_streamlit(monkeypatch, {})
    assert config.llm_backend() == "groq"
    assert config.llm_base_url() == "https://api.groq.com/openai/v1"
    assert config.llm_model() == "llama-3.3-70b-versatile"


def test_streamlit_missing_does_not_crash(monkeypatch):
    """streamlit import 자체가 실패해도 빈 값으로 fallback."""
    # streamlit 을 ImportError 나게 강제.
    monkeypatch.setitem(sys.modules, "streamlit", None)
    # `import streamlit as st` 가 raises → except 로 default 반환.
    assert config.llm_api_key() == ""


def test_secrets_attribute_missing_does_not_crash(monkeypatch):
    """st 모듈은 있지만 secrets 속성이 없는 경우 (로컬에서 secrets.toml 없음)."""
    _install_fake_streamlit(monkeypatch, secrets=None)
    assert config.llm_api_key() == ""
