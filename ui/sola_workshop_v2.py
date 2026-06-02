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

from persona import context as persona_ctx
from persona.schema import Persona
from sola import client as sola_client
from sola import propose as sola_propose
from sola import summarize as sola_summarize
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


def _archive_stats() -> dict[str, int]:
    """SOLA 좌측 통계 — 보드 KPI 실데이터(`board_v2._archive_stats`) 재사용.

    이전엔 match_today/opportunities 가 하드코딩 상수(32/4)였다. 보드와 동일한
    60초 캐시 소스(`_board_kpis`)를 공유해 실제 매칭/기회 수를 노출한다.
    """
    from ui import board_v2  # lazy — 모듈 로드 순환 회피

    try:
        return board_v2._archive_stats()
    except Exception:
        summary = bookmarks_store.summary_counts()
        pending = int(summary["proposal_status"].get("pending", 0))  # type: ignore[index]
        return {"match_today": 0, "opportunities": 0, "pending_adopt": pending}


def _ctx_archive_summary() -> tuple[int, str]:
    """우측 ws-ctx "산출물 보관함" 카드 — 대기 카운트 + 최근 1건 미리보기.

    thread ↔ bookmark 직접 연결 모델은 없으므로(후속 PR) "현재 보관함의 가장
    최근 pending 제안서" 를 대표로 노출 → 사용자가 [열기] 로 보관함 area 로 이동.
    """
    try:
        items = bookmarks_store.list_all(type_="proposal")
    except Exception:
        items = []
    pending = [b for b in items if b.status == "pending"]
    pending_count = len(pending)

    if not pending:
        body = (
            '<div style="padding: 14px 12px; font-size: 12.5px; color: var(--text-muted);'
            ' line-height: 1.5;">'
            '아직 제안서가 없어요.<br>'
            '<span style="font-size:11.5px;">보드의 자동화 기회 카드에서 SOLA 와 검토 → 채택하면 여기 모입니다.</span>'
            '</div>'
        )
        return 0, body

    # 가장 최근 pending — created_at 내림차순 첫 항목
    pending.sort(key=lambda b: b.created_at, reverse=True)
    top = pending[0]
    title_safe = _html.escape((top.title or "(제목 없음)")[:60])
    age_safe = _html.escape(_ctx_age_label(top.created_at))
    tag_text = "대기"  # 모두 pending
    from urllib.parse import quote as _q
    archive_href = "?app_area=" + _q("📦 산출물 보관함")
    body = (
        '<div class="ws-ctx-prop">'
        f'<div class="ws-prop-h">{title_safe}</div>'
        '<div class="ws-prop-meta">'
        f'<span class="ws-prop-tag-tech">{tag_text}</span>'
        f'<span class="ws-prop-state">{age_safe}</span>'
        '</div>'
        f'<a class="ws-ctx-link" href="{archive_href}" target="_self" '
        'style="text-decoration:none; display:inline-block;">'
        f'보관함 열기 ({pending_count}건 대기) →'
        '</a>'
        '</div>'
    )
    return pending_count, body


