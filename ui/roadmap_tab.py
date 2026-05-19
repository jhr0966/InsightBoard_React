"""로드맵 탭: 첨부 엑셀(Master_Table) 업로드 → 검증 → Parquet 저장."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from persona.schema import Persona
from roadmap.ingest import ingest_excel
from roadmap.query import by_dept, by_lv, load_latest
from ui.components import (
    render_html,
    metric_card,
    metric_grid,
    status_card,
    step_guide,
    step_item,
)
from ui.layout import main_and_chat
from ui.styles import page_header, section_label


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


def _build_page_context(df: pd.DataFrame) -> str:
    lines = ["화면: 제조기술 로드맵 (부서/공정 계층 집계)"]
    if df.empty:
        lines.append("(아직 업로드된 로드맵 없음)")
        return "\n".join(lines)
    lines.append(f"전체 작업: {len(df):,}건 · 부서 수: {df['dept'].nunique()}")
    dept = by_dept(df).head(10)
    lines.append("부서별 작업 수(상위 10): " + ", ".join(
        f"{r['dept']}={r['count']}" for _, r in dept.iterrows()
    ))
    lv3 = by_lv(df, "lv3").head(15)
    lines.append("Lv3 공정별 작업 수(상위 15): " + ", ".join(
        f"{r['lv3']}={r['count']}" for _, r in lv3.iterrows()
    ))
    return "\n".join(lines)


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    df = load_latest()

    page_header(
        "제조기술 로드맵",
        "첨부 엑셀 업로드 · 부서/공정 계층 집계",
        chat_toggle_key="roadmap",
    )

    with main_and_chat(
        "roadmap",
        page_context_fn=lambda: _build_page_context(df),
        persona=persona,
        hint="현재 로드맵 통계(부서·공정 집계)를 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            render_html(
                step_guide([
                    step_item(1, "엑셀 선택", "Master_Table 원본 파일을 업로드", active=True),
                    step_item(2, "시트 확인", "기본 시트명은 Master_Table"),
                    step_item(3, "검증·저장", "스키마 검증 후 Parquet DB 저장"),
                    step_item(4, "매칭 준비", "인사이트 분석에서 뉴스와 작업 연결"),
                ]),
                unsafe_allow_html=True,
            )

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

            render_html("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
            dept_count = (
                df["dept"].nunique()
                if not df.empty and "dept" in df.columns else 0
            )
            lv3_count = (
                df["lv3"].nunique()
                if not df.empty and "lv3" in df.columns else 0
            )
            render_html(
                metric_grid([
                    metric_card(
                        "로드맵 작업",
                        f"{len(df):,}건",
                        caption="저장된 작업 정의",
                        icon="🗂",
                        tone="teal",
                    ),
                    metric_card(
                        "부서 수",
                        f"{dept_count:,}",
                        caption="업로드된 조직 범위",
                        icon="🏭",
                        tone="ok" if dept_count else "warn",
                    ),
                    metric_card(
                        "Lv3 공정",
                        f"{lv3_count:,}",
                        caption="뉴스 매칭 기준 공정",
                        icon="⚙️",
                        tone="info" if lv3_count else "warn",
                    ),
                ]),
                unsafe_allow_html=True,
            )

            if df.empty:
                render_html(
                    status_card(
                        "로드맵 데이터가 없습니다",
                        "Master_Table 엑셀을 업로드·검증·저장하면 부서/공정 집계와 뉴스 매칭을 시작할 수 있습니다.",
                        status="warn",
                        icon="🗂",
                    ),
                    unsafe_allow_html=True,
                )
                return
            col1, col2 = st.columns(2)
            with col1:
                section_label("부서별 작업 수")
                st.dataframe(by_dept(df), use_container_width=True, hide_index=True)
            with col2:
                section_label("Lv3 (공정)별 작업 수")
                st.dataframe(by_lv(df, "lv3").head(20), use_container_width=True, hide_index=True)

            with st.expander("원본 보기 (상위 50행)"):
                st.dataframe(df.head(50), use_container_width=True, hide_index=True)
