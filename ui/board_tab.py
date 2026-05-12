"""인사이트보드 탭: 트렌드 + 부서별 AI 인사이트 + 매칭 결과."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from roadmap.query import load_latest as load_roadmap
from sola import opportunity
from sola.client import is_configured as llm_ready
from sola.insight import insight_for_dept
from store import bookmarks, trends
from store.bookmarks import Bookmark
from store.match import score_matches
from store.news_db import load_all_today
from ui.styles import page_header


def _render_trends(news: pd.DataFrame) -> None:
    st.subheader("트렌드")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**일자별 기사 수**")
        date_df = trends.by_date(news)
        if date_df.empty:
            st.caption("(데이터 없음)")
        else:
            st.bar_chart(date_df.set_index("date"))
    with col2:
        st.markdown("**소스별 기사 수**")
        src_df = trends.by_source(news)
        if src_df.empty:
            st.caption("(데이터 없음)")
        else:
            st.dataframe(src_df, use_container_width=True, hide_index=True)


def _render_dept_insights(news: pd.DataFrame, roadmap: pd.DataFrame) -> None:
    st.subheader("부서별 AI 인사이트")
    st.caption("첫 호출만 LLM 사용, 동일 (부서·뉴스셋) 조합은 캐시에서 즉시 응답합니다.")

    if st.button("AI 인사이트 생성·갱신", key="board_insight_btn"):
        st.session_state["_do_dept_insight"] = True

    show = st.session_state.get("board_show_insight", False)
    if st.session_state.pop("_do_dept_insight", False):
        st.session_state["board_show_insight"] = True
        show = True
        st.rerun()

    if not show:
        st.info("위 버튼을 누르면 부서별 한 줄 인사이트가 생성됩니다.")
        return

    from persona.schema import Persona

    persona: Persona = st.session_state.get("persona") or Persona()
    depts_raw = sorted(roadmap["dept"].dropna().astype(str).unique().tolist())
    # 사용자 부서를 맨 앞으로
    if persona.dept and persona.dept in depts_raw:
        depts = [persona.dept] + [d for d in depts_raw if d != persona.dept]
    else:
        depts = depts_raw

    cols = st.columns(2)
    for i, dept in enumerate(depts):
        with cols[i % 2]:
            is_mine = persona.dept and dept == persona.dept
            border = "border: 2px solid var(--accent);" if is_mine else ""
            badge = "🎯 " if is_mine else ""
            text = insight_for_dept(dept, news)
            st.markdown(
                f"""
                <div class="news-card" style="min-height:auto; {border}">
                    <div class="card-meta">
                        <span class="card-press">{badge}{html.escape(dept)}</span>
                    </div>
                    <div class="card-body" style="-webkit-line-clamp: 6;">{html.escape(text)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_opportunity(news: pd.DataFrame, roadmap: pd.DataFrame) -> None:
    st.subheader("🚀 자동화 기회 매트릭스 (부서 × 공정)")
    st.caption("뉴스↔작업 매칭 점수를 셀 단위로 누적. 상위 셀이 자동화 기회가 큰 곳.")

    cells = opportunity.score_cells(news, roadmap, cell_level="lv3", top_k_per_task=5)
    if cells.empty:
        st.info("매칭되는 뉴스가 없습니다. 키워드 수집 또는 본문 Enrich 를 진행하세요.")
        return

    top_n = st.slider("상위 셀 개수", 3, 20, 8, key="board_opp_n")
    use_llm_comment = st.checkbox(
        "셀별 LLM 코멘트 사용 (캐시됨)", value=False, disabled=not llm_ready(),
        help="LLM 미설정 시 룰 기반 표만 표시됩니다.",
        key="board_opp_llm",
    )

    head = cells.head(top_n).copy()
    # 표 보기
    with st.expander("매트릭스 표 보기", expanded=False):
        st.dataframe(head, use_container_width=True, hide_index=True)

    # 카드 그리드 (2열)
    from persona.schema import Persona

    persona: Persona = st.session_state.get("persona") or Persona()
    existing_ids = {b.id for b in bookmarks.list_all(type_="opportunity")}

    cols = st.columns(2)
    for i, (_, row) in enumerate(head.iterrows()):
        bm_id = bookmarks.make_id("opportunity", str(row["dept"]), str(row["lv3"]))
        with cols[i % 2]:
            is_mine = persona.dept and row["dept"] == persona.dept
            border = "border: 2px solid var(--accent);" if is_mine else ""
            badge = "🎯 " if is_mine else ""
            comment_html = ""
            if use_llm_comment:
                c = opportunity.llm_commentary(
                    str(row["dept"]), str(row["lv3"]),
                    str(row["sample_news"]), str(row["sample_tasks"]),
                )
                if c:
                    comment_html = f'<div class="card-body" style="-webkit-line-clamp:5;">{html.escape(c)}</div>'

            st.markdown(
                f"""
                <div class="news-card" style="min-height:auto; {border}">
                    <div class="card-meta">
                        <span class="card-press">{badge}{html.escape(str(row['dept']))}</span>
                        <span class="card-date">{html.escape(str(row['lv3']))}</span>
                        <span class="card-num">score {row['cell_score']:.1f}</span>
                    </div>
                    <div class="card-title" style="font-size:0.9rem;">{html.escape(str(row['sample_tasks']))}</div>
                    {comment_html}
                    <div class="card-body" style="-webkit-line-clamp:3;">관련 뉴스: {html.escape(str(row['sample_news']))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            is_book = bm_id in existing_ids
            btn_label = "★ 북마크됨" if is_book else "☆ 북마크"
            if st.button(btn_label, key=f"opp_bm_{bm_id}", disabled=is_book):
                bookmarks.add(Bookmark(
                    id=bm_id,
                    type="opportunity",
                    title=f"{row['dept']} · {row['lv3']}",
                    content=f"작업: {row['sample_tasks']}\n뉴스: {row['sample_news']}",
                    tags=[str(row["dept"]), str(row["lv3"])],
                ))
                st.session_state["board_msg"] = ("ok", f"북마크 저장: {row['dept']} · {row['lv3']}")
                st.rerun()

    msg = st.session_state.pop("board_msg", None)
    if msg:
        kind, text = msg
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](text)


def _render_matches(news: pd.DataFrame, roadmap: pd.DataFrame) -> None:
    from persona.schema import Persona
    from ui import task_tree

    st.subheader("계층 필터 · 뉴스 매칭")
    # 페르소나 부서를 기본 필터로 미리 적용
    persona: Persona = st.session_state.get("persona") or Persona()
    if persona.dept and "board_dept" not in st.session_state:
        st.session_state["board_dept"] = persona.dept

    _selection, filtered = task_tree.render_drilldown(roadmap, key_prefix="board")
    if filtered.empty:
        st.warning("선택한 필터에 해당하는 작업이 없습니다.")
        return

    matches = score_matches(news, filtered, top_k=3)
    if matches.empty:
        st.info("매칭되는 뉴스가 없습니다. 다른 키워드로 수집해보세요.")
        return

    agg = (
        matches.groupby(["dept", "lv3", "task"], dropna=False)
        .agg(matched_news=("link", "nunique"), avg_score=("score", "mean"))
        .reset_index()
        .sort_values(["matched_news", "avg_score"], ascending=False, ignore_index=True)
    )
    st.dataframe(agg.head(30), use_container_width=True, hide_index=True)

    st.markdown("**매칭 상세 (상위 30)**")
    for _, row in matches.sort_values("score", ascending=False).head(30).iterrows():
        st.markdown(
            f"""
            <div class="news-card" style="min-height:auto;">
                <div class="card-meta">
                    <span class="card-press">{html.escape(str(row['dept']))}</span>
                    <span class="card-date">{html.escape(str(row['lv3']))} · {html.escape(str(row['task']))}</span>
                    <span class="card-num">score {row['score']:.1f}</span>
                </div>
                <div class="card-title">{html.escape(str(row['news_title']))}</div>
                <div class="card-link"><a href="{html.escape(str(row['link']))}" target="_blank">원문 보기 →</a></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render() -> None:
    page_header("인사이트보드", "트렌드 · 부서별 AI 인사이트 · 작업 매칭")

    roadmap = load_roadmap()
    news = load_all_today()

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("로드맵 작업", f"{len(roadmap):,}건")
    col_b.metric("오늘 뉴스", f"{len(news):,}건")
    col_c.metric("부서 수", f"{roadmap['dept'].nunique() if not roadmap.empty else 0}")

    if roadmap.empty or news.empty:
        st.info("로드맵 업로드와 뉴스 수집을 먼저 진행하세요.")
        return

    st.markdown("---")
    _render_trends(news)
    st.markdown("---")
    _render_opportunity(news, roadmap)
    st.markdown("---")
    _render_dept_insights(news, roadmap)
    st.markdown("---")
    _render_matches(news, roadmap)