def _ctx_age_label(iso: str) -> str:
    """ISO → '오늘'/'어제'/'5월 17일' 짧은 라벨."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    now = datetime.now(timezone.utc)
    delta = (now.date() - dt.date()).days
    if delta <= 0:
        return "오늘"
    if delta == 1:
        return "어제"
    if delta <= 7:
        return f"{delta}일 전"
    return f"{dt.month}월 {dt.day}일"


def render() -> None:
    """SOLA 작업실 — 통일 셸의 **중앙 산출물 작업대(캔버스)**.

    좌측 사이드바·우측 LLM 채팅(`chat_panel.render_side`)은 `app.py` 가 그린다.
    이 함수는 중앙 메인 영역만 렌더: 액션(제안서 생성·요약) + 현재 산출물 문서 +
    세션/산출물 목록. **대화(메시지·입력)는 우측 채팅이 담당** — 다른 화면과 동일한
    [좌 사이드바 │ 중앙 콘텐츠 │ 우 채팅] 3영역 통일.
    """
    inject_screen_css("sola")
    persona = app_shell.get_persona()

    # ── pending 핸들러 (위젯 인스턴스화 이전) ──
    # send 는 app.py 의 chat_panel.consume_send_if_any 가 처리(우측 채팅과 thread 공유).
    _consume_thread_actions_if_any()
    _switch_thread_from_query_if_any()
    _consume_prefill_ask_if_any()
    _consume_generate_proposal_if_any(persona)
    _consume_summarize_if_any(persona)
    _consume_save_proposal_if_any()
    _render_sola_action_toasts()

    app_shell.render_topbar(
        page_title="SOLA 작업실",
        eyebrow_current="SOLA 작업실",
        refresh_label=app_shell.refresh_label_now(),
        fresh_kind="accent",
    )
    app_shell.render_setup_banner_if_needed()
    _render_brief_handoff_banner_if_needed()
    _render_workbench(persona)


def chat_context_block(persona: Persona) -> str:
    """우측 채팅(render_side)에 자동 첨부될 SOLA 작업실 컨텍스트."""
    parts = ["--- 현재 화면: SOLA 작업실 (제안서·요약 작업대) ---"]
    try:
        th = _active_thread()
        parts.append(f"활성 세션: {th.title or '새 대화'}")
    except Exception:
        pass
    dept = st.query_params.get("dept", "")
    lv3 = st.query_params.get("lv3", "")
    target = " · ".join(p for p in (dept, lv3) if p)
    if target:
        parts.append(f"인계 컨텍스트(작업): {target}")
    try:
        msgs = _load_messages()
        last = next(
            (m["content"] for m in reversed(msgs)
             if m.get("role") == "assistant" and (m.get("content") or "").strip()),
            "",
        )
        if last:
            parts.append("현재 산출물(발췌): " + last[:300])
    except Exception:
        pass
    return "\n".join(parts)


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
            font-weight: 500; color: var(--accent-active); margin-left: 6px;
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
            font-size: 11px; color: var(--accent-active); opacity: 0.7; letter-spacing: 0.04em;
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
    # LLM 으로 5~12자 압축 제목 → 실패 시 truncation fallback
    auto_title = None
    if role == "user" and (not th.title or th.title == "새 대화"):
        try:
            from sola.thread_title import generate as _gen_title
            auto_title = _gen_title(content)
        except Exception:
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


# ── 제안서 생성·저장 (Phase B — 제품 핵심 루프) ──────────────

def _related_news_df(dept: str, lv3: str, *, limit: int = 8):
    """제안서 근거용 관련 뉴스 — 최근 뉴스 중 작업(dept/lv3)과 매칭 상위 N건.

    매칭 결과가 없으면 최근 뉴스로 폴백. 뉴스가 아예 없으면 빈 DataFrame.
    """
    import pandas as pd

    try:
        from store import news_db
        news = news_db.load_news_for_days(14)
    except Exception:
        news = pd.DataFrame()
    if news is None or news.empty:
        return pd.DataFrame()
    if not (dept or lv3):
        return news.head(limit)
    try:
        from store import match
        tasks_df = pd.DataFrame([{
            "dept": dept, "lv1": "", "lv2": lv3, "lv3": lv3,
            "task": lv3, "sub_task": "",
        }])
        scored = match.score_matches(news, tasks_df, top_k=limit,
                                     semantic_weight=match.DEFAULT_SEMANTIC_WEIGHT)
        if not scored.empty and "link" in scored.columns and "link" in news.columns:
            links = [lnk for lnk in scored["link"].tolist() if lnk]
            rel = news[news["link"].isin(links)]
            if not rel.empty:
                return rel.head(limit)
    except Exception:
        pass
    return news.head(limit)


def _consume_generate_proposal_if_any(persona: Persona) -> None:
    """`_do_generate_proposal` pending → propose 엔진으로 구조화 제안서 생성 →
    assistant 메시지로 append.

    인계(dept/lv3) 컨텍스트 + 관련 뉴스 근거를 `sola.propose.propose_for_task`
    (전용 제안서 시스템 프롬프트)에 넘긴다. LLM 미설정 시 propose 가 입력
    미리보기를 반환하므로 무중단.
    """
    payload = st.session_state.pop("_do_generate_proposal", None)
    if not payload:
        return
    dept = str(payload.get("dept", "")).strip()
    lv3 = str(payload.get("lv3", "")).strip()
    target = " · ".join(p for p in (dept, lv3) if p) or "선택한 작업"

    task = {
        "team": persona.team or "",
        "dept": dept or persona.dept or "",
        "lv3": lv3,
        "task": lv3 or target,
    }
    news_df = _related_news_df(dept, lv3)

    # 사용자 요청을 메시지로 남겨 맥락/제목 보존
    _append_message("user", f"📝 [{target}] 자동화 과제 제안서를 생성해줘.")
    try:
        with st.spinner("SOLA 가 제안서를 작성하고 있어요…"):
            proposal = sola_propose.propose_for_task(task, news_df, persona=persona)
        _append_message("assistant", proposal)
        n = 0 if news_df is None or news_df.empty else len(news_df)
        st.session_state["_sola_action_toast"] = (
            "ok",
            f"제안서 초안을 생성했어요 — 근거 뉴스 {n}건. ‘📦 보관함에 저장’으로 산출물로 남기세요.",
        )
    except Exception as exc:
        _append_message("assistant", f"⚠️ 제안서 생성 실패: {type(exc).__name__}: {exc}")
        st.session_state["_sola_action_toast"] = ("error", f"제안서 생성 실패: {type(exc).__name__}")
    st.rerun()


def _consume_summarize_if_any(persona: Persona) -> None:
    """`_do_summarize` pending → 최근 뉴스를 `sola.summarize` 로 요약 → assistant 메시지."""
    if not st.session_state.pop("_do_summarize", False):
        return
    import pandas as pd
    try:
        from store import news_db
        news = news_db.load_news_for_days(7)
    except Exception:
        news = pd.DataFrame()
    _append_message("user", "📰 최근 수집 뉴스를 요약해줘.")
    try:
        with st.spinner("SOLA 가 뉴스를 요약하고 있어요…"):
            out = sola_summarize.summarize_news(news)
        _append_message("assistant", out)
        n = 0 if news is None or news.empty else len(news)
        st.session_state["_sola_action_toast"] = ("ok", f"최근 뉴스 {n}건을 요약했어요.")
    except Exception as exc:
        _append_message("assistant", f"⚠️ 요약 실패: {type(exc).__name__}: {exc}")
        st.session_state["_sola_action_toast"] = ("error", f"요약 실패: {type(exc).__name__}")
    st.rerun()


def _consume_save_proposal_if_any() -> None:
    """`_do_save_proposal` pending → 현 thread 의 마지막 제안서(assistant)를
    proposal 북마크로 저장(실 content).

    thread 당 안정 id → 재저장은 갱신(중복 방지). 저장 후 보드/사이드바의
    '채택 대기' 카운트 캐시를 무효화. 이로써 끊겨 있던 루프
    (기회 → 생성 → 보관함)가 닫힌다.
    """
    if not st.session_state.pop("_do_save_proposal", False):
        return
    msgs = _load_messages()
    proposal = ""
    for m in reversed(msgs):
        if m.get("role") == "assistant" and (m.get("content") or "").strip():
            proposal = m["content"].strip()
            break
    if not proposal:
        st.session_state["_sola_action_toast"] = (
            "warn", "저장할 제안서 내용이 없어요. 먼저 ‘📝 제안서 생성’으로 초안을 만들어주세요.",
        )
        st.rerun()
        return

    th = _active_thread()
    title = (th.title or "SOLA 제안서").strip()[:80]
    tags = [t for t in (st.query_params.get("dept", ""), st.query_params.get("lv3", "")) if t]
    bm_id = "sola_" + bookmarks_store.make_id("proposal", th.id)
    try:
        bookmarks_store.add(bookmarks_store.Bookmark(
            id=bm_id, type="proposal", title=title, content=proposal,
            tags=tags, status="pending",
        ))
        try:  # 보드/사이드바 '채택 대기' 카운트 갱신
            from ui import board_v2
            board_v2._board_kpis.clear()
            board_v2._archive_stats.clear()
        except Exception:
            pass
        st.session_state["_sola_action_toast"] = (
            "ok", f"제안서를 산출물 보관함에 저장했어요 — ‘{title[:30]}’ (검토 대기)",
        )
    except Exception as exc:
        st.session_state["_sola_action_toast"] = ("error", f"저장 실패: {type(exc).__name__}")
    st.rerun()


def _render_sola_action_toasts() -> None:
    """제안서 생성/저장 액션 피드백 토스트 1회 소비."""
    toast = st.session_state.pop("_sola_action_toast", None)
    if not toast:
        return
    kind, text = toast
    icon = {"ok": "✅", "warn": "⚠️", "error": "🚫"}.get(kind, "")
    st.toast(f"{icon} {text}".strip())


def _consume_thread_actions_if_any() -> None:
    """Thread 관련 pending → 실행 후 rerun.

    flag:
      _do_new_thread        — 새 thread 생성 후 active 전환
      _do_switch_thread     — value=thread_id, 그 thread 로 active 전환
      _do_toggle_pin        — value=thread_id, pinned 토글
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

    pin_id = st.session_state.pop("_do_toggle_pin", None)
    if pin_id:
        cur = sola_threads.get(str(pin_id))
        if cur:
            sola_threads.update(str(pin_id), pinned=not cur.pinned, touch=False)
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


