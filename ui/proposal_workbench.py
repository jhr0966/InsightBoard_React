"""제안서 작업장 — 2열 레이아웃 (좌: MD 뷰 / 우: SOLA 대화·수정).

사용자가 직전 생성 제안서 또는 북마크된 제안서를 골라 좌측 뷰로 띄우고,
우측 채팅 패널에서 두 가지 모드로 작업한다:

  💬 대화  — 활성 제안서를 시스템 컨텍스트로 잡고 일반 채팅 (수정 안 함)
  ✏️ 수정  — 사용자 지시 → 새 MD 로 좌측 패널 in-place 교체 (1단계 undo)

세션 키 (`pw_` prefix):
  pw_active_md     : 현재 활성 제안서 MD
  pw_active_title  : 활성 제안서 제목 (북마크 저장 시 기본 제목)
  pw_active_source : "session" | "bookmark:<id>" (식별용)
  pw_undo          : 이전 MD 1건 (1단계 undo)
  pw_chat          : [{role, content}] 작업장 전용 채팅 (sola_chat_history 와 분리)
  pw_mode          : "💬 대화" | "✏️ 수정"
"""
from __future__ import annotations

import streamlit as st

from persona import context as persona_ctx
from persona.schema import Persona
from sola import refine
from sola.client import LLMNotConfigured, chat
from sola.prompts import SYSTEM_CHAT
from store.bookmarks import BOOKMARK_STATUSES


_STATUS_LABEL = {
    "pending": "⏳ 검토 중",
    "adopted": "✅ 채택",
    "rejected": "✖ 거절",
}


def _options() -> list[tuple[str, str, str]]:
    """selectbox 옵션 목록: [(key, label, source)].

    source = "session" | "bookmark:<id>"
    """
    out: list[tuple[str, str, str]] = []
    session_prop = st.session_state.get("sola_prop_result")
    if session_prop:
        out.append(("session", "🟢 직전 작성 제안서", "session"))

    from store import bookmarks

    for bm in bookmarks.list_all(type_="proposal"):
        label = f"📌 {bm.title[:60]} · {bm.created_at[:10]}"
        out.append((f"bm:{bm.id}", label, f"bookmark:{bm.id}"))
    return out


def _load_selected(source: str) -> tuple[str, str] | None:
    """source 에서 (제목, MD) 추출. 없으면 None."""
    if source == "session":
        md = st.session_state.get("sola_prop_result")
        if not md:
            return None
        return ("직전 작성 제안서", md)
    if source.startswith("bookmark:"):
        bm_id = source.split(":", 1)[1]
        from store import bookmarks

        for it in bookmarks.list_all(type_="proposal"):
            if it.id == bm_id:
                return (it.title or "북마크된 제안서", it.content)
    return None


def _active_bm_id() -> str:
    """활성 제안서가 북마크 출처면 그 id, 아니면 빈 문자열."""
    src = st.session_state.get("pw_active_source", "")
    if src.startswith("bookmark:"):
        return src.split(":", 1)[1]
    return ""


def _do_refine(instruction: str, persona: Persona) -> None:
    current = st.session_state.get("pw_active_md", "")
    if not current:
        return
    try:
        with st.spinner("LLM 호출 중…"):
            new_md = refine.refine_proposal(current, instruction, persona=persona)
    except LLMNotConfigured as e:
        st.session_state["pw_chat"].append({"role": "assistant", "content": f"⚠️ LLM 미설정: {e}"})
        return
    except Exception as e:  # noqa: BLE001
        st.session_state["pw_chat"].append({"role": "assistant", "content": f"⚠️ 호출 실패: {e}"})
        return

    # 1단계 undo 백업 + 활성 교체
    st.session_state["pw_undo"] = current
    st.session_state["pw_active_md"] = new_md.strip()
    st.session_state["pw_chat"].append(
        {"role": "assistant", "content": "✏️ 제안서를 수정해 좌측 패널을 갱신했습니다. 마음에 들지 않으면 **↶ 되돌리기** 를 눌러주세요."}
    )


