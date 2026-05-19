"""인사이트보드 탭: 트렌드 + 부서별 AI 인사이트 + 매칭 결과."""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timezone

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
from ui.components import (
    metric_card,
    metric_grid,
    render_html,
    status_card,
    step_guide,
    step_item,
)
from ui.layout import main_and_chat
from ui.styles import page_header, section_label


_PERIOD_OPTIONS = {
    "오늘": 1,
    "최근 7일": 7,
    "최근 30일": 30,
}


# ---------- Data payloads ----------


@dataclass(frozen=True)
class _TrendsPayload:
    period_label: str
    days: int
    period_df: pd.DataFrame
    vol_df: pd.DataFrame
    emergence: dict[str, pd.DataFrame]


def _empty_emergence() -> dict[str, pd.DataFrame]:
    return {
        "new": pd.DataFrame(columns=["keyword", "count"]),
        "gone": pd.DataFrame(columns=["keyword", "count"]),
        "rising": pd.DataFrame(columns=["keyword", "today", "base", "delta"]),
    }


def _compute_trends_payload(news_today: pd.DataFrame) -> _TrendsPayload:
    """기간 라디오 선택값을 읽어 트렌드 페이로드를 반환.

    UI와 page_context 양쪽에서 같은 결과를 재사용하기 위해 한 곳에서만 계산한다.
    """
    period_label = st.session_state.get("board_period", "오늘")
    days = _PERIOD_OPTIONS.get(period_label, 1)
    period_df = news_today if days == 1 else load_news_for_days(days)
    vol_df = trends.daily_volume(period_df, days=days)
    emergence = _empty_emergence()
    if days > 1 and not period_df.empty:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        is_today = period_df.get("date", pd.Series("", index=period_df.index)).astype(str).eq(today_str)
        today_only = period_df[is_today]
        base_only = period_df[~is_today]
        if not today_only.empty and not base_only.empty:
            emergence = trends.keyword_emergence(today_only, base_only, top_n=8)
    return _TrendsPayload(period_label, days, period_df, vol_df, emergence)


# ---------- Small helpers ----------


def _persona_emphasis(persona: Persona, dept: str) -> tuple[str, str]:
    """페르소나 부서면 강조 border + 🎯 뱃지."""
    is_mine = bool(persona.dept and dept == persona.dept)
    border = "border: 2px solid var(--accent);" if is_mine else ""
    badge = "🎯 " if is_mine else ""
    return border, badge


def _ordered_depts(roadmap: pd.DataFrame, persona: Persona) -> list[str]:
    depts = sorted(roadmap["dept"].dropna().astype(str).unique().tolist())
    if persona.dept and persona.dept in depts:
        depts = [persona.dept] + [d for d in depts if d != persona.dept]
    return depts


def _insight_flow_html(*, news_ready: bool, roadmap_ready: bool, has_opportunities: bool) -> str:
    """Phase 5 분석 흐름 가이드: 트렌드 → 로드맵 연결 → 기회 선별 → SOLA 제안."""
    return step_guide([
        step_item(1, "트렌드 확인", "기간별 기사량·새 키워드로 변화 신호를 확인", active=news_ready),
        step_item(2, "로드맵 연결", "부서·공정 계층 필터로 관련 작업 범위를 좁힘", active=roadmap_ready),
        step_item(3, "기회 선별", "부서×공정 매트릭스에서 점수 높은 셀을 검토", active=has_opportunities),
        step_item(4, "SOLA 제안", "선택한 기회를 제안서 초안 생성 흐름으로 전달", active=has_opportunities),
    ])


def _opportunity_to_sola_state(row: pd.Series | dict) -> dict[str, str]:
    """Build session-state updates that route one opportunity cell to SOLA propose mode."""
    dept = str(row.get("dept", ""))
    lv3 = str(row.get("lv3", ""))
    return {
        "app_area": "🤖 SOLA 작업실",
        "sola_mode": "자동화 과제 제안서",
        "prop_dept": dept,
        "prop_lv3": lv3,
        "board_dept": dept,
        "board_lv3": lv3,
    }


def _apply_opportunity_to_sola(row: pd.Series | dict) -> None:
    st.session_state.update(_opportunity_to_sola_state(row))


def _opportunity_flow_context(cells: pd.DataFrame) -> str:
    if cells.empty:
        return "자동화 기회 후보: 없음"
    lines = ["자동화 기회 후보(실행 전환 대상):"]
    for _, row in cells.head(5).iterrows():
        lines.append(
            f"- {row['dept']} / {row['lv3']} score={row['cell_score']:.1f}; "
            f"tasks={row['sample_tasks']}; news={row['sample_news']}"
        )
    return "\n".join(lines)


