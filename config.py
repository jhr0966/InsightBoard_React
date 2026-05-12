"""전역 설정. 환경변수와 경로 상수를 한 곳에 모은다.

읽는 위치는 import 시점이 아니라 함수 호출 시점이라 테스트에서 monkeypatch 가능.
"""
from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DATA_ROOT = REPO_ROOT / "data"
NEWS_DIR = DATA_ROOT / "news"
ROADMAP_DIR = DATA_ROOT / "roadmap"
SOLA_DIR = DATA_ROOT / "sola"
ASSETS_DIR = REPO_ROOT / "assets"


def ensure_data_dirs() -> None:
    for p in (NEWS_DIR, ROADMAP_DIR, SOLA_DIR):
        p.mkdir(parents=True, exist_ok=True)


def llm_backend() -> str:
    return os.getenv("LLM_BACKEND", "groq").strip().lower()


def llm_base_url() -> str:
    backend = llm_backend()
    explicit = os.getenv("LLM_BASE_URL", "").strip()
    if explicit:
        return explicit
    return {
        "groq": "https://api.groq.com/openai/v1",
        "internal": "",
        "ollama": "http://localhost:11434/v1",
    }.get(backend, "")


def llm_api_key() -> str:
    return os.getenv("LLM_API_KEY", "").strip()


def llm_model() -> str:
    backend = llm_backend()
    explicit = os.getenv("LLM_MODEL", "").strip()
    if explicit:
        return explicit
    return {
        "groq": "llama-3.3-70b-versatile",
        "internal": "",
        "ollama": "llama3.1",
    }.get(backend, "")