def _do_discuss(question: str, persona: Persona) -> None:
    current = st.session_state.get("pw_active_md", "")
    persona_block = persona_ctx.system_block(persona)
    ctx = f"\n\n--- 참고 제안서 ---\n{current.strip()}\n--- /참고 제안서 ---\n" if current else ""

    # 이전 사이클에서 채택된 제안서를 자동 컨텍스트로 첨부 (제목·메모만).
    from store import bookmarks as _bm

    adopted = [b for b in _bm.list_adopted_proposals(limit=5) if b.id != _active_bm_id()]
    if adopted:
        lines = ["\n--- 이전 사이클에서 채택된 제안서 ---"]
        for b in adopted:
            head = f"- {b.title}"
            if b.decided_at:
                head += f" (채택: {b.decided_at[:10]})"
            lines.append(head)
            if b.decision_note:
                lines.append(f"    메모: {b.decision_note}")
        lines.append("--- /채택된 제안서 ---\n")
        ctx += "\n".join(lines)

    history = st.session_state["pw_chat"]
    messages = [{"role": "system", "content": SYSTEM_CHAT + persona_block + ctx}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in history if m["role"] in ("user", "assistant"))
    try:
        with st.spinner("LLM 호출 중…"):
            reply = chat(messages=messages, temperature=0.3)
    except LLMNotConfigured as e:
        reply = f"⚠️ LLM 미설정: {e}"
    except Exception as e:  # noqa: BLE001
        reply = f"⚠️ 호출 실패: {e}"
    history.append({"role": "assistant", "content": reply})