# ---------- Card HTML ----------


def _dept_insight_card_html(dept: str, text: str, *, border: str, badge: str) -> str:
    return (
        f'<div class="news-card" style="min-height:auto; {border}">'
        f'<div class="card-meta">'
        f'<span class="card-press">{badge}{html.escape(dept)}</span>'
        f'</div>'
        f'<div class="card-body" style="-webkit-line-clamp: 6;">{html.escape(text)}</div>'
        f'</div>'
    )


def _opportunity_card_html(
    row: pd.Series, *, border: str, badge: str, comment_html: str
) -> str:
    return (
        f'<div class="news-card" style="min-height:auto; {border}">'
        f'<div class="card-meta">'
        f'<span class="card-press">{badge}{html.escape(str(row["dept"]))}</span>'
        f'<span class="card-date">{html.escape(str(row["lv3"]))}</span>'
        f'<span class="card-num">score {row["cell_score"]:.1f}</span>'
        f'</div>'
        f'<div class="card-title" style="font-size:0.9rem;">'
        f'{html.escape(str(row["sample_tasks"]))}'
        f'</div>'
        f'{comment_html}'
        f'<div class="card-body" style="-webkit-line-clamp:3;">'
        f'관련 뉴스: {html.escape(str(row["sample_news"]))}'
        f'</div>'
        f'</div>'
    )


def _match_card_html(row: pd.Series) -> str:
    return (
        f'<div class="news-card" style="min-height:auto;">'
        f'<div class="card-meta">'
        f'<span class="card-press">{html.escape(str(row["dept"]))}</span>'
        f'<span class="card-date">'
        f'{html.escape(str(row["lv3"]))} · {html.escape(str(row["task"]))}'
        f'</span>'
        f'<span class="card-num">score {row["score"]:.1f}</span>'
        f'</div>'
        f'<div class="card-title">{html.escape(str(row["news_title"]))}</div>'
        f'<div class="card-link">'
        f'<a href="{html.escape(str(row["link"]))}" target="_blank">원문 보기 →</a>'
        f'</div>'
        f'</div>'
    )


# ---------- Trend sub-renderers ----------


def _render_trend_brief(payload: _TrendsPayload) -> None:
    brief_cache_key = f"_brief_text_{payload.period_label}"
    cached_brief = st.session_state.get(brief_cache_key, "")
    bc1, bc2 = st.columns([5, 1])
    with bc1:
        render_html(
            f'<div class="card" style="margin-bottom:0.6rem;">'
            f'<div class="card-meta"><span class="card-press">🧠 SOLA 한 줄</span>'
            f'<span class="card-date">{html.escape(payload.period_label)}</span></div>'
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
            disabled=payload.period_df.empty,
        ):
            st.session_state["_do_board_brief"] = True

    if st.session_state.pop("_do_board_brief", False):
        with st.spinner("LLM 호출 중…"):
            st.session_state[brief_cache_key] = trend_brief.brief(
                period_label=payload.period_label,
                vol_df=payload.vol_df,
                emergence=payload.emergence,
            )
        st.rerun()


def _render_trend_charts(payload: _TrendsPayload) -> None:
    col1, col2 = st.columns([2, 1])
    with col1:
        if payload.vol_df["count"].sum() == 0:
            st.caption("(데이터 없음)")
        elif payload.days == 1:
            st.bar_chart(payload.vol_df.set_index("date"))
        else:
            st.line_chart(payload.vol_df.set_index("date"))
    with col2:
        st.caption("소스별 분포")
        src_df = trends.by_source(payload.period_df)
        if src_df.empty:
            st.caption("(데이터 없음)")
        else:
            st.dataframe(src_df, use_container_width=True, hide_index=True)


def _render_emergence(emergence: dict[str, pd.DataFrame]) -> None:
    if emergence["new"].empty and emergence["rising"].empty and emergence["gone"].empty:
        return
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


def _render_trends(payload: _TrendsPayload) -> None:
    """다중 일자 트렌드. 라디오로 기간 선택, 차트 + 키워드 emergence + LLM brief."""
    st.radio(
        "기간",
        list(_PERIOD_OPTIONS.keys()),
        horizontal=True,
        key="board_period",
        label_visibility="collapsed",
    )
    _render_trend_brief(payload)
    st.caption(f"{payload.period_label} · 기사 {len(payload.period_df):,}건")
    _render_trend_charts(payload)
    if payload.days > 1:
        _render_emergence(payload.emergence)


