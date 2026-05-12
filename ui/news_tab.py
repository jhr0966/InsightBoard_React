"""뉴스 콘텐츠 탭: 오늘 수집된 기사를 키워드 빈도/언론사별로 본다."""
from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from store.news_db import load_all_today
from ui.styles import page_header


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


def render() -> None:
    page_header("뉴스 콘텐츠", "오늘 수집된 기사 · 언론사/키워드 집계")

    df = load_all_today()
    if df.empty:
        st.info("오늘 수집된 기사가 없습니다. 먼저 [수집] 탭에서 검색하세요.")
        return

    st.caption(f"오늘 기사: {len(df):,}건")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**언론사 분포**")
        press = (
            df.groupby("press", dropna=False).size()
            .reset_index(name="count").sort_values("count", ascending=False, ignore_index=True)
        )
        st.dataframe(press.head(20), use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**키워드 빈도 (top 30)**")
        st.dataframe(_keyword_counts(df), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**전체 기사**")
    cols = [c for c in ("title", "press", "date", "link", "query") if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)
