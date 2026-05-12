"""SOLA 탭: LLM 기반 요약 / 자동화 과제 제안서 / 채팅 (M2)."""
from __future__ import annotations

import html

import streamlit as st

from config import llm_backend, llm_base_url, llm_model
from roadmap.query import filter_hierarchy, load_latest as load_roadmap
from sola import chat_ctx, propose, summarize
from sola.client import LLMNotConfigured, chat, is_configured
from sola.prompts import SYSTEM_CHAT
from store import chat_log
from store.match import score_matches
from store.news_db import load_all_today
from ui.styles import page_header


def _status_panel() -> None:
    cols = st.columns(4)
    cols[0].markdown(f"**backend** `{llm_backend()}`")
    cols[1].markdown(f"**model** `{llm_model() or '(미설정)'}`")
    cols[2].markdown(f"**base_url** `{(llm_base_url() or '(미설정)')[:38]}`")
    cols[3].markdown(f"**ready** {'✅' if is_configured() else '❌'}")


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

    col1, col2, col3 = st.columns(3)
    with col1:
        dept_options = ["(전체)"] + sorted(roadmap["dept"].dropna().astype(str).unique().tolist())
        dept = st.selectbox("부서", dept_options, key="prop_dept")
    with col2:
        lv3_options = ["(전체)"] + sorted(roadmap["lv3"].dropna().astype(str).unique().tolist())
        lv3 = st.selectbox("공정(Lv3)", lv3_options, key="prop_lv3")
    with col3:
        filtered = filter_hierarchy(
            roadmap,
            dept=None if dept == "(전체)" else dept,
            lv3=None if lv3 == "(전체)" else lv3,
        )
        task_labels = [
            f"{r['dept']} / {r['lv3']} / {r['task']} / {r['sub_task']}".strip(" /")
            for _, r in filtered.iterrows()
        ]
        idx = st.selectbox(
            "작업 선택",
            range(len(task_labels)),
            format_func=lambda i: task_labels[i] if task_labels else "(없음)",
            key="prop_task_idx",
        ) if task_labels else None

    if idx is None or not task_labels:
        st.info("필터 조건에 맞는 작업이 없습니다.")
        return

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
                st.session_state["sola_prop_result"] = propose.propose_for_task(task_row, related)
        except LLMNotConfigured as e:
            st.session_state["sola_prop_result"] = f"⚠️ LLM 미설정: {e}"
        except Exception as e:  # noqa: BLE001
            st.session_state["sola_prop_result"] = f"⚠️ 호출 실패: {e}"
        st.rerun()

    result = st.session_state.get("sola_prop_result")
    if result:
        st.markdown("---")
        st.markdown(result)
        st.download_button(
            "마크다운 다운로드",
            data=result.encode("utf-8"),
            file_name=f"proposal_{task_row.get('task', 'task')}.md",
            mime="text/markdown",
        )


def _render_chat() -> None:
    st.subheader("LLM 채팅")
    st.caption("오늘 뉴스와 로드맵이 컨텍스트로 자동 첨부됩니다. 대화는 `data/sola/chat_history.jsonl`에 저장돼 새로고침 후에도 복원됩니다.")

    if "sola_chat_history" not in st.session_state:
        st.session_state["sola_chat_history"] = chat_log.load_history()
    history: list[dict] = st.session_state["sola_chat_history"]

    cols = st.columns([1, 4])
    with cols[0]:
        if st.button("대화 초기화", key="chat_reset_btn"):
            st.session_state["_do_chat_reset"] = True
    if st.session_state.pop("_do_chat_reset", False):
        st.session_state["sola_chat_history"] = []
        chat_log.reset()
        st.rerun()

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("질문을 입력하세요 (예: 오늘 뉴스 중 용접 자동화 관련만 요약해줘)")
    if user_input:
        history.append({"role": "user", "content": user_input})
        st.session_state["sola_chat_history"] = history
        chat_log.save_history(history)
        st.session_state["_pending_chat"] = True
        st.rerun()

    if st.session_state.pop("_pending_chat", False):
        try:
            ctx = chat_ctx.build_context_block(load_all_today(), load_roadmap())
            messages = [{"role": "system", "content": SYSTEM_CHAT + ctx}]
            messages.extend({"role": m["role"], "content": m["content"]} for m in history)
            with st.spinner("LLM 호출 중…"):
                reply = chat(messages=messages, temperature=0.3)
        except LLMNotConfigured as e:
            reply = f"⚠️ LLM 미설정: {e}"
        except Exception as e:  # noqa: BLE001
            reply = f"⚠️ 호출 실패: {e}"
        history.append({"role": "assistant", "content": reply})
        st.session_state["sola_chat_history"] = history
        chat_log.save_history(history)
        st.rerun()


def render() -> None:
    page_header("SOLA", "LLM 기반 요약 · 제안서 · 채팅")
    _status_panel()
    st.markdown("---")

    mode = st.radio(
        "기능",
        ("뉴스 요약", "자동화 과제 제안서", "채팅"),
        horizontal=True,
        key="sola_mode",
    )

    if mode == "뉴스 요약":
        _render_summary()
    elif mode == "자동화 과제 제안서":
        _render_propose()
    else:
        _render_chat()
