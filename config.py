"""전역 설정. 환경변수와 경로 상수를 한 곳에 모은다.

읽는 위치는 import 시점이 아니라 함수 호출 시점이라 테스트에서 monkeypatch 가능.

LLM 설정 우선순위:
  1. 프로세스 환경변수 (`.env` 파일 포함, `python-dotenv` 가 자동 로드)
  2. Streamlit Cloud `st.secrets` (`share.streamlit.io` 의 App settings → Secrets)
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


REPO_ROOT = Path(__file__).resolve().parent
# DATA_ROOT 은 `INSIGHTBOARD_DATA_ROOT` 로 오버라이드 가능 — Vercel 등 읽기전용
# 파일시스템(쓰기는 /tmp 만 허용)에서 `INSIGHTBOARD_DATA_ROOT=/tmp/data` 로 띄운다.
_DATA_ENV = os.getenv("INSIGHTBOARD_DATA_ROOT", "").strip()
DATA_ROOT = Path(_DATA_ENV).expanduser() if _DATA_ENV else REPO_ROOT / "data"
NEWS_DIR = DATA_ROOT / "news"
ROADMAP_DIR = DATA_ROOT / "roadmap"
SOLA_DIR = DATA_ROOT / "sola"
ASSETS_DIR = REPO_ROOT / "assets"

# cron 일일 수집 + '지금 수집'(빈 키워드) 폴백 기본 키워드.
# 광범위 2종으로 단순화 — 너무 많은 키워드는 수집을 느리게/노이즈를 키운다.
# GH Actions workflow_dispatch 인자 / UI 키워드 입력으로 override 가능.
DEFAULT_DAILY_KEYWORDS: tuple[str, ...] = (
    "AI",
    "자동화",
)


def ensure_data_dirs() -> None:
    for p in (NEWS_DIR, ROADMAP_DIR, SOLA_DIR):
        p.mkdir(parents=True, exist_ok=True)


def _env_or_secret(name: str, default: str = "") -> str:
    """환경변수 우선 → 없으면 Streamlit `st.secrets` fallback.

    Streamlit Cloud(share.streamlit.io) 배포 시 App settings → Secrets 에
    TOML 로 입력한 값이 여기로 들어온다. 로컬 실행에서는 streamlit context 가
    없거나 secrets.toml 이 없을 수 있으므로 모든 예외를 흡수해 빈 문자열 반환.
    """
    val = os.getenv(name, "").strip()
    if val:
        return val
    try:
        import streamlit as st

        if not hasattr(st, "secrets"):
            return default
        return str(st.secrets.get(name, default) or default).strip()
    except Exception:  # noqa: BLE001 — streamlit 미설치/secrets 미설정 등 모두 fallback.
        return default


def llm_provider() -> str:
    """LLM 제공자 계열 — 호출 SDK/메시지 포맷을 결정한다.

    - "openai"    : OpenAI 호환 (groq · 사내 SOLA(OpenAI 형식) · ollama · openai).
                    base_url/api_key/model 만 바꾸면 되는 모든 백엔드.
    - "anthropic" : 네이티브 Claude(Anthropic) API. (별칭 "claude")

    `LLM_BACKEND` 는 OpenAI 호환 계열 안에서 base_url 을 고르는 하위 스위치로 남는다.
    """
    p = _env_or_secret("LLM_PROVIDER", "openai").strip().lower()
    return "anthropic" if p in ("anthropic", "claude") else "openai"


def llm_backend() -> str:
    return _env_or_secret("LLM_BACKEND", "groq").strip().lower()


def llm_base_url() -> str:
    backend = llm_backend()
    explicit = _env_or_secret("LLM_BASE_URL", "").strip()
    if explicit:
        return explicit
    return {
        "groq": "https://api.groq.com/openai/v1",
        "internal": "",
        "ollama": "http://localhost:11434/v1",
    }.get(backend, "")


def llm_api_key() -> str:
    return _env_or_secret("LLM_API_KEY", "").strip()


def llm_model() -> str:
    backend = llm_backend()
    explicit = _env_or_secret("LLM_MODEL", "").strip()
    if explicit:
        return explicit
    return {
        "groq": "llama-3.3-70b-versatile",
        "internal": "",
        "ollama": "llama3.1",
    }.get(backend, "")
