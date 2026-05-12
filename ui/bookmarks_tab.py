"""북마크 탭: 자동화 기회·뉴스·제안서 즐겨찾기 관리."""
from __future__ import annotations

import html

import streamlit as st

from store import bookmarks
from ui.styles import page_header


_TYPE_LABEL = {
    "all": "전체",
    "opportunity": "자동화 기회",
    "proposal": "제안서",
    "news": "뉴스",
    "task": "작업",
}


def render() -> None:
    page_header("📌 북마크", "관심 자동화 기회·뉴스·제안서 모음")

    type_keys = list(_TYPE_LABEL.keys())
    chosen = st.radio(
        "타입", type_keys,
        format_func=lambda k: _TYPE_LABEL[k],
        horizontal=True,
        key="bm_type",
    )
    items = bookmarks.list_all(type_=None if chosen == "all" else chosen)
    st.caption(f"{len(items)}건")

    if not items:
        st.info("아직 북마크가 없습니다. 인사이트보드의 ☆ 또는 제안서 화면의 ☆ 버튼으로 저장하세요.")
        return

    for bm in reversed(items):
        type_label = _TYPE_LABEL.get(bm.type, bm.type)
        tag_html = "".join(
            f'<span class="keyword-badge">{html.escape(t)}</span>' for t in (bm.tags or [])
        )
        link_html = (
            f'<div class="card-link"><a href="{html.escape(bm.link)}" target="_blank">원문 보기 →</a></div>'
            if bm.link else ""
        )
        st.markdown(
            f"""
            <div class="news-card" style="min-height:auto;">
                <div class="card-meta">
                    <span class="card-press">{html.escape(type_label)}</span>
                    <span class="card-date">{html.escape(bm.created_at)}</span>
                </div>
                <div class="card-title">{html.escape(bm.title)}</div>
                <div class="card-keywords">{tag_html}</div>
                <div class="card-body">{html.escape(bm.content)}</div>
                {link_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🗑️ 삭제", key=f"bm_del_{bm.id}"):
            st.session_state["_bm_delete"] = bm.id

    if (target := st.session_state.pop("_bm_delete", None)):
        if bookmarks.remove(target):
            st.success("삭제되었습니다.")
        st.rerun()
