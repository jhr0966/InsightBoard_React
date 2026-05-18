"""북마크 탭: 자동화 기회·뉴스·제안서 즐겨찾기 관리 + 의사결정 상태."""
from __future__ import annotations

import html

import streamlit as st

from persona.schema import Persona
from store import bookmarks
from store.bookmarks import BOOKMARK_STATUSES, DEFAULT_EXPIRE_DAYS
from ui.components import metric_card, metric_grid, status_card
from ui.layout import main_and_chat
from ui.styles import page_header, section_label


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
    cls = {"pending": "pending", "adopted": "adopted", "rejected": "rejected"}.get(status, "pending")
    label = _STATUS_LABEL.get(status, status)
    return f'<span class="status-badge {cls}">{html.escape(label)}</span>'


def _build_page_context(items) -> str:
    lines = ["화면: 북마크 (자동화 기회·제안서·뉴스·작업 모음 + 의사결정 상태)"]
    if not items:
        lines.append("(비어 있음)")
        return "\n".join(lines)
    lines.append(f"표시 중인 북마크: {len(items)}건")
    by_type: dict[str, list] = {}
    for it in items:
        by_type.setdefault(it.type, []).append(it)
    for typ, group in by_type.items():
        lines.append(f"\n[{_TYPE_LABEL.get(typ, typ)}] {len(group)}건")
        for bm in group[:5]:
            extra = f" ({_STATUS_LABEL.get(bm.status, bm.status)})" if bm.type == "proposal" else ""
            lines.append(f"- {bm.title}{extra}")
            if bm.decision_note:
                lines.append(f"    메모: {bm.decision_note}")
    return "\n".join(lines)


def _archive_metrics_html(items) -> str:
    """Render output archive metrics for all filtered items."""
    counts = bookmarks.summary_counts(items)
    by_type = counts["by_type"]
    by_status = counts["proposal_status"]
    return metric_grid([
        metric_card("전체 산출물", f"{counts['total']:,}건", caption="현재 필터 기준", icon="📦", tone="info"),
        metric_card("제안서", f"{by_type.get('proposal', 0):,}건", caption="저장된 SOLA 결과", icon="📝", tone="teal"),
        metric_card("채택 과제", f"{by_status.get('adopted', 0):,}건", caption="영구 보존 결정", icon="✅", tone="ok"),
        metric_card("검토 중", f"{by_status.get('pending', 0):,}건", caption="후속 결정 필요", icon="⏳", tone="warn" if by_status.get('pending', 0) else "info"),
    ])


def render() -> None:
    persona: Persona = st.session_state.get("persona") or Persona()
    page_header(
        "📌 북마크",
        "관심 자동화 기회·뉴스·제안서 모음",
        chat_toggle_key="bookmarks",
    )

    type_keys = list(_TYPE_LABEL.keys())
    chosen = st.session_state.get("bm_type", "all")
    items_for_ctx = bookmarks.list_all(type_=None if chosen == "all" else chosen)

    with main_and_chat(
        "bookmarks",
        page_context_fn=lambda: _build_page_context(items_for_ctx),
        persona=persona,
        hint="현재 필터링된 북마크 목록을 컨텍스트로 대화합니다.",
    ) as main:
        with main:
            st.caption(
                f"ℹ 제안서는 작성 후 **{DEFAULT_EXPIRE_DAYS}일** 지나면 자동 삭제됩니다. "
                "**채택(adopted)** 상태로 변경하면 영구 보존됩니다. "
                "(만료 정리는 앱 진입 시 1회 자동 수행)"
            )

            chosen = st.radio(
                "타입", type_keys,
                format_func=lambda k: _TYPE_LABEL[k],
                horizontal=True,
                key="bm_type",
            )
            items = bookmarks.list_all(type_=None if chosen == "all" else chosen)
            st.caption(f"{len(items)}건")
            st.markdown(_archive_metrics_html(items), unsafe_allow_html=True)

            if not items:
                st.markdown(
                    status_card(
                        "아직 저장된 산출물이 없습니다",
                        "인사이트 분석의 ☆ 또는 SOLA 작업실의 제안서 저장 버튼으로 검토할 항목을 보관하세요.",
                        status="teal",
                        icon="📌",
                    ),
                    unsafe_allow_html=True,
                )
                return

            _render_items(items)


def _workbench_state_for_bookmark(bm_id: str) -> dict[str, str]:
    """Return session-state updates that open a proposal bookmark in the workbench."""
    return {
        "app_area": "🤖 SOLA 작업실",
        "pw_select": f"bm:{bm_id}",
        "pw_active_source": "",
        "pw_mode": "✏️ 수정",
    }


def _render_items(items) -> None:
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
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
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
            with c4:
                if st.button("✏️ 작업장", key=f"bm_workbench_{bm.id}"):
                    st.session_state.update(_workbench_state_for_bookmark(bm.id))
                    st.rerun()

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
