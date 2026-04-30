from __future__ import annotations

import pandas as pd
import streamlit as st


def render_task_filters(tasks_df: pd.DataFrame) -> pd.DataFrame:
    """팀/공정 필터 UI를 렌더하고 필터된 DataFrame을 반환."""
    if tasks_df.empty:
        return tasks_df

    filtered = tasks_df.copy()
    c1, c2 = st.columns(2)

    if "team" in filtered.columns:
        teams = ["전체"] + sorted([str(v) for v in filtered["team"].dropna().unique()])
        selected_team = c1.selectbox("팀 필터", teams, index=0)
        if selected_team != "전체":
            filtered = filtered[filtered["team"].astype(str) == selected_team]
    else:
        c1.caption("팀 컬럼 없음")

    processes = ["전체"] + sorted([str(v) for v in filtered["process"].dropna().unique()])
    selected_process = c2.selectbox("공정 필터", processes, index=0)
    if selected_process != "전체":
        filtered = filtered[filtered["process"].astype(str) == selected_process]

    st.caption(f"필터 결과: {len(filtered)} / {len(tasks_df)}건")
    return filtered