def _filter_threads_by_query(threads: "list[sola_threads.Thread]", query: str) -> "list[sola_threads.Thread]":
    """제목에 query 가 포함된 thread 만 (대소문자 무시, 공백 strip).

    빈 query 면 입력 그대로 반환.
    """
    q = (query or "").strip().lower()
    if not q:
        return threads
    return [t for t in threads if q in (t.title or "").lower()]


def _render_thread_list_html(threads: "list[sola_threads.Thread]", active_id: str,
                             search_query: str = "") -> str:
    """좌측 thread list — 시안 마크업과 호환되는 ul.ws-th-list 그룹 HTML.

    Args:
        threads: 표시할 thread 리스트 (이미 정렬됨).
        active_id: 강조할 활성 thread id.
        search_query: 검색어 (있으면 결과를 단일 '검색 결과 N건' 그룹으로 평탄화).
    """
    if not threads and not search_query.strip():
        return (
            '<div style="padding: 18px 14px; text-align: center; color: var(--text-muted);'
            ' font-size: 13px; line-height: 1.6;">'
            '아직 대화가 없어요.<br>'
            '<span style="font-size:12px;">아래 입력창에 질문하면 첫 스레드가 만들어져요.</span>'
            '</div>'
        )

    def _item_html(t: "sola_threads.Thread") -> str:
        active_cls = " ws-th-active" if t.id == active_id else ""
        time_label = _hhmm(t.updated_at or t.created_at)
        pin_mark = " · ★ 고정" if t.pinned else ""
        href = f"?app_area={_AREA_QUOTED}&switch_thread={t.id}"
        return (
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

    parts: list[str] = []

    # 검색 모드 — 단일 평탄 그룹
    if search_query.strip():
        filtered = _filter_threads_by_query(threads, search_query)
        if not filtered:
            return (
                f'<div class="ws-th-grp">검색 결과</div>'
                '<div style="padding: 18px 14px; text-align: center; color: var(--text-muted);'
                ' font-size: 13px; line-height: 1.6;">'
                f'“{_html.escape(search_query[:40])}” 와 일치하는 대화가 없어요.<br>'
                '<span style="font-size:12px;">검색을 지우면 전체 목록으로 돌아갑니다.</span>'
                '</div>'
            )
        parts.append(f'<div class="ws-th-grp">검색 결과 {len(filtered)}건</div>')
        parts.append('<ul class="ws-th-list">')
        parts.extend(_item_html(t) for t in filtered)
        parts.append('</ul>')
        return "\n".join(parts)

    # 일반 모드 — 그룹별 묶기 (순서: ★고정 → 오늘 → 어제 → 이번 주 → 이전)
    groups: dict[str, list[sola_threads.Thread]] = {}
    pinned: list[sola_threads.Thread] = []
    for t in threads:
        if t.pinned:
            pinned.append(t)
            continue
        g = _group_label(t.updated_at or t.created_at)
        groups.setdefault(g, []).append(t)

    def _emit_group(label: str, items: "list[sola_threads.Thread]") -> None:
        if not items:
            return
        parts.append(f'<div class="ws-th-grp">{_html.escape(label)}</div>')
        parts.append('<ul class="ws-th-list">')
        parts.extend(_item_html(t) for t in items)
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
    """`_do_ask_prefill` pending → **새 thread 생성** 후 prefill 텍스트로 전송.

    인계(보드/인사이트 CTA)는 보통 새 주제이므로, 기존 대화에 섞지 않고
    전용 thread 를 만든다. thread 제목은 인계 종류로 시드(첫 user 메시지가
    채워지면 _append_message 가 다시 제목을 잡음).
    """
    if not st.session_state.pop("_do_ask_prefill", False):
        return
    prefill, _ph, _pins = _composer_prefill()
    if prefill.strip():
        # 인계 전용 새 thread — 종류 기반 임시 제목
        from_kind = st.query_params.get("from", "")
        seed_title = {
            "brief": "보드 브리핑 검토",
            "opp": "자동화 기회 검토",
            "matrix": "매트릭스 후보 검토",
            "ia_map": "공정 매핑 분석",
            "edit": "제안서 이어서 수정",
        }.get(from_kind, "")
        th = sola_threads.create(seed_title)
        st.session_state[_ACTIVE_THREAD_KEY] = th.id
        st.session_state["_do_sola_send"] = prefill.strip()
    st.rerun()


def _render_workbench(persona: Persona) -> None:
    """중앙 산출물 작업대(캔버스) — 액션 + 현재 산출물 문서 + 세션/산출물 목록.

    대화·입력은 우측 채팅(`chat_panel.render_side`)이 담당하므로 여기엔 chat_input 없음.
    """
    _SEC = ('<div style="font-size:12px; font-weight:800; letter-spacing:0.08em; '
            'text-transform:uppercase; color:var(--text-muted); margin:{m};">{t}</div>')

    messages = _load_messages()
    last_assistant = next(
        (m for m in reversed(messages)
         if m.get("role") == "assistant" and (m.get("content") or "").strip()),
        None,
    )
    hand_dept = st.query_params.get("dept", "")
    hand_lv3 = st.query_params.get("lv3", "")
    prefill, _ph, _pins = _composer_prefill()
    target = " · ".join(p for p in (hand_dept, hand_lv3) if p)
    has_handoff = bool(target or prefill.strip())
    gen_payload = {"dept": hand_dept, "lv3": hand_lv3, "kind": st.query_params.get("from", "")}

    # ── 1) 액션 바 ──
    chip = (
        f'<span style="display:inline-flex; align-items:center; gap:6px; padding:5px 11px; '
        f'background:rgba(37,99,235,0.12); border:1px solid rgba(37,99,235,0.30); border-radius:999px; font-size:12.5px; '
        f'font-weight:600; color:var(--accent-active);">🎯 {_html.escape(target)}</span>'
        if target else
        '<span style="display:inline-flex; align-items:center; gap:6px; padding:5px 11px; '
        'background:var(--surface-soft); border:1px solid var(--surface-divider); border-radius:999px; font-size:12.5px; '
        'font-weight:600; color:var(--text-secondary);">👤 페르소나 컨텍스트</span>'
    )
    st.html(
        '<div style="display:flex; justify-content:space-between; align-items:center; '
        'gap:12px; flex-wrap:wrap; margin:2px 0 12px;"><div>'
        '<div style="font-size:12px; font-weight:800; letter-spacing:0.1em; '
        'text-transform:uppercase; color:var(--text-muted);">작업대</div>'
        '<div style="font-size:14px; color:var(--text-secondary); margin-top:2px;">'
        '제안서·요약을 만들고 산출물로 저장하세요</div></div>'
        f'<div>{chip}</div></div>'
    )
    a1, a2, a3 = st.columns([1.4, 1.2, 1.1])
    with a1:
        if st.button("📝 제안서 생성", key="wb_gen_proposal", type="primary",
                     use_container_width=True,
                     help="인계 컨텍스트(부서·공정) + 관련 뉴스로 자동화 과제 제안서 초안을 생성"):
            st.session_state["_do_generate_proposal"] = gen_payload
            st.rerun()
    with a2:
        if st.button("📰 뉴스 요약", key="wb_summarize", use_container_width=True,
                     help="최근 7일 수집 뉴스를 요약"):
            st.session_state["_do_summarize"] = True
            st.rerun()
    with a3:
        if st.button("➕ 새 대화", key="wb_new_thread", use_container_width=True,
                     help="새 세션 시작 (현 세션은 아래 목록에 보존)"):
            st.session_state["_do_new_thread"] = True
            st.rerun()

    # ── 2) 현재 산출물 (캔버스) ──
    st.html(_SEC.format(m="18px 0 8px", t="현재 산출물"))
    if last_assistant is not None:
        active_th = _active_thread()
        doc_title = (active_th.title or "SOLA 산출물").strip()
        with st.container(border=True):
            st.markdown(f"##### 📄 {doc_title}")
            st.markdown(last_assistant.get("content", ""))
        s1, s2, _s3 = st.columns([1.3, 1.1, 1.4])
        with s1:
            if st.button("📦 보관함에 저장", key="wb_save_proposal", type="primary",
                         use_container_width=True,
                         help="이 산출물을 제안서로 보관함에 저장(검토 대기)"):
                st.session_state["_do_save_proposal"] = True
                st.rerun()
        with s2:
            if has_handoff and st.button("🔄 다시 생성", key="wb_regen",
                                         use_container_width=True,
                                         help="같은 컨텍스트로 제안서를 다시 생성"):
                st.session_state["_do_generate_proposal"] = gen_payload
                st.rerun()
    else:
        st.html(
            '<div style="padding:28px 18px; text-align:center; background:var(--surface-soft); '
            'border:1px dashed var(--surface-divider); border-radius:14px; color:var(--text-secondary);">'
            '<div style="font-size:26px; margin-bottom:6px;">🪄</div>'
            '<div style="font-size:15px; font-weight:700; color:var(--text-primary);">아직 산출물이 없어요</div>'
            '<div style="font-size:13px; line-height:1.6; margin-top:4px;">'
            '위 <b>📝 제안서 생성</b>으로 시작하거나, 오른쪽 <b>SOLA 채팅</b>으로 대화하면 '
            '결과가 여기에 문서로 정리됩니다.</div></div>'
        )

    # ── 3) 세션 목록 ──
    st.html(_SEC.format(m="22px 0 8px", t="내 세션"))
    all_threads = sola_threads.list_threads()
    st.text_input("세션 검색", key="_sola_search_q",
                  placeholder="세션 제목으로 검색 — 비우면 전체",
                  label_visibility="collapsed")
    search_query = st.session_state.get("_sola_search_q", "") or ""
    active_th = _active_thread()
    st.html(
        '<div class="ws-threads" style="margin-top:4px;">'
        + _render_thread_list_html(all_threads, active_th.id, search_query)
        + '</div>'
    )

    # 현재 세션 관리 (고정 / 삭제) — 기능 보존
    m1, m2, _m3 = st.columns([1.3, 1.3, 2])
    with m1:
        pin_label = "📌 고정 해제" if active_th.pinned else "📌 세션 고정"
        if st.button(pin_label, key="wb_pin", use_container_width=True):
            st.session_state["_do_toggle_pin"] = active_th.id
            st.rerun()
    with m2:
        if len(all_threads) > 1:
            confirm_key = f"_confirm_del_{active_th.id}"
            if st.session_state.get(confirm_key):
                if st.button("⚠️ 정말 삭제", key="wb_del_confirm", type="primary",
                             use_container_width=True):
                    st.session_state["_do_delete_thread"] = active_th.id
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
            else:
                if st.button("🗑 세션 삭제", key="wb_del", use_container_width=True,
                             help="이 세션과 메시지를 영구 삭제"):
                    st.session_state[confirm_key] = True
                    st.rerun()

    # ── 4) 저장한 산출물 (보관함 pending) ──
    _cnt, prop_html = _ctx_archive_summary()
    st.html(_SEC.format(m="22px 0 8px", t="저장한 산출물") + prop_html)
