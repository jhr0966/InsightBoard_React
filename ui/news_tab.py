"""뉴스 콘텐츠 탭: 오늘 수집된 기사를 키워드 빈도/언론사별로 본다."""
from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from persona.schema import Persona
from store.news_db import load_all_today
from ui.components import status_card
from ui.layout import main_and_chat
from ui.styles import page_header, section_label


def _keyword_counts(df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
    if df.empty or "keywords" not in df.columns:
        return pd.DataFrame(columns=["keyword", "count"])
    tokens: list[str] = []
    for cell in df["keywords"].fillna("").astype(str):
        tokens.extend(t.strip() for t in cell.split(",") if t.strip())
    if not tokens:
        return pd.DataFrame(columns=["keyword", "count"])
    return (
        pd.DataFrame(Counter(tokens).most_common(top_n), columns=["keyword", "count"])
    )


def _build_page_context(df: pd.DataFrame) -> str:
    lines = ["화면: 뉴스 콘텐츠 (언론사·키워드 집계)"]
    if df.empty:
        lines.append("오늘 수집된 기사: 없음")
        return "\n".join(lines)
    lines.append(f"오늘 기사: {len(df):,}건")
    if "press" in df.columns:
        press_top = (
            df.groupby("press", dropna=False).size().sort_values(ascending=False).head(10)
        )
        lines.append("언론사 분포(상위 10): " + ", ".join(f"{idx}={cnt}" for idx, cnt in press_top.items()))
    kc = _keyword_counts(df, top_n=15)
    if not kc.empty:
        lines.append("키워드 빈도(상위 15): " + ", ".join(f"{r['keyword']}={r['count']}" for _, r in kc.iterrows()))
    return "\n".join(lines)


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    df = load_all_today()

    page_header(
        "뉴스 콘텐츠",
        "오늘 수집된 기사 · 언론사/키워드 집계",
        chat_toggle_key="news",
    )

    with main_and_chat(
        "news",
        page_context_fn=lambda: _build_page_context(df),
        persona=persona,
        hint="현재 표시 중인 언론사/키워드 분포를 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            if df.empty:
                st.markdown(
                    status_card(
                        "오늘 수집된 기사가 없습니다",
                        "먼저 🧱 데이터 관리 → 뉴스 수집에서 키워드 기반 수집을 실행하세요.",
                        status="warn",
                        icon="📰",
                    ),
                    unsafe_allow_html=True,
                )
                return

            st.caption(f"오늘 기사: {len(df):,}건")

            col1, col2 = st.columns(2)
            with col1:
                section_label("언론사 분포")
                press = (
                    df.groupby("press", dropna=False).size()
                    .reset_index(name="count").sort_values("count", ascending=False, ignore_index=True)
                )
                st.dataframe(press.head(20), use_container_width=True, hide_index=True)
            with col2:
                section_label("키워드 빈도 (top 30)")
                st.dataframe(_keyword_counts(df), use_container_width=True, hide_index=True)

            st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
            section_label("전체 기사")
            cols = [c for c in ("title", "press", "date", "link", "query") if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
