"""작업 트리 드릴다운: 부서 → Lv1 → Lv2 → Lv3 → 작업.

각 단계 selectbox 에 '(전체)' 옵션 제공, 다음 단계 선택지는 상위 단계에 의존.
반환: (선택값 dict, 필터링된 DataFrame).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import render_html, status_card


def _select(label: str, df: pd.DataFrame, col: str, key: str) -> str | None:
    options = sorted(df[col].dropna().astype(str).unique().tolist()) if not df.empty and col in df.columns else []
    if not options:
        st.selectbox(label, ["(전체)"], key=key, disabled=True)
        return None
    chosen = st.selectbox(label, ["(전체)"] + options, key=key)
    return None if chosen == "(전체)" else chosen


def render_drilldown(
    roadmap_df: pd.DataFrame,
    *,
    key_prefix: str = "tt",
    show_task_picker: bool = False,
) -> tuple[dict, pd.DataFrame]:
    """반환:
      selection — {dept, lv1, lv2, lv3, task}
      filtered  — selection 적용된 DataFrame
    """
    if roadmap_df.empty:
        render_html(
            status_card(
                "작업 정의 데이터가 없습니다",
                "🧱 데이터 관리 → 작업 정의 데이터 업로드에서 엑셀을 업로드하세요.",
                status="warn",
                icon="🗂",
            ),
            unsafe_allow_html=True,
        )
        return {}, roadmap_df

    c1, c2, c3 = st.columns(3)
    with c1:
        dept = _select("부서", roadmap_df, "dept", f"{key_prefix}_dept")
    df = roadmap_df if not dept else roadmap_df[roadmap_df["dept"] == dept]

    with c2:
        lv1 = _select("분류(Lv1)", df, "lv1", f"{key_prefix}_lv1")
    if lv1:
        df = df[df["lv1"] == lv1]

    with c3:
        lv2 = _select("소분류(Lv2)", df, "lv2", f"{key_prefix}_lv2")
    if lv2:
        df = df[df["lv2"] == lv2]

    lv3 = _select("공정(Lv3)", df, "lv3", f"{key_prefix}_lv3")
    if lv3:
        df = df[df["lv3"] == lv3]

    selection: dict = {"dept": dept, "lv1": lv1, "lv2": lv2, "lv3": lv3, "task": None}
    if show_task_picker:
        tasks = sorted(df["task"].dropna().astype(str).unique().tolist()) if "task" in df.columns else []
        if tasks:
            task = st.selectbox("작업", ["(전체)"] + tasks, key=f"{key_prefix}_task")
            if task != "(전체)":
                selection["task"] = task
                df = df[df["task"] == task]

    st.caption(f"필터 적용: {len(df):,}건")
    return selection, df.reset_index(drop=True)
