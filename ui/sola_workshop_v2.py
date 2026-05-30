"""SOLA 작업실 — v2 디자인 적용.

특수성: SOLA workshop 화면은 우측 .app-sola 패널을 그리지 않는다. 대신 화면
자체가 3-열 `.ws-shell` (쓰레드 / 채팅 / 컨텍스트) 로 구성되어 SOLA 경험을
풀스크린으로 제공.

CSS 규칙은 `body:has(.ws-shell)` 분기로 block-container 우측 패딩을 축소
(scale.css 에 추가).
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone

import streamlit as st

from config import ASSETS_DIR
from persona import context as persona_ctx
from persona.schema import Persona
from sola import client as sola_client
from sola.preview import format_messages_preview
from store import bookmarks as bookmarks_store
from store import chat_log
from store import sola_threads
from ui import app_shell
from ui.styles import inject_screen_css


# 활성 thread id 의 session key — B.4 이후 chat_key 가 thread.id 로 분기됨.
_ACTIVE_THREAD_KEY = "_sola_thread_id"
# A.3 잔재 호환 — legacy 단일 thread id (chat_key="sola_main").
_LEGACY_THREAD_ID = sola_threads.LEGACY_MAIN_THREAD_ID

_SOLA_SYSTEM_PROMPT = (
    "당신은 SOLA, 조선소 작업 정의를 이해하는 AI 어시스턴트입니다. "
    "외부 기술 동향을 우리 작업에 어떻게 적용할지 번역하고, "
    "ROI · 일정 · 위험요인을 함께 설명합니다. "
    "답변은 한국어로, 사용자의 페르소나와 맥락을 반영해서 작성합니다."
)


_SOLA_TEMPLATE = ASSETS_DIR / "v2" / "screens" / "sola_main.html"


def _load_persona() -> Persona:
    p = st.session_state.get("persona")
    if isinstance(p, Persona):
        return p
    from persona import store as persona_store

    p = persona_store.load()
    st.session_state["persona"] = p
    return p


def _archive_stats() -> dict[str, int]:
    summary = bookmarks_store.summary_counts()
    pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
    return {"match_today": 32, "opportunities": 4, "pending_adopt": pending}


def render() -> None:
    """SOLA 작업실 v2 — topbar + app-side + 3-열 ws-shell (app-sola 없음)."""
    inject_screen_css("sola")

    persona = _load_persona()

    # ── pending 핸들러 (run 최상단, 위젯 인스턴스화 이전) ──
    # 순서: 스레드 전환·생성·삭제 → URL switch → prefill ask → send
    # (앞단 결과가 뒷단의 active_thread 를 바꿀 수 있어 이 순서 필수)
    _consume_thread_actions_if_any()
    _switch_thread_from_query_if_any()
    _consume_prefill_ask_if_any()
    _consume_send_if_any(persona)

    stats = _archive_stats()
    refresh = app_shell.refresh_label_now()

    app_shell.render_topbar(
        page_title="SOLA 작업실",
        eyebrow_current="SOLA 작업실",
        refresh_label=refresh,
        fresh_kind="accent",
    )
    app_shell.render_app_side(
        active_area="🤖 SOLA 작업실",
        persona=persona,
        stats=stats,
    )
    app_shell.render_setup_banner_if_needed()
    _render_brief_handoff_banner_if_needed()
    _render_main(persona)
    # 의도적으로 app-sola 미렌더 — ws-ctx 가 그 역할 대체


_HANDOFF_LABELS: dict[str, tuple[str, str]] = {
    "brief": ("📊 보드 브리핑에서 인계됨", "3건의 뉴스를 컨텍스트로 사용"),
    "opp": ("🎯 자동화 기회 카드에서 인계됨", "이 부서·공정으로 제안서 초안 시작"),
    "matrix": ("🧭 기회 매트릭스 1위에서 인계됨", "이 부서·공정으로 제안서 초안 시작"),
    "ia_map": ("🔎 인사이트 공정 매핑 카드에서 인계됨", "이 공정 상세 — 매칭 뉴스·작업 컨텍스트"),
    "edit": ("📦 산출물 보관함에서 인계됨", "기존 제안서를 이어서 수정"),
}


def _render_brief_handoff_banner_if_needed() -> None:
    """`?from=...` 에 따라 인계 컨텍스트 배너 렌더 (LLM 입력 wire 는 후속 PR).

    지원 from: brief / opp / matrix / ia_map.
      - brief : session_state["_board_brief_items"] 3건 제목 노출
      - opp / matrix / ia_map : URL query 의 dept · lv3 노출
    """
    from_kind = st.query_params.get("from")
    if from_kind not in _HANDOFF_LABELS:
        return

    title, sub = _HANDOFF_LABELS[from_kind]
    body_html = ""

    if from_kind == "brief":
        items = st.session_state.get("_board_brief_items") or []
        if not items:
            return
        body_html = "<ol>" + "".join(
            f'<li><span class="ws-brief-num">{i + 1}</span>{_html.escape(it.get("title", "")[:80])}</li>'
            for i, it in enumerate(items[:3])
        ) + "</ol>"
    elif from_kind == "edit":
        bm_title = st.query_params.get("title", "")
        if not bm_title:
            return
        body_html = (
            f'<div class="ws-brief-target">'
            f'<span class="ws-brief-target-eye">대상 제안서</span>'
            f'<span class="ws-brief-target-v">{_html.escape(bm_title[:80])}</span>'
            f'</div>'
        )
    else:
        dept = st.query_params.get("dept", "")
        lv3 = st.query_params.get("lv3", "")
        if not dept and not lv3:
            return
        target = " · ".join(p for p in (dept, lv3) if p) or "—"
        body_html = (
            f'<div class="ws-brief-target">'
            f'<span class="ws-brief-target-eye">대상</span>'
            f'<span class="ws-brief-target-v">{_html.escape(target)}</span>'
            f'</div>'
        )

    st.html(
        f"""
        <style>
          body:has(.db-topbar) .ws-brief-handoff {{
            position: sticky; z-index: 7;
            margin: 0 24px 14px; padding: 12px 16px;
            background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 10px;
            font-size: 13px; color: #1E3A8A;
          }}
          /* LLM banner 없을 때만 sticky top:76 — banner 가 sticky 면 stacking 아래로 */
          body:has(.db-topbar) .ws-brief-handoff {{
            top: 76px;
          }}
          body:has(.db-topbar):has(.app-llm-banner) .ws-brief-handoff {{
            top: 132px;
          }}
          body:has(.db-topbar) .ws-brief-handoff-h {{
            font-weight: 800; margin-bottom: 6px;
            display: flex; align-items: center; gap: 6px;
          }}
          body:has(.db-topbar) .ws-brief-handoff-sub {{
            font-weight: 500; color: #1E40AF; margin-left: 6px;
          }}
          body:has(.db-topbar) .ws-brief-handoff ol {{ margin: 0; padding-left: 0; list-style: none; }}
          body:has(.db-topbar) .ws-brief-handoff li {{
            padding: 3px 0; display: flex; gap: 8px; align-items: baseline;
          }}
          body:has(.db-topbar) .ws-brief-num {{
            display: inline-flex; align-items: center; justify-content: center;
            min-width: 18px; height: 18px; padding: 0 5px; border-radius: 4px;
            background: #2563EB; color: #fff; font-size: 11px; font-weight: 800;
          }}
          body:has(.db-topbar) .ws-brief-target {{
            display: flex; gap: 8px; align-items: center;
          }}
          body:has(.db-topbar) .ws-brief-target-eye {{
            font-size: 11px; color: #1E40AF; opacity: 0.7; letter-spacing: 0.04em;
          }}
          body:has(.db-topbar) .ws-brief-target-v {{ font-weight: 700; }}
        </style>
        <div class="ws-brief-handoff">
          <div class="ws-brief-handoff-h">
            {title}<span class="ws-brief-handoff-sub">— {sub}</span>
          </div>
          {body_html}
        </div>
        """
    )


def _composer_prefill() -> tuple[str, str, str]:
    """`?from=...` 기반 composer prefill 텍스트 + placeholder + pins HTML.

    Returns: (prefill, placeholder, pins_html).
    """
    from_kind = st.query_params.get("from")
    dept = st.query_params.get("dept", "")
    lv3 = st.query_params.get("lv3", "")
    target = " · ".join(p for p in (dept, lv3) if p)

    if from_kind == "brief":
        items = st.session_state.get("_board_brief_items") or []
        if items:
            titles = "\n".join(f"- {it.get('title', '')[:80]}" for it in items[:3])
            prefill = (
                f"오늘 보드의 다음 {len(items)}건 뉴스를 컨텍스트로,\n"
                f"{titles}\n\n"
                f"부서장에게 보낼 1쪽 제안서 초안을 만들어줘."
            )
            pins = (
                '<span class="ws-cmp-pin">📎 컨텍스트 첨부됨</span>'
                f'<span class="ws-cmp-pin-list">'
                f'<span class="ws-pin-mini">📊 보드 브리핑</span>'
                f'<span class="ws-pin-mini">뉴스 {len(items)}</span>'
                f'<span class="ws-pin-mini">페르소나</span>'
                f'</span>'
            )
            return prefill, "추가로 조정할 점이 있다면 알려주세요 — 일정·예산·KPI 등", pins

    if from_kind in ("opp", "matrix") and target:
        verb = "자동화 기회" if from_kind == "opp" else "매트릭스 1위"
        prefill = (
            f"{target} {verb}에 대한 제안서 초안을 만들어줘.\n"
            f"우리 페르소나 컨텍스트로 ROI · 일정 · 위험요인 포함."
        )
        pins = (
            '<span class="ws-cmp-pin">📎 컨텍스트 첨부됨</span>'
            f'<span class="ws-cmp-pin-list">'
            f'<span class="ws-pin-mini">{"🎯 자동화 기회" if from_kind == "opp" else "🧭 매트릭스"}</span>'
            f'<span class="ws-pin-mini">{_html.escape(target)[:30]}</span>'
            f'<span class="ws-pin-mini">페르소나</span>'
            f'</span>'
        )
        return prefill, "제안서 톤·길이·강조점을 추가로 조정할 수 있어요", pins

    if from_kind == "ia_map" and target:
        prefill = (
            f"{target} 공정의 현재 상황과 매칭된 뉴스 신호를 정리하고,\n"
            f"적용 가능한 자동화 옵션 3가지를 비교해줘."
        )
        pins = (
            '<span class="ws-cmp-pin">📎 컨텍스트 첨부됨</span>'
            f'<span class="ws-cmp-pin-list">'
            f'<span class="ws-pin-mini">🔎 공정 매핑</span>'
            f'<span class="ws-pin-mini">{_html.escape(target)[:30]}</span>'
            f'<span class="ws-pin-mini">페르소나</span>'
            f'</span>'
        )
        return prefill, "비교 기준(난이도·비용·기간)을 추가로 명시할 수 있어요", pins

    if from_kind == "edit":
        bm_title = st.query_params.get("title", "")
        if bm_title:
            prefill = (
                f"기존 제안서 '{bm_title[:80]}' 를 이어서 수정하려고 해.\n"
                f"현재 내용을 검토하고 개선할 점을 제안해줘."
            )
            pins = (
                '<span class="ws-cmp-pin">📎 컨텍스트 첨부됨</span>'
                '<span class="ws-cmp-pin-list">'
                '<span class="ws-pin-mini">📦 기존 제안서</span>'
                f'<span class="ws-pin-mini">{_html.escape(bm_title[:30])}</span>'
                '<span class="ws-pin-mini">페르소나</span>'
                '</span>'
            )
            return prefill, "수정 방향(톤·근거 보강·일정 등)을 구체적으로 적어주세요", pins

    # 기본 — 인계 없음
    pins = (
        '<span class="ws-cmp-pin">컨텍스트 미첨부</span>'
        '<span class="ws-cmp-pin-list">'
        '<span class="ws-pin-mini">페르소나만 적용</span>'
        '</span>'
    )
    return "", "무엇을 도와드릴까요? — 보드/인사이트 카드의 CTA 로 시작해도 됩니다", pins


# ── 채팅 메시지 영구화 + 렌더 ────────────────────────────────

def _active_thread() -> "sola_threads.Thread":
    """현재 활성 thread — 없으면 가장 최근, 그것도 없으면 새로 생성.

    A.3 잔재(`chat_key="sola_main"`) 가 있고 thread 가 아직 없으면 자동 마이그.
    """
    sola_threads.migrate_legacy_main_if_needed()
    active_id = st.session_state.get(_ACTIVE_THREAD_KEY)
    th = sola_threads.ensure_active(active_id)
    st.session_state[_ACTIVE_THREAD_KEY] = th.id
    return th


def _load_messages() -> list[dict]:
    """활성 thread 메시지 — 세션 캐시, 없으면 chat_log 에서 load."""
    th = _active_thread()
    cache_key = f"_sola_messages_{th.id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    try:
        msgs = chat_log.load_history(th.id)
    except Exception:
        msgs = []
    st.session_state[cache_key] = msgs
    return msgs


def _append_message(role: str, content: str) -> None:
    th = _active_thread()
    cache_key = f"_sola_messages_{th.id}"
    msgs = _load_messages()
    msgs.append({
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    st.session_state[cache_key] = msgs
    try:
        chat_log.save_history(msgs, th.id)
    except Exception:
        pass  # 영구화 실패해도 세션엔 남음

    # 첫 user 메시지로 thread 제목 자동 설정 (제목이 기본값이면)
    auto_title = None
    if role == "user" and (not th.title or th.title == "새 대화"):
        auto_title = sola_threads.title_from_first_user_message(content)
    sola_threads.update(
        th.id,
        title=auto_title,
        message_count=len(msgs),
        touch=True,
    )


def _build_llm_messages(persona: Persona, history: list[dict]) -> list[dict]:
    """sola_client.chat 에 전달할 OpenAI 포맷 messages — system + 화면 컨텍스트 + history.

    System 메시지 구성:
      1. SOLA 시스템 프롬프트
      2. 페르소나 블록 (이름/부서/직무/관심공정)
      3. **직전에 본 화면의 콘텐츠** — `_chat_context_for_sola` 에 각 area 의
         render() 가 저장한 텍스트 블록. 사용자가 "보고있는 화면의 어떤 것이든"
         질문해도 LLM 이 답할 수 있도록.
    """
    sys_parts = [_SOLA_SYSTEM_PROMPT, persona_ctx.system_block(persona)]
    screen_ctx = st.session_state.get("_chat_context_for_sola", "").strip()
    if screen_ctx:
        sys_parts.append(screen_ctx)
    sys_block = "\n\n".join(p for p in sys_parts if p).strip()
    out: list[dict] = [{"role": "system", "content": sys_block}]
    for m in history:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            out.append({"role": m["role"], "content": m["content"]})
    return out


def _msg_html(role: str, content: str, ts: str = "") -> str:
    """단일 메시지 → ws-msg HTML (시안 마크업 호환)."""
    safe = _html.escape(content).replace("\n", "<br>")
    try:
        from datetime import datetime as _dt
        time_label = _dt.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M") if ts else ""
    except Exception:
        time_label = ""
    if role == "user":
        return (
            '<div class="ws-msg ws-msg-user">'
            f'<div class="ws-bubble ws-bubble-user">{safe}</div>'
            '<div class="ws-msg-meta">'
            '<span class="ws-avatar ws-avatar-user">나</span>'
            f'<span>{_html.escape(time_label)}</span>'
            '</div></div>'
        )
    # assistant (SOLA)
    return (
        '<div class="ws-msg">'
        '<div class="ws-msg-from">'
        '<span class="ws-avatar ws-avatar-sola">🤖</span>'
        '<span class="ws-msg-from-name">SOLA</span>'
        '</div>'
        f'<div class="ws-bubble ws-bubble-sola"><p>{safe}</p></div>'
        '<div class="ws-msg-meta-bot">'
        f'<span>{_html.escape(time_label)}</span>'
        '</div></div>'
    )


def _render_messages_html(messages: list[dict]) -> str:
    if not messages:
        return (
            '<div class="ws-msg-empty" style="padding: 36px 12px; text-align: center; '
            'color: var(--text-muted); font-size: 14px; line-height: 1.6;">'
            '대화를 시작해보세요.<br>'
            '<span style="font-size: 12.5px;">아래 입력창에 질문을 적거나, 보드의 '
            "<b>SOLA와 검토</b> CTA 로 컨텍스트를 인계받으세요.</span>"
            '</div>'
        )
    return "\n".join(_msg_html(m["role"], m["content"], m.get("ts", "")) for m in messages)


# ── send 핸들러 (run 최상단) ─────────────────────────────────

def _consume_send_if_any(persona: Persona) -> None:
    """`_do_sola_send` pending → LLM 호출 → 메시지 추가 → rerun.

    오류는 assistant 메시지로 노출 (UX 단절 방지). LLM 미설정은
    `sola.preview` 미리보기로 폴백.
    """
    payload = st.session_state.pop("_do_sola_send", None)
    if not payload:
        return
    user_text = str(payload).strip()
    if not user_text:
        return

    _append_message("user", user_text)
    msgs = _load_messages()
    llm_messages = _build_llm_messages(persona, msgs)

    try:
        with st.spinner("SOLA 가 답변을 작성하고 있어요…"):
            answer = sola_client.chat(llm_messages)
        _append_message("assistant", answer)
    except sola_client.LLMNotConfigured:
        preview = format_messages_preview(
            llm_messages,
            header="ℹ️ LLM 미설정 — 아래는 실제로 전달될 입력 컨텍스트입니다.",
            footer_hint=True,
        )
        _append_message("assistant", preview)
    except Exception as exc:
        _append_message("assistant", f"⚠️ 응답 생성 실패: {type(exc).__name__}: {exc}")
    st.rerun()


def _consume_thread_actions_if_any() -> None:
    """Thread 관련 pending → 실행 후 rerun.

    flag:
      _do_new_thread        — 새 thread 생성 후 active 전환
      _do_switch_thread     — value=thread_id, 그 thread 로 active 전환
      _do_delete_thread     — value=thread_id, 삭제 후 active 재선정
    """
    if st.session_state.pop("_do_new_thread", False):
        th = sola_threads.create()
        st.session_state[_ACTIVE_THREAD_KEY] = th.id
        st.rerun()

    switch_id = st.session_state.pop("_do_switch_thread", None)
    if switch_id:
        if sola_threads.get(str(switch_id)):
            st.session_state[_ACTIVE_THREAD_KEY] = str(switch_id)
            st.rerun()

    del_id = st.session_state.pop("_do_delete_thread", None)
    if del_id:
        sola_threads.delete(str(del_id))
        # 활성 thread 가 지워졌다면 재선정
        if st.session_state.get(_ACTIVE_THREAD_KEY) == str(del_id):
            st.session_state.pop(_ACTIVE_THREAD_KEY, None)
        st.rerun()


def _group_label(iso: str) -> str:
    """thread 갱신 시각 → '오늘'/'어제'/'이번 주'/'이전' 그룹 라벨."""
    if not iso:
        return "이전"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return "이전"
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta_days = (now.date() - dt.date()).days
    if delta_days <= 0:
        return "오늘"
    if delta_days == 1:
        return "어제"
    if delta_days <= 7:
        return "이번 주"
    return "이전"


def _hhmm(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except Exception:
        return ""


def _render_thread_list_html(threads: "list[sola_threads.Thread]", active_id: str) -> str:
    """좌측 thread list — 시안 마크업과 호환되는 ul.ws-th-list 그룹 HTML."""
    if not threads:
        return (
            '<div style="padding: 18px 14px; text-align: center; color: var(--text-muted);'
            ' font-size: 13px; line-height: 1.6;">'
            '아직 대화가 없어요.<br>'
            '<span style="font-size:12px;">아래 입력창에 질문하면 첫 스레드가 만들어져요.</span>'
            '</div>'
        )

    # 그룹별 묶기 (순서: 오늘 → 어제 → 이번 주 → 이전, pinned 는 별도 그룹)
    groups: dict[str, list[sola_threads.Thread]] = {}
    pinned: list[sola_threads.Thread] = []
    for t in threads:
        if t.pinned:
            pinned.append(t)
            continue
        g = _group_label(t.updated_at or t.created_at)
        groups.setdefault(g, []).append(t)

    parts: list[str] = []

    def _emit_group(label: str, items: "list[sola_threads.Thread]") -> None:
        if not items:
            return
        parts.append(f'<div class="ws-th-grp">{_html.escape(label)}</div>')
        parts.append('<ul class="ws-th-list">')
        for t in items:
            active_cls = " ws-th-active" if t.id == active_id else ""
            time_label = _hhmm(t.updated_at or t.created_at)
            pin_mark = " · ★ 고정" if t.pinned else ""
            href = f"?app_area={_AREA_QUOTED}&switch_thread={t.id}"
            parts.append(
                f'<li class="ws-th-item{active_cls}">'
                f'<a class="ws-th-l" href="{href}" target="_self" style="display:flex; align-items:center; gap:10px; flex:1; text-decoration:none; color:inherit;">'
                f'<div class="ws-th-icon"><span style="font-size:11px;">💬</span></div>'
                f'<div>'
                f'<div class="ws-th-name">{_html.escape(t.title or "새 대화")}</div>'
                f'<div class="ws-th-meta">{_html.escape(time_label)} · 메시지 {int(t.message_count)}{pin_mark}</div>'
                f'</div>'
                f'</a>'
                f'</li>'
            )
        parts.append('</ul>')

    if pinned:
        _emit_group("★ 고정", pinned)
    for label in ("오늘", "어제", "이번 주", "이전"):
        _emit_group(label, groups.get(label, []))

    return "\n".join(parts)


def _render_thread_filters_html(threads: "list[sola_threads.Thread]") -> str:
    """필터 chip (현재는 시각만, 정직 카운트). active 는 '전체'."""
    total = len(threads)
    pinned = sum(1 for t in threads if t.pinned)
    return (
        f'<span class="ws-th-filter ws-th-filter-active">전체 {total}</span>'
        f'<span class="ws-th-filter" title="필터 wire 는 후속 PR" '
        f'style="opacity:0.5; cursor:not-allowed;">★ 고정 {pinned}</span>'
    )


def _switch_thread_from_query_if_any() -> None:
    """?switch_thread=<id> 가 URL 에 있으면 1회 소비 → active 전환 + query strip."""
    tid = st.query_params.get("switch_thread")
    if not tid:
        return
    if sola_threads.get(str(tid)):
        st.session_state[_ACTIVE_THREAD_KEY] = str(tid)
        # 다른 thread 의 메시지 캐시 — 정리하지 않아도 _active_thread() 가 새 키로 분기
    if "switch_thread" in st.query_params:
        del st.query_params["switch_thread"]
    st.rerun()


# 5-nav area_key 의 URL quote 캐시 (thread link 에 사용).
from urllib.parse import quote as _urlquote
_AREA_QUOTED = _urlquote("🤖 SOLA 작업실")


def _consume_prefill_ask_if_any() -> None:
    """`?ask_prefill=1` (또는 pending flag) → composer prefill 텍스트로 즉시 전송."""
    if not st.session_state.pop("_do_ask_prefill", False):
        return
    prefill, _ph, _pins = _composer_prefill()
    if prefill.strip():
        st.session_state["_do_sola_send"] = prefill.strip()
    st.rerun()


def _render_main(persona: Persona) -> None:
    """sola_main.html 템플릿 로드 + persona snapshot + composer prefill 치환."""
    name = persona.name or "사용자"
    dept = persona.dept or ""
    job = persona.job or ""
    line_parts = [p for p in (name, job, dept) if p]
    persona_line = " · ".join(line_parts) if line_parts else "사용자"

    interests = persona.interest_lv3 or persona.interest_tasks or []
    interests_label = ", ".join(interests[:3]) if interests else "미설정"

    prefill, placeholder, pins_html = _composer_prefill()
    messages = _load_messages()
    messages_html = _render_messages_html(messages)

    # Thread list — 활성 thread 강조 + 그룹별 묶기
    active_th = _active_thread()
    all_threads = sola_threads.list_threads()
    thread_list_html = _render_thread_list_html(all_threads, active_th.id)
    thread_filters_html = _render_thread_filters_html(all_threads)
    # 새 스레드 버튼 — `<a href>` 로 만들면 query param 안 쓰고 Streamlit
    # button (아래) 으로 일관 처리. 자리 표시용 정적 마크업만 placeholder 에 넣고
    # 실 인터랙션은 _render_main 마지막에 Streamlit button 추가.
    new_thread_btn_html = (
        '<button class="ws-new" disabled '
        'title="아래 +새 대화 버튼으로 생성">'
        '<img src="data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'13\' '
        "height='13' viewBox='0 0 24 24' fill='none' stroke='#475569' stroke-width='2.4' "
        "stroke-linecap='round' stroke-linejoin='round'><line x1='12' y1='5' x2='12' y2='19'/>"
        "<line x1='5' y1='12' x2='19' y2='12'/></svg>\" width=\"13\" height=\"13\" alt=\"\" />"
        "새 스레드"
        "</button>"
    )

    template = _SOLA_TEMPLATE.read_text(encoding="utf-8")
    html_out = (
        template
        .replace("{{PERSONA_LINE}}", _html.escape(persona_line))
        .replace("{{PERSONA_INTERESTS}}", _html.escape(interests_label))
        .replace("{{PERSONA_TEAM_SIZE}}", "5–15명")
        .replace("{{KEYWORDS_COUNT}}", "8개")
        .replace("{{NEW_THREAD_BTN}}", new_thread_btn_html)
        .replace("{{THREAD_FILTERS}}", thread_filters_html)
        .replace("{{THREAD_LIST}}", thread_list_html)
        .replace("{{WS_MESSAGES}}", messages_html)
        .replace("{{COMPOSER_PREFILL}}", _html.escape(prefill))
        .replace("{{COMPOSER_PLACEHOLDER}}", _html.escape(placeholder))
        .replace("{{COMPOSER_PINS}}", pins_html)
    )
    st.html(html_out)

    # ── 새 대화 시작 버튼 (Streamlit native, 실 인터랙션) ──
    # 시안의 좌측 <button class="ws-new"> 은 HTML 내부라 클릭 wire 불가 → 본문 위에
    # Streamlit 버튼으로 새 대화 생성을 노출.
    c1, c2, c3 = st.columns([1, 1, 6])
    with c1:
        if st.button("➕ 새 대화", key="sola_new_thread_btn",
                     use_container_width=True,
                     help="새 thread 시작 (현 대화는 좌측 목록에 보존됨)"):
            st.session_state["_do_new_thread"] = True
            st.rerun()
    with c2:
        # 현 thread 삭제 — 메시지 없을 때만 유효 (실수 방지)
        if active_th.message_count == 0 and len(all_threads) > 1:
            if st.button("🗑 빈 대화 정리", key="sola_del_thread_btn",
                         use_container_width=True):
                st.session_state["_do_delete_thread"] = active_th.id
                st.rerun()

    # ── prefill 인계받았을 때 즉시 전송 CTA (composer 시안 위) ──
    if prefill.strip():
        if st.button(
            "📨 이 컨텍스트로 SOLA에게 물어보기",
            key="sola_ask_prefill_btn",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["_do_ask_prefill"] = True
            st.rerun()

    # ── 실제 입력 — st.chat_input (자동 하단 고정 + 전송 버튼 내장) ──
    user_input = st.chat_input(placeholder or "SOLA 에게 질문하세요…", key="sola_chat_input")
    if user_input:
        st.session_state["_do_sola_send"] = user_input
        st.rerun()
