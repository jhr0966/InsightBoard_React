"""로드맵 탭: 첨부 엑셀(Master_Table) 업로드 → 검증 → Parquet 저장."""
from __future__ import annotations

import io

import streamlit as st

from roadmap.ingest import ingest_excel
from roadmap.query import by_dept, by_lv, load_latest
from ui.styles import page_header


def _do_ingest() -> None:
    upload = st.session_state.get("rm_upload")
    if upload is None:
        st.session_state["rm_status"] = ("warn", "엑셀 파일을 먼저 업로드하세요.")
        return
    buf = io.BytesIO(upload.getvalue())
    sheet = st.session_state.get("rm_sheet", "Master_Table") or "Master_Table"
    result = ingest_excel(buf, sheet_name=sheet)
    if not result.ok:
        st.session_state["rm_status"] = ("error", "  /  ".join(result.errors))
        return
    st.session_state["rm_status"] = (
        "ok",
        f"{result.row_count:,}행 저장 완료 → {result.parquet_path}",
    )


def render() -> None:
    page_header("제조기술 로드맵", "첨부 엑셀 업로드 · 부서/공정 계층 집계")

    st.file_uploader("Master_Table.xlsx", type=["xlsx", "xlsm"], key="rm_upload")
    st.text_input("시트명", value="Master_Table", key="rm_sheet")

    if st.button("업로드·검증·저장", type="primary"):
        st.session_state["_do_ingest"] = True

    if st.session_state.pop("_do_ingest", False):
        _do_ingest()
        st.rerun()

    status = st.session_state.get("rm_status")
    if status:
        kind, msg = status
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](msg)

    st.markdown("---")
    df = load_latest()
    if df.empty:
        st.info("아직 업로드된 로드맵이 없습니다.")
        return

    st.caption(f"현재 로드맵: {len(df):,}행")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**부서별 작업 수**")
        st.dataframe(by_dept(df), use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**Lv3(공정)별 작업 수**")
        st.dataframe(by_lv(df, "lv3").head(20), use_container_width=True, hide_index=True)

    with st.expander("원본 보기 (상위 50행)"):
        st.dataframe(df.head(50), use_container_width=True, hide_index=True)
