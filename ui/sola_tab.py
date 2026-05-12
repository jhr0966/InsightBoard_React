"""SOLA(AI 분석 엔진) 탭. M1에서는 상태 안내만, 본격 구현은 M2."""
from __future__ import annotations

import streamlit as st

from config import llm_backend, llm_base_url, llm_model
from ui.styles import page_header


def render() -> None:
    page_header("SOLA", "AI 분석 엔진 (M2 예정)")

    st.info(
        "M1은 룰 기반 매칭까지만 제공합니다. "
        "M2에서 뉴스 요약·작업 매핑·자동화 과제 추출을 OpenAI 호환 LLM(기본 Groq, 사내 API 전환 가능)으로 붙입니다."
    )

    st.markdown("### 현재 LLM 라우팅 설정")
    st.json({
        "backend": llm_backend(),
        "base_url": llm_base_url() or "(미설정)",
        "model": llm_model() or "(미설정)",
        "api_key": "**** (설정됨)" if _has_key() else "(미설정)",
    })
    st.caption(".env 의 LLM_BACKEND / LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 로 전환합니다.")


def _has_key() -> bool:
    import os

    return bool(os.getenv("LLM_API_KEY", "").strip())
