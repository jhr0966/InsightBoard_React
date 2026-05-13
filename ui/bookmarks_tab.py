"""북마크 탭: 자동화 기회·뉴스·제안서 즐겨찾기 관리 + 의사결정 상태."""
from __future__ import annotations

import html

import streamlit as st

from store import bookmarks
from store.bookmarks import BOOKMARK_STATUSES, DEFAULT_EXPIRE_DAYS
from ui.styles import page_header


_TYPE_LABEL = {
    "all": "전체",
    "opportunity": "자동화 기회",
    "proposal": "제안서",
    "news": "뉴스",
    "task": "작업",
}

_STATUS_LABEL = {
    "pending": "⏳ 검토 중",
    "adopted": "✅ 채택",
    "rejected": "✖ 거절",
}


def _status_badge_html(status: str) -> str:
    color = {
        "pending": "#9A9690",
        "adopted": "#1A8C5B",
        "rejected": "#C44848",
    }.get(status, "#9A9690")
    label = _STATUS_LABEL.get(status, status)
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
        f'background:{color};color:#fff;font-size:0.72rem;font-weight:600;">'
        f'{html.escape(label)}</span>'
    )


def render() -> None:
    page_header("📌 북마크", "관심 자동화 기회·뉴스·제안서 모음")

    st.caption(
        f"ℹ 제안서는 작성 후 **{DEFAULT_EXPIRE_DAYS}일** 지나면 자동 삭제됩니다. "
        "**채택(adopted)** 상태로 변경하면 영구 보존됩니다. "
        "(만료 정리는 앱 진입 시 1회 자동 수행)"
    )

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
        status_html = _status_badge_html(bm.status) if bm.type == "proposal" else ""
        decision_meta = ""
        if bm.type == "proposal" and bm.decided_at:
            decision_meta = (
                f'<div style="font-size:0.72rem;color:#9A9690;margin-top:0.3rem;">'
                f'결정 시각: {html.escape(bm.decided_at)}'
                + (f' · 메모: {html.escape(bm.decision_note)}' if bm.decision_note else "")
                + '</div>'
            )
        st.markdown(
            f"""
            <div class="news-card" style="min-height:auto;">
                <div class="card-meta">
                    <span class="card-press">{html.escape(type_label)}</span>
                    {status_html}
                    <span class="card-date">{html.escape(bm.created_at)}</span>
                </div>
                <div class="card-title">{html.escape(bm.title)}</div>
                <div class="card-keywords">{tag_html}</div>
                <div class="card-body">{html.escape(bm.content)}</div>
                {decision_meta}
                {link_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if bm.type == "proposal":
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                st.selectbox(
                    "상태",
                    options=list(BOOKMARK_STATUSES),
                    index=list(BOOKMARK_STATUSES).index(bm.status),
                    format_func=lambda s: _STATUS_LABEL.get(s, s),
                    key=f"bm_status_{bm.id}",
                    label_visibility="collapsed",
                )
            with c2:
                st.text_input(
                    "결정 메모",
                    value=bm.decision_note,
                    key=f"bm_note_{bm.id}",
                    placeholder="결정 사유·후속 액션 (선택)",
                    label_visibility="collapsed",
                )
            with c3:
                if st.button("💾 상태 저장", key=f"bm_save_{bm.id}"):
                    st.session_state["_bm_save_target"] = bm.id

        if st.button("🗑️ 삭제", key=f"bm_del_{bm.id}"):
            st.session_state["_bm_delete"] = bm.id

    if (target := st.session_state.pop("_bm_save_target", None)):
        new_status = st.session_state.get(f"bm_status_{target}", "pending")
        new_note = st.session_state.get(f"bm_note_{target}", "")
        if bookmarks.set_status(target, new_status, note=new_note):
            st.success(f"상태를 '{_STATUS_LABEL.get(new_status, new_status)}'로 저장했습니다.")
        st.rerun()

    if (target := st.session_state.pop("_bm_delete", None)):
        if bookmarks.remove(target):
            st.success("삭제되었습니다.")
        st.rerun()
