"""인사이트보드 탭: 트렌드 + 부서별 AI 인사이트 + 매칭 결과."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from sola import opportunity, trend_brief
from sola.client import is_configured as llm_ready
from sola.insight import insight_for_dept
from store import bookmarks, trends
from store.bookmarks import Bookmark
from store.match import score_matches
from store.news_db import load_all_today, load_news_for_days
from ui.layout import main_and_chat
from ui.styles import page_header, section_label


_PERIOD_OPTIONS = {
    "오늘": 1,
    "최근 7일": 7,
    "최근 30일": 30,
}


def _compute_trends_payload(news_today: pd.DataFrame):
    """기간 라디오 선택값을 읽어 (period_label, days, period_df, vol_df, emergence) 반환.

    UI 와 page_context 양쪽에서 같은 계산을 재사용.
    """
    period_label = st.session_state.get("board_period", "오늘")
    days = _PERIOD_OPTIONS.get(period_label, 1)
    period_df = news_today if days == 1 else load_news_for_days(days)
    vol_df = trends.daily_volume(period_df, days=days)

    if days > 1 and not period_df.empty:
        from datetime import datetime, timezone

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        is_today = period_df.get("date", pd.Series("", index=period_df.index)).astype(str).eq(today_str)
        today_only = period_df[is_today]
        base_only = period_df[~is_today]
        if not today_only.empty and not base_only.empty:
            emergence = trends.keyword_emergence(today_only, base_only, top_n=8)
        else:
            emergence = {
                "new": pd.DataFrame(columns=["keyword", "count"]),
                "gone": pd.DataFrame(columns=["keyword", "count"]),
                "rising": pd.DataFrame(columns=["keyword", "today", "base", "delta"]),
            }
    else:
        emergence = {
            "new": pd.DataFrame(columns=["keyword", "count"]),
            "gone": pd.DataFrame(columns=["keyword", "count"]),
            "rising": pd.DataFrame(columns=["keyword", "today", "base", "delta"]),
        }
    return period_label, days, period_df, vol_df, emergence


def _render_trends(news_today: pd.DataFrame) -> None:
    """다중 일자 트렌드. 라디오로 기간 선택, 일자별 라인 + 키워드 emergence + LLM brief."""
    period_label = st.radio(
        "기간",
        list(_PERIOD_OPTIONS.keys()),
        horizontal=True,
        key="board_period",
        label_visibility="collapsed",
    )
    _, days, period_df, vol_df, emergence = _compute_trends_payload(news_today)

    # ── 🧠 SOLA 의 한 줄 (LLM 해석 카드)
    brief_cache_key = f"_brief_text_{period_label}"
    cached_brief = st.session_state.get(brief_cache_key, "")
    bc1, bc2 = st.columns([5, 1])
    with bc1:
        st.markdown(
            f'<div class="card" style="margin-bottom:0.6rem;">'
            f'<div class="card-meta"><span class="card-press">🧠 SOLA 한 줄</span>'
            f'<span class="card-date">{html.escape(period_label)}</span></div>'
            f'<div class="card-body" style="-webkit-line-clamp:4;font-size:0.92rem;">'
            f'{html.escape(cached_brief or "버튼을 눌러 LLM 해석을 생성하세요.")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with bc2:
        if st.button(
            "갱신",
            key="_board_brief_btn",
            use_container_width=True,
            disabled=period_df.empty,
        ):
            st.session_state["_do_board_brief"] = True

    if st.session_state.pop("_do_board_brief", False):
        with st.spinner("LLM 호출 중…"):
            st.session_state[brief_cache_key] = trend_brief.brief(
                period_label=period_label, vol_df=vol_df, emergence=emergence,
            )
        st.rerun()

    st.caption(f"{period_label} · 기사 {len(period_df):,}건")

    col1, col2 = st.columns([2, 1])
    with col1:
        if vol_df["count"].sum() == 0:
            st.caption("(데이터 없음)")
        elif days == 1:
            st.bar_chart(vol_df.set_index("date"))
        else:
            st.line_chart(vol_df.set_index("date"))
    with col2:
        st.caption("소스별 분포")
        src_df = trends.by_source(period_df)
        if src_df.empty:
            st.caption("(데이터 없음)")
        else:
            st.dataframe(src_df, use_container_width=True, hide_index=True)

    # 키워드 emergence — days > 1 + 데이터 있을 때만 표시
    if days > 1 and (not emergence["new"].empty or not emergence["rising"].empty or not emergence["gone"].empty):
        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            st.markdown("**🆕 새 키워드**")
            if emergence["new"].empty:
                st.caption("(없음)")
            else:
                st.dataframe(emergence["new"], use_container_width=True, hide_index=True)
        with ec2:
            st.markdown("**📈 상승 키워드**")
            if emergence["rising"].empty:
                st.caption("(없음)")
            else:
                st.dataframe(
                    emergence["rising"][["keyword", "today", "delta"]],
                    use_container_width=True, hide_index=True,
                )
        with ec3:
            st.markdown("**📉 사라진 키워드**")
            if emergence["gone"].empty:
                st.caption("(없음)")
            else:
                st.dataframe(emergence["gone"], use_container_width=True, hide_index=True)


def _render_dept_insights(news: pd.DataFrame, roadmap: pd.DataFrame) -> None:
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
    st.caption("부서×공정 셀별 매칭 점수 누적. 상위 셀이 자동화 기회가 큰 곳.")

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
            b1, b2 = st.columns(2)
            with b1:
                if st.button(btn_label, key=f"opp_bm_{bm_id}", disabled=is_book, use_container_width=True):
                    bookmarks.add(Bookmark(
                        id=bm_id,
                        type="opportunity",
                        title=f"{row['dept']} · {row['lv3']}",
                        content=f"작업: {row['sample_tasks']}\n뉴스: {row['sample_news']}",
                        tags=[str(row["dept"]), str(row["lv3"])],
                    ))
                    st.session_state["board_msg"] = ("ok", f"북마크 저장: {row['dept']} · {row['lv3']}")
                    st.rerun()
            with b2:
                if st.button(
                    "🔗 매칭 뉴스",
                    key=f"opp_jump_{bm_id}",
                    use_container_width=True,
                    help="이 셀(부서·공정)의 매칭 뉴스만 아래 매칭 섹션에 표시합니다.",
                ):
                    st.session_state["_do_match_focus"] = {
                        "dept": str(row["dept"]),
                        "lv3": str(row["lv3"]),
                    }

    pending_focus = st.session_state.pop("_do_match_focus", None)
    if pending_focus is not None:
        st.session_state["board_match_focus"] = pending_focus
        st.session_state["board_msg"] = (
            "ok",
            f"🔗 '{pending_focus['dept']} · {pending_focus['lv3']}' 셀의 매칭 뉴스를 아래에서 확인하세요.",
        )
        st.rerun()

    msg = st.session_state.pop("board_msg", None)
    if msg:
        kind, text = msg
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](text)


def _matches_for_focus(news: pd.DataFrame, roadmap: pd.DataFrame, dept: str, lv3: str) -> pd.DataFrame:
    """매트릭스 셀 점프용 — (dept, lv3) 행에 대한 매칭 결과만 추출.

    빈 roadmap·뉴스·매칭 없음은 빈 DataFrame 반환. `_render_matches` 의 자유 필터 경로와
    분리된 stateless 함수 — 단위 테스트 가능.
    """
    if news.empty or roadmap.empty:
        return pd.DataFrame()
    if "dept" not in roadmap.columns or "lv3" not in roadmap.columns:
        return pd.DataFrame()
    sub = roadmap[(roadmap["dept"] == dept) & (roadmap["lv3"] == lv3)]
    if sub.empty:
        return pd.DataFrame()
    return score_matches(news, sub, top_k=3)


def _render_matches(news: pd.DataFrame, roadmap: pd.DataFrame) -> None:
    from ui import task_tree

    # 매트릭스 카드에서 점프해 들어온 경우: task_tree 필터를 우회하고 (dept, lv3) 직접 필터.
    focus = st.session_state.get("board_match_focus")
    if isinstance(focus, dict) and focus.get("dept") and focus.get("lv3"):
        f_dept = str(focus["dept"])
        f_lv3 = str(focus["lv3"])
        cl_col, _ = st.columns([4, 1])
        with cl_col:
            st.markdown(
                f'<div class="card-flat" style="margin-bottom:8px;">'
                f'🔗 매트릭스 셀 매칭 보기 — <b>{html.escape(f_dept)}</b> · '
                f'<b>{html.escape(f_lv3)}</b></div>',
                unsafe_allow_html=True,
            )
        if st.button("↩️ 전체 매칭 보기로 되돌리기", key="board_match_focus_clear"):
            st.session_state["_do_clear_match_focus"] = True
        if st.session_state.pop("_do_clear_match_focus", False):
            st.session_state.pop("board_match_focus", None)
            st.rerun()
        matches = _matches_for_focus(news, roadmap, f_dept, f_lv3)
        if matches.empty:
            st.info(f"'{f_dept} · {f_lv3}' 셀에 매칭되는 뉴스가 없습니다.")
            return
    else:
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


def _build_page_context(news: pd.DataFrame, roadmap: pd.DataFrame, persona: Persona) -> str:
    """인사이트보드 화면의 핵심 데이터를 LLM 컨텍스트로 압축."""
    lines: list[str] = ["화면: 인사이트보드 (트렌드 · 자동화 기회 매트릭스 · 부서 인사이트 · 매칭)"]
    if persona.is_set():
        lines.append(f"사용자 부서: {persona.dept or '-'} / 직무: {persona.job or '-'}")
    if news.empty or roadmap.empty:
        return "\n".join(lines)

    period_label, days, period_df, vol_df, emergence = _compute_trends_payload(news)
    lines.append(f"선택 기간: {period_label} ({days}일)")

    if not vol_df.empty:
        lines.append("일자별 기사 수: " + ", ".join(
            f"{r['date']}={r['count']}" for _, r in vol_df.iterrows()
        ))
    by_src = trends.by_source(period_df)
    if not by_src.empty:
        lines.append("소스 분포: " + ", ".join(
            f"{r['source']}={r['count']}" for r in by_src.head(5).to_dict(orient="records")
        ))

    if days > 1:
        if not emergence["new"].empty:
            lines.append("새 키워드(오늘만): " + ", ".join(
                f"{r['keyword']}={r['count']}" for _, r in emergence["new"].head(5).iterrows()
            ))
        if not emergence["rising"].empty:
            lines.append("상승 키워드(오늘↑base): " + ", ".join(
                f"{r['keyword']}(+{r['delta']})" for _, r in emergence["rising"].head(5).iterrows()
            ))

    # SOLA 가 생성한 brief(있으면) 도 컨텍스트로
    brief_text = st.session_state.get(f"_brief_text_{period_label}", "")
    if brief_text:
        lines.append(f"SOLA 한 줄 해석: {brief_text}")

    try:
        cells = opportunity.score_cells(news, roadmap, cell_level="lv3", top_k_per_task=5)
        if not cells.empty:
            lines.append("\n자동화 기회 매트릭스 상위 셀(부서 / 공정 / score):")
            for _, row in cells.head(8).iterrows():
                lines.append(
                    f"- {row['dept']} / {row['lv3']} (score={row['cell_score']:.1f}) "
                    f"sample_task={row['sample_tasks']}"
                )
    except Exception:  # noqa: BLE001
        pass

    return "\n".join(lines)


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    roadmap = load_roadmap()
    news = load_all_today()

    chat_open = page_header(
        "인사이트보드",
        "트렌드 · 자동화 기회 · 부서별 AI 인사이트 · 매칭",
        chat_toggle_key="board",
    )

    with main_and_chat(
        "board",
        page_context_fn=lambda: _build_page_context(news, roadmap, persona),
        persona=persona,
        hint="현재 보드(트렌드·매트릭스·부서 인사이트·매칭)를 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("로드맵 작업", f"{len(roadmap):,}건")
            col_b.metric("오늘 뉴스", f"{len(news):,}건")
            col_c.metric("부서 수", f"{roadmap['dept'].nunique() if not roadmap.empty else 0}")

            if roadmap.empty or news.empty:
                st.markdown(
                    '<div class="card-flat" style="margin-top:1.2rem;">'
                    '로드맵 업로드와 뉴스 수집을 먼저 진행하세요.</div>',
                    unsafe_allow_html=True,
                )
                return

            st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
            section_label("트렌드")
            _render_trends(news)

            st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
            section_label("자동화 기회 매트릭스")
            _render_opportunity(news, roadmap)

            st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
            section_label("부서별 AI 인사이트")
            _render_dept_insights(news, roadmap)

            st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
            section_label("계층 필터 · 뉴스 매칭")
            _render_matches(news, roadmap)
    _ = chat_open  # 채팅 토글 결과는 main_and_chat 내부에서 처리됨
