"""SOLA 작업실: LLM 기반 산출물 생성 (요약 / 자동화 과제 제안서).

채팅은 우측 사이드 패널(`main_and_chat`)에서 수행 — 다른 탭과 동일한 채팅
UX 를 사용하며, 직전 작성 제안서 / 채택된 제안서가 자동으로 컨텍스트에 첨부된다.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from config import llm_backend, llm_base_url, llm_model
from persona.schema import Persona
from roadmap.query import load_latest as load_roadmap
from sola import propose, summarize
from sola.client import LLMNotConfigured, is_configured
from store import bookmarks
from store.match import score_matches
from store.news_db import load_all_today
from ui.components import render_html, action_card, action_grid, status_card
from ui.layout import main_and_chat
from ui.styles import page_header, section_label


def _workspace_cards_html(*, news_count: int, roadmap_count: int, proposal_count: int, ready: bool) -> str:
    """Render SOLA work-type cards that explain the output creation flow."""
    return action_grid([
        action_card(
            "📰",
            "뉴스 요약",
            f"오늘 기사 {news_count:,}건을 회의 공유용 요약으로 압축합니다.",
            tone="teal" if news_count else "",
        ),
        action_card(
            "📝",
            "자동화 과제 제안서",
            f"로드맵 작업 {roadmap_count:,}건과 관련 뉴스를 연결해 제안서 초안을 만듭니다.",
            tone="teal" if roadmap_count and news_count else "",
        ),
        action_card(
            "💬",
            "컨텍스트 채팅",
            "오늘 뉴스·로드맵·채택 제안서를 컨텍스트로 후속 질문을 이어갑니다.",
            tone="info" if ready else "",
        ),
        action_card(
            "📦",
            "산출물 보관함",
            f"저장된 제안서 {proposal_count:,}건의 채택·거절·다운로드 상태를 관리합니다.",
            tone="ok" if proposal_count else "",
        ),
    ])


def _workspace_readiness_html(*, ready: bool, news_count: int, roadmap_count: int) -> str:
    """Render a compact readiness message for SOLA output generation."""
    if ready and news_count and roadmap_count:
        return status_card(
            "SOLA 산출물 생성 준비 완료",
            "뉴스와 로드맵, LLM 설정이 준비되어 요약·제안서·채팅을 바로 실행할 수 있습니다.",
            status="ok",
            icon="🤖",
        )
    missing: list[str] = []
    if not news_count:
        missing.append("뉴스 수집")
    if not roadmap_count:
        missing.append("로드맵 업로드")
    if not ready:
        missing.append("LLM 설정")
    return status_card(
        "SOLA 실행 전 준비가 필요합니다",
        "다음 → 🧱 데이터 관리에서 " + " · ".join(missing) + "을(를) 완료하세요. 준비가 끝나면 이 자리에 '준비 완료' 안내가 표시됩니다.",
        status="warn",
        icon="🤖",
    )


def _status_panel() -> None:
    render_html(
        f"""
        <div class="card-flat" style="display:flex;flex-wrap:wrap;gap:18px;
                 font-size:0.84rem;color:var(--text-2);margin-bottom:0.6rem;">
          <div><b>backend</b> <code>{html.escape(llm_backend())}</code></div>
          <div><b>model</b> <code>{html.escape(llm_model() or '(미설정)')}</code></div>
          <div><b>base_url</b> <code>{html.escape((llm_base_url() or '(미설정)')[:48])}</code></div>
          <div><b>ready</b> {'✅' if is_configured() else '⚠️'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_summary() -> None:
    st.subheader("뉴스 요약")
    df = load_all_today()
    st.caption(f"오늘 수집 기사: {len(df):,}건")
    n = st.slider("요약에 사용할 기사 수", min_value=5, max_value=50, value=20, step=5, key="sola_sum_n")

    if st.button("요약 생성", type="primary", key="sola_sum_btn"):
        st.session_state["_do_summary"] = True

    if st.session_state.pop("_do_summary", False):
        if df.empty:
            st.warning("오늘 수집된 기사가 없습니다. [수집] 탭에서 먼저 검색하세요.")
        else:
            try:
                with st.spinner("LLM 호출 중…"):
                    st.session_state["sola_sum_result"] = summarize.summarize_news(df, max_items=n)
            except LLMNotConfigured as e:
                st.session_state["sola_sum_result"] = f"⚠️ LLM 미설정: {e}"
            except Exception as e:  # noqa: BLE001
                st.session_state["sola_sum_result"] = f"⚠️ 호출 실패: {e}"
        st.rerun()

    result = st.session_state.get("sola_sum_result")
    if result:
        st.markdown(result)
        col_dl, col_bm = st.columns([1, 1])
        with col_dl:
            st.download_button(
                "요약 마크다운 다운로드",
                data=result.encode("utf-8"),
                file_name="sola_news_summary.md",
                mime="text/markdown",
            )
        with col_bm:
            bm_id = bookmarks.make_id("proposal", "summary", result[:80])
            is_book = bookmarks.has(bm_id)
            if st.button("★ 보관됨" if is_book else "☆ 요약 보관", disabled=is_book, key="sola_sum_bm_btn"):
                bookmarks.add(bookmarks.Bookmark(
                    id=bm_id,
                    type="proposal",
                    title="SOLA 뉴스 요약",
                    content=result,
                    tags=["뉴스 요약", "SOLA"],
                ))
                st.success("산출물 보관함에 저장됨")
                st.rerun()


def _render_propose() -> None:
    st.subheader("자동화 과제 제안서")
    roadmap = load_roadmap()
    news = load_all_today()
    if roadmap.empty:
        st.info("로드맵 업로드를 먼저 진행하세요.")
        return
    if news.empty:
        st.info("뉴스 수집을 먼저 진행하세요.")
        return

    from ui import task_tree

    persona: Persona = st.session_state.get("persona") or Persona()
    # 페르소나가 있으면 부서를 기본 필터로 미리 적용
    if persona.dept and "prop_dept" not in st.session_state:
        st.session_state["prop_dept"] = persona.dept

    _selection, filtered = task_tree.render_drilldown(roadmap, key_prefix="prop", show_task_picker=False)

    if filtered.empty:
        st.info("필터 조건에 맞는 작업이 없습니다.")
        return

    task_labels = [
        f"{r['dept']} / {r['lv3']} / {r['task']} / {r['sub_task']}".strip(" /")
        for _, r in filtered.iterrows()
    ]
    idx = st.selectbox(
        "작업 선택",
        range(len(task_labels)),
        format_func=lambda i: task_labels[i],
        key="prop_task_idx",
    )

    task_row = filtered.iloc[idx].to_dict()
    matches = score_matches(news, filtered.iloc[[idx]], top_k=10)
    related = (
        news[news["link"].isin(matches["link"])] if not matches.empty else news.head(0)
    )

    st.caption(f"매칭된 관련 뉴스: {len(related)}건")

    if st.button("제안서 생성", type="primary", key="prop_btn"):
        st.session_state["_do_propose"] = True

    if st.session_state.pop("_do_propose", False):
        try:
            with st.spinner("LLM 호출 중…"):
                st.session_state["sola_prop_result"] = propose.propose_for_task(
                    task_row, related, persona=persona,
                )
        except LLMNotConfigured as e:
            st.session_state["sola_prop_result"] = f"⚠️ LLM 미설정: {e}"
        except Exception as e:  # noqa: BLE001
            st.session_state["sola_prop_result"] = f"⚠️ 호출 실패: {e}"
        st.rerun()

    result = st.session_state.get("sola_prop_result")
    if result:
        st.markdown("---")
        st.markdown(result)
        col_dl, col_bm = st.columns([1, 1])
        with col_dl:
            st.download_button(
                "마크다운 다운로드",
                data=result.encode("utf-8"),
                file_name=f"proposal_{task_row.get('task', 'task')}.md",
                mime="text/markdown",
            )
        with col_bm:
            from store import bookmarks
            from store.bookmarks import Bookmark

            bm_id = bookmarks.make_id(
                "proposal",
                str(task_row.get("dept", "")),
                str(task_row.get("task", "")),
                str(task_row.get("sub_task", "")),
            )
            is_book = bookmarks.has(bm_id)
            if st.button("★ 북마크됨" if is_book else "☆ 제안서 북마크", disabled=is_book, key="prop_bm_btn"):
                bookmarks.add(Bookmark(
                    id=bm_id,
                    type="proposal",
                    title=f"{task_row.get('dept', '')} · {task_row.get('task', '')}",
                    content=result,
                    tags=[str(task_row.get("dept", "")), str(task_row.get("lv3", ""))],
                ))
                st.success("북마크 저장됨")
                st.rerun()


def _build_page_context(
    news: pd.DataFrame, roadmap: pd.DataFrame, persona: Persona,
) -> str:
    """SOLA 작업실 화면을 사이드 채팅 패널 컨텍스트로 압축.

    직전 작성 제안서·채택된 제안서는 `render_chat_panel` 이 자동으로 첨부하므로
    여기서는 화면 상태(현재 모드, 데이터 카운트, 필터)만 요약한다.
    """
    lines = ["화면: SOLA 작업실 (요약·자동화 과제 제안서 생성)"]
    if persona.is_set():
        lines.append(f"사용자 부서: {persona.dept or '-'} / 직무: {persona.job or '-'}")
    mode = st.session_state.get("sola_mode", "뉴스 요약")
    lines.append(f"현재 모드: {mode}")
    lines.append(f"오늘 뉴스: {len(news):,}건 · 로드맵 작업: {len(roadmap):,}건")
    if mode == "자동화 과제 제안서":
        dept = st.session_state.get("prop_dept", "")
        lv3 = st.session_state.get("prop_lv3", "")
        if dept or lv3:
            lines.append(f"제안서 필터: 부서={dept or '-'} / 공정={lv3 or '-'}")
    if st.session_state.get("sola_sum_result"):
        lines.append("최근 산출물: 뉴스 요약(세션 보유)")
    if st.session_state.get("sola_prop_result"):
        lines.append("최근 산출물: 자동화 과제 제안서(세션 보유)")
    return "\n".join(lines)


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    news = load_all_today()
    roadmap = load_roadmap()

    page_header(
        "SOLA 작업실",
        "산출물 생성(요약·제안서) · 채팅은 우측 💬 패널",
        chat_toggle_key="sola",
    )

    with main_and_chat(
        "sola",
        page_context_fn=lambda: _build_page_context(news, roadmap, persona),
        persona=persona,
        hint="현재 화면 + 직전 작성 제안서 + 채택된 제안서가 자동으로 첨부됩니다.",
    ) as main:
        with main:
            _status_panel()
            proposal_count = len(bookmarks.list_all(type_="proposal"))
            section_label("작업 유형")
            render_html(
                _workspace_cards_html(
                    news_count=len(news),
                    roadmap_count=len(roadmap),
                    proposal_count=proposal_count,
                    ready=is_configured(),
                ),
                unsafe_allow_html=True,
            )
            render_html(
                _workspace_readiness_html(
                    ready=is_configured(),
                    news_count=len(news),
                    roadmap_count=len(roadmap),
                ),
                unsafe_allow_html=True,
            )

            mode = st.radio(
                "작업 유형 선택",
                ("뉴스 요약", "자동화 과제 제안서"),
                horizontal=True,
                key="sola_mode",
                label_visibility="collapsed",
            )

            if mode == "뉴스 요약":
                _render_summary()
            elif mode == "자동화 과제 제안서":
                _render_propose()