# ---------- Dept insights ----------


def _render_dept_insights(news: pd.DataFrame, roadmap: pd.DataFrame) -> None:
    """부서별 한 줄 LLM 인사이트 — 자동 표시 (캐시 hit 시 즉시, miss 시 spinner).

    이전엔 'AI 인사이트 생성·갱신' 수동 버튼이 필요했지만 캐시 키가
    (dept, titles head(8), llm_model) 기준이라 같은 뉴스셋에 두 번째부터는
    LLM 비용이 0. 자동 표시로 전환하고 새로고침은 별도 버튼만 남긴다.
    """
    if not llm_ready():
        render_html(
            status_card(
                "LLM 미설정 — 부서 인사이트는 LLM 응답을 사용합니다",
                "다음 → 환경변수에 LLM 키를 설정하면 이 자리에 부서별 한 줄 해석이 자동으로 표시됩니다.",
                status="warn",
                icon="🤖",
            ),
            unsafe_allow_html=True,
        )
        return

    refresh_col, caption_col = st.columns([1, 4])
    with refresh_col:
        refresh = st.button(
            "🔄 다시 생성", key="board_insight_refresh",
            help="현재 부서별 인사이트를 LLM 캐시 무시하고 다시 요청합니다.",
            use_container_width=True,
        )
    with caption_col:
        st.caption(
            "처음 진입한 부서만 LLM 을 호출하고 이후엔 캐시에서 즉시 응답합니다. "
            "새 뉴스가 들어오면 자동으로 새 결과가 나옵니다."
        )

    persona: Persona = st.session_state.get("persona") or Persona()
    cols = st.columns(2)
    for i, dept in enumerate(_ordered_depts(roadmap, persona)):
        with cols[i % 2]:
            border, badge = _persona_emphasis(persona, dept)
            with st.spinner(f"'{dept}' 인사이트 생성 중…"):
                text = insight_for_dept(dept, news, force=refresh)
            render_html(
                _dept_insight_card_html(dept, text, border=border, badge=badge),
                unsafe_allow_html=True,
            )


# ---------- Opportunity ----------


def _render_opportunity_cards(
    cells: pd.DataFrame, persona: Persona, use_llm_comment: bool
) -> None:
    existing_ids = {b.id for b in bookmarks.list_all(type_="opportunity")}
    cols = st.columns(2)
    for i, (_, row) in enumerate(cells.iterrows()):
        bm_id = bookmarks.make_id("opportunity", str(row["dept"]), str(row["lv3"]))
        with cols[i % 2]:
            border, badge = _persona_emphasis(persona, str(row["dept"]))
            comment_html = ""
            if use_llm_comment:
                c = opportunity.llm_commentary(
                    str(row["dept"]), str(row["lv3"]),
                    str(row["sample_news"]), str(row["sample_tasks"]),
                )
                if c:
                    comment_html = (
                        f'<div class="card-body" style="-webkit-line-clamp:5;">'
                        f'{html.escape(c)}</div>'
                    )

            render_html(
                _opportunity_card_html(
                    row, border=border, badge=badge, comment_html=comment_html,
                ),
                unsafe_allow_html=True,
            )

            is_book = bm_id in existing_ids
            btn_label = "★ 북마크됨" if is_book else "☆ 북마크"
            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if st.button(
                    btn_label, key=f"opp_bm_{bm_id}",
                    disabled=is_book, use_container_width=True,
                ):
                    bookmarks.add(Bookmark(
                        id=bm_id,
                        type="opportunity",
                        title=f"{row['dept']} · {row['lv3']}",
                        content=f"작업: {row['sample_tasks']}\n뉴스: {row['sample_news']}",
                        tags=[str(row["dept"]), str(row["lv3"])],
                    ))
                    st.session_state["board_msg"] = (
                        "ok", f"북마크 저장: {row['dept']} · {row['lv3']}",
                    )
                    st.rerun()
            with bcol2:
                if st.button(
                    "💬 SOLA 제안", key=f"opp_sola_{bm_id}",
                    use_container_width=True,
                ):
                    _apply_opportunity_to_sola(row)
                    st.rerun()