def render() -> None:
    st.subheader("📝 제안서 작업장")
    st.caption(
        "직전에 만든 제안서 또는 북마크된 제안서를 골라 좌측에 띄우고, "
        "우측에서 LLM 과 대화하거나 지시로 직접 수정하세요."
    )

    # 세션 초기화
    st.session_state.setdefault("pw_active_md", "")
    st.session_state.setdefault("pw_active_title", "")
    st.session_state.setdefault("pw_active_source", "")
    st.session_state.setdefault("pw_chat", [])
    st.session_state.setdefault("pw_mode", "💬 대화")

    options = _options()
    if not options:
        st.info(
            "표시할 제안서가 없습니다. **자동화 과제 제안서** 탭에서 먼저 1건 생성하거나, "
            "기존 제안서를 ★북마크 해주세요."
        )
        return

    keys = [k for k, _, _ in options]
    labels_map = {k: lbl for k, lbl, _ in options}
    source_map = {k: src for k, _, src in options}

    sel = st.selectbox(
        "제안서 선택",
        options=keys,
        format_func=lambda k: labels_map[k],
        key="pw_select",
    )

    # 선택이 바뀐 경우 활성 MD 로드 + 채팅·undo 초기화
    if source_map[sel] != st.session_state["pw_active_source"]:
        loaded = _load_selected(source_map[sel])
        if loaded is not None:
            title, md = loaded
            st.session_state["pw_active_title"] = title
            st.session_state["pw_active_md"] = md.strip()
            st.session_state["pw_active_source"] = source_map[sel]
            st.session_state["pw_chat"] = []
            st.session_state.pop("pw_undo", None)

    persona: Persona = st.session_state.get("persona") or Persona()

    col_doc, col_chat = st.columns([3, 2], gap="large")

    # ── 좌측: 제안서 뷰 ──────────────────────────────────────────
    with col_doc:
        title_cols = st.columns([3, 2])
        with title_cols[0]:
            st.markdown(f"##### 📄 {st.session_state['pw_active_title']}")
        # 활성 제안서가 북마크 출처면 상태 셀렉터 + 즉시 저장.
        active_source = st.session_state["pw_active_source"]
        if active_source.startswith("bookmark:"):
            from store import bookmarks

            bm_id = active_source.split(":", 1)[1]
            current_bm = next(
                (it for it in bookmarks.list_all(type_="proposal") if it.id == bm_id),
                None,
            )
            if current_bm is not None:
                with title_cols[1]:
                    new_status = st.selectbox(
                        "상태",
                        options=list(BOOKMARK_STATUSES),
                        index=list(BOOKMARK_STATUSES).index(current_bm.status),
                        format_func=lambda s: _STATUS_LABEL.get(s, s),
                        key=f"pw_status_sel_{bm_id}",
                        label_visibility="collapsed",
                    )
                if new_status != current_bm.status:
                    bookmarks.set_status(bm_id, new_status)
                    st.toast(f"상태를 '{_STATUS_LABEL.get(new_status, new_status)}'로 변경했습니다.")
                    st.rerun()
        with st.container(border=True):
            st.markdown(st.session_state["pw_active_md"] or "_(비어 있음)_")

        action_cols = st.columns([1, 1, 1])
        with action_cols[0]:
            undo_disabled = "pw_undo" not in st.session_state
            if st.button("↶ 되돌리기", disabled=undo_disabled, key="pw_undo_btn"):
                st.session_state["_do_pw_undo"] = True
        with action_cols[1]:
            if st.button("★ 북마크 저장", key="pw_save_btn"):
                st.session_state["_do_pw_save"] = True
        with action_cols[2]:
            st.download_button(
                "⬇️ MD 다운로드",
                data=st.session_state["pw_active_md"].encode("utf-8"),
                file_name=f"proposal_{st.session_state['pw_active_title'][:30]}.md",
                mime="text/markdown",
                key="pw_dl_btn",
                disabled=not st.session_state["pw_active_md"],
            )

    # ── 우측: SOLA 패널 ──────────────────────────────────────────
    with col_chat:
        st.radio(
            "모드",
            options=("💬 대화", "✏️ 수정"),
            horizontal=True,
            key="pw_mode",
            help="대화 모드는 활성 제안서를 컨텍스트로 일반 채팅. 수정 모드는 사용자 지시로 좌측 패널을 in-place 교체합니다.",
        )

        for msg in st.session_state["pw_chat"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        placeholder = (
            "예: 이 제안서에서 가장 큰 리스크는?"
            if st.session_state["pw_mode"].startswith("💬")
            else "예: 리스크 섹션을 더 자세히 써줘 / 더 짧게 요약 / 보수적 톤으로"
        )
        user_input = st.chat_input(placeholder)
        if user_input:
            st.session_state["pw_chat"].append({"role": "user", "content": user_input})
            st.session_state["_pw_pending_input"] = user_input
            st.rerun()

    # ── pending 처리 (최상단 패턴 유지) ──────────────────────────
    if st.session_state.pop("_do_pw_undo", False):
        prev = st.session_state.pop("pw_undo", None)
        if prev is not None:
            st.session_state["pw_active_md"] = prev
            st.session_state["pw_chat"].append(
                {"role": "assistant", "content": "↶ 이전 버전으로 되돌렸습니다."}
            )
        st.rerun()

    if st.session_state.pop("_do_pw_save", False):
        from store import bookmarks
        from store.bookmarks import Bookmark

        md = st.session_state["pw_active_md"]
        title = st.session_state["pw_active_title"] or "제안서"
        bm_id = bookmarks.make_id("proposal-wb", title, md[:200])
        bookmarks.add(
            Bookmark(
                id=bm_id,
                type="proposal",
                title=f"{title} (작업장)",
                content=md,
                tags=["workbench"],
            )
        )
        st.success("작업장 현재 버전을 북마크에 저장했습니다.")
        st.rerun()

    pending = st.session_state.pop("_pw_pending_input", None)
    if pending:
        if st.session_state["pw_mode"].startswith("✏️"):
            _do_refine(pending, persona)
        else:
            _do_discuss(pending, persona)
        st.rerun()