def _render_opportunity(
    news: pd.DataFrame, roadmap: pd.DataFrame, cells: pd.DataFrame | None = None,
) -> None:
    st.caption(
        "각 카드의 score = (그 부서·공정 셀에 누적된 뉴스↔작업 매칭 점수의 합). "
        "값이 클수록 해당 공정에서 다뤄지는 뉴스 양·관련성이 높아 자동화 도입 여지가 크다는 신호입니다."
    )

    if cells is None:
        cells = opportunity.score_cells(news, roadmap, cell_level="lv3", top_k_per_task=5)
    if cells.empty:
        render_html(
            status_card(
                "자동화 기회를 계산할 매칭 뉴스가 없습니다",
                "다음 → 🧱 데이터 관리 → 키워드 수집 → (필요 시) ✨ Enrich. 뉴스가 들어오면 이 자리에 부서·공정별 기회 카드가 나타납니다.",
                status="warn",
                icon="⚙️",
            ),
            unsafe_allow_html=True,
        )
        return

    top_n = st.slider(
        "상위 셀 개수", 3, 20, 8, key="board_opp_n",
        help="점수가 높은 부서·공정 셀을 몇 개까지 카드로 보여줄지.",
    )
    use_llm_comment = st.checkbox(
        "셀별 LLM 코멘트 사용 (캐시됨)", value=False, disabled=not llm_ready(),
        help="각 카드 아래에 LLM이 한 줄 해석을 붙여줍니다. LLM 미설정 시 룰 기반 표만 표시.",
        key="board_opp_llm",
    )

    head = cells.head(top_n).copy()
    with st.expander("매트릭스 표 보기", expanded=False):
        st.dataframe(head, use_container_width=True, hide_index=True)

    persona: Persona = st.session_state.get("persona") or Persona()
    _render_opportunity_cards(head, persona, use_llm_comment)

    msg = st.session_state.pop("board_msg", None)
    if msg:
        kind, text = msg
        {"ok": st.success, "warn": st.warning, "error": st.error}[kind](text)


# ---------- Matches ----------


def _render_matches(news: pd.DataFrame, roadmap: pd.DataFrame) -> None:
    from ui import task_tree

    persona: Persona = st.session_state.get("persona") or Persona()
    if persona.dept and "board_dept" not in st.session_state:
        st.session_state["board_dept"] = persona.dept

    _selection, filtered = task_tree.render_drilldown(roadmap, key_prefix="board")
    if filtered.empty:
        render_html(
            status_card(
                "선택한 필터에 해당하는 작업이 없습니다",
                "다음 → 위 부서·공정 드롭다운을 더 넓게 선택하거나, 🧱 데이터 관리 → 로드맵 업로드 탭에서 작업 정의가 들어있는지 확인하세요.",
                status="warn",
                icon="🧭",
            ),
            unsafe_allow_html=True,
        )
        return

    matches = score_matches(news, filtered, top_k=3)
    if matches.empty:
        render_html(
            status_card(
                "선택한 작업과 매칭되는 뉴스가 없습니다",
                "다음 → 🧱 데이터 관리 → 키워드를 추가/변경해 수집하거나, 위 필터를 다른 부서·공정으로 바꿔보세요.",
                status="warn",
                icon="📰",
            ),
            unsafe_allow_html=True,
        )
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
        render_html(_match_card_html(row), unsafe_allow_html=True)


# ---------- Page context (chat) ----------


def _build_page_context(
    news: pd.DataFrame,
    roadmap: pd.DataFrame,
    persona: Persona,
    *,
    payload: _TrendsPayload | None = None,
    cells: pd.DataFrame | None = None,
) -> str:
    """인사이트보드 화면의 핵심 데이터를 LLM 컨텍스트로 압축.

    `payload`, `cells` 가 주어지면 재계산 없이 그대로 사용한다.
    """
    lines: list[str] = ["화면: 인사이트보드 (트렌드 · 자동화 기회 매트릭스 · 부서 인사이트 · 매칭)"]
    if persona.is_set():
        lines.append(f"사용자 부서: {persona.dept or '-'} / 직무: {persona.job or '-'}")
    if news.empty or roadmap.empty:
        return "\n".join(lines)

    if payload is None:
        payload = _compute_trends_payload(news)
    lines.append(f"선택 기간: {payload.period_label} ({payload.days}일)")

    if not payload.vol_df.empty:
        lines.append("일자별 기사 수: " + ", ".join(
            f"{r['date']}={r['count']}" for _, r in payload.vol_df.iterrows()
        ))
    by_src = trends.by_source(payload.period_df)
    if not by_src.empty:
        lines.append("소스 분포: " + ", ".join(
            f"{r['source']}={r['count']}" for r in by_src.head(5).to_dict(orient="records")
        ))

    if payload.days > 1:
        if not payload.emergence["new"].empty:
            lines.append("새 키워드(오늘만): " + ", ".join(
                f"{r['keyword']}={r['count']}"
                for _, r in payload.emergence["new"].head(5).iterrows()
            ))
        if not payload.emergence["rising"].empty:
            lines.append("상승 키워드(오늘↑base): " + ", ".join(
                f"{r['keyword']}(+{r['delta']})"
                for _, r in payload.emergence["rising"].head(5).iterrows()
            ))

    brief_text = st.session_state.get(f"_brief_text_{payload.period_label}", "")
    if brief_text:
        lines.append(f"SOLA 한 줄 해석: {brief_text}")

    if cells is None:
        try:
            cells = opportunity.score_cells(
                news, roadmap, cell_level="lv3", top_k_per_task=5,
            )
        except Exception:  # noqa: BLE001
            cells = pd.DataFrame()
    lines.append(_opportunity_flow_context(cells))

    return "\n".join(lines)


# ---------- Overview & entry ----------


def _render_overview(news: pd.DataFrame, roadmap: pd.DataFrame, cells: pd.DataFrame) -> None:
    """메트릭 그리드 + (데이터 충분 시) 분석 흐름 가이드. 데이터 부족 시 안내 카드."""
    dept_count = (
        roadmap["dept"].nunique()
        if not roadmap.empty and "dept" in roadmap.columns else 0
    )
    render_html(
        metric_grid([
            metric_card("로드맵 작업", f"{len(roadmap):,}건",
                        caption="분석 가능한 작업 정의", icon="🗂", tone="teal"),
            metric_card("오늘 뉴스", f"{len(news):,}건",
                        caption="매칭 후보 기사", icon="📰", tone="info"),
            metric_card("부서 수", f"{dept_count:,}",
                        caption="로드맵 내 부서 범위", icon="🏭",
                        tone="ok" if dept_count else "warn"),
        ]),
        unsafe_allow_html=True,
    )

    if roadmap.empty or news.empty:
        render_html(
            status_card(
                "인사이트 분석을 위한 데이터가 부족합니다",
                "다음 → 🧱 데이터 관리 (왼쪽 메뉴) → 1) 로드맵 업로드 2) 뉴스 수집. 두 가지가 준비되면 트렌드·기회·매칭 카드가 자동으로 채워집니다.",
                status="warn",
                icon="🧱",
            ),
            unsafe_allow_html=True,
        )
        return

    render_html("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
    section_label("분석 실행 흐름")
    render_html(
        _insight_flow_html(
            news_ready=not news.empty,
            roadmap_ready=not roadmap.empty,
            has_opportunities=not cells.empty,
        ),
        unsafe_allow_html=True,
    )


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    roadmap = load_roadmap()
    news = load_all_today()

    page_header(
        "인사이트보드",
        "트렌드 · 자동화 기회 · 부서별 AI 인사이트 · 매칭",
        chat_toggle_key="board",
    )

    # 한 번만 계산해서 메인 렌더와 page_context(채팅)에 공유한다.
    payload = _compute_trends_payload(news) if not news.empty else None
    if not news.empty and not roadmap.empty:
        cells = opportunity.score_cells(news, roadmap, cell_level="lv3", top_k_per_task=5)
    else:
        cells = pd.DataFrame()

    with main_and_chat(
        "board",
        page_context_fn=lambda: _build_page_context(
            news, roadmap, persona, payload=payload, cells=cells,
        ),
        persona=persona,
        hint="현재 보드(트렌드·매트릭스·부서 인사이트·매칭)를 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            _render_overview(news, roadmap, cells)

            if news.empty or roadmap.empty:
                return

            render_html("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
            assert payload is not None  # news 비어있지 않으므로 항상 생성됨

            tab_trend, tab_opp, tab_insight, tab_match = st.tabs([
                "📈 트렌드",
                "⚙️ 자동화 기회",
                "🤖 부서 인사이트",
                "🔗 계층 매칭",
            ])
            with tab_trend:
                _render_trends(payload)
            with tab_opp:
                _render_opportunity(news, roadmap, cells)
            with tab_insight:
                _render_dept_insights(news, roadmap)
            with tab_match:
                _render_matches(news, roadmap)
