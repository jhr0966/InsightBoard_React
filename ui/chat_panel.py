"""글로벌 SOLA 채팅 패널 — 모든 area 본문 하단에 노출되는 미니 채팅.

설계:
  - 활성 thread (sola_threads) 의 메시지 load + Streamlit chat_input
  - LLM 호출 인프라(sola_workshop_v2._consume_send_if_any/_build_llm_messages)
    재사용 — 풀 SOLA workshop 과 같은 thread/영구화 공유
  - 빈 thread 일 때: area 별 "이 화면에서 이런 걸 물어보세요" 안내 카드
  - chat_input 은 화면 하단 자동 고정 (Streamlit native)

각 area 의 진입점:
    chat_panel.render(persona, area_key="📊 오늘의 보드")
        → 본문 끝에 expander 안에 채팅
        → app.py 의 chat_context_block set 결과를 LLM 컨텍스트로 자동 첨부
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone
from urllib.parse import quote

import streamlit as st

from persona.schema import Persona
from sola.client import is_configured as _llm_ready


# ── area 별 안내 & 추천 질문 ─────────────────────────────────

_AREA_INTROS: dict[str, dict[str, list[str] | str]] = {
    "📊 오늘의 보드": {
        "headline": "📊 오늘의 보드 — SOLA 가 이 화면 데이터를 알고 있어요",
        "suggestions": [
            "오늘 KPI 중 가장 눈에 띄는 변화는?",
            "자동화 기회 top 4 중 우선 PoC 할 만한 1건은?",
            "트렌드 키워드에서 우리 부서 관련 인사이트는?",
            "탑 스토리 3건 요약해줘",
            "매트릭스 1위 후보의 위험요인은?",
        ],
    },
    "🧱 데이터 관리": {
        "headline": "🧱 데이터 관리 — 수집 상태·뉴스 라이브러리를 알고 있어요",
        "suggestions": [
            "최근 14일 수집 추이 분석",
            "출처별 분포에서 비정상 신호 있어?",
            "오늘 수집된 뉴스 중 우리 부서 관련만 3건 추천",
            "활성 출처가 줄어든 이유는?",
            "키워드 보강 추천",
        ],
    },
    "🔎 인사이트 분석": {
        "headline": "🔎 인사이트 분석 — 트렌드·매트릭스·공정 매핑을 알고 있어요",
        "suggestions": [
            "트렌드 top 6 키워드의 8주 추이 해석",
            "신규 등장 키워드가 우리 작업에 의미하는 바",
            "매트릭스 top 3 PoC 후보 비교",
            "공정 매핑 카드 1위의 다음 단계",
            "관심 키워드와 트렌드의 교집합",
        ],
    },
    "🤖 SOLA 작업실": {
        "headline": "🤖 SOLA 작업실 — 이전 대화 thread 모두 컨텍스트에 있어요",
        "suggestions": [
            "이전 thread 들 요약",
            "어떤 주제로 다시 시작할까?",
            "이번 주 한 SOLA 작업 정리",
        ],
    },
    "📦 산출물 보관함": {
        "headline": "📦 산출물 보관함 — 채택·대기·기각 카드를 알고 있어요",
        "suggestions": [
            "채택된 제안서들의 공통 성공 요인",
            "대기 중 어떤 걸 먼저 검토해야 해?",
            "기각된 사유 패턴 분석",
            "채택률 개선 방법",
        ],
    },
    "프로필 설정": {
        "headline": "👤 페르소나 편집 — 더 좋은 컨텍스트 설정을 도와드려요",
        "suggestions": [
            "내 부서·직무에 맞는 관심 공정 추천",
            "어떤 키워드를 추가하면 좋을까?",
            "유사 페르소나의 활용 사례",
        ],
    },
}


def _intro_card_html(area_key: str) -> str:
    """빈 thread 일 때 노출되는 area 별 안내 카드."""
    intro = _AREA_INTROS.get(area_key) or _AREA_INTROS["📊 오늘의 보드"]
    headline = _html.escape(str(intro["headline"]))
    items = intro["suggestions"]
    chip_html = "".join(
        f'<span style="display:inline-block; padding:6px 12px; margin:4px 4px 0 0; '
        f'background:#EFF6FF; border:1px solid #BFDBFE; border-radius:999px; '
        f'font-size:12.5px; color:#1E3A8A; line-height:1.4;">'
        f'{_html.escape(str(s))}'
        f'</span>'
        for s in items
    )
    return (
        f'<div style="padding:14px 16px; background:#F8FAFC; '
        f'border:1px solid #E5E7EB; border-radius:10px; line-height:1.5;">'
        f'<div style="font-weight:700; font-size:14px; color:#0F172A; margin-bottom:4px;">{headline}</div>'
        f'<div style="font-size:12.5px; color:#64748B; margin-bottom:8px;">'
        f'아래 입력창에 직접 적거나, 추천 질문 중 하나로 시작하세요.'
        f'</div>'
        f'<div>{chip_html}</div>'
        f'</div>'
    )


def _format_recent_messages(messages: list[dict], cap: int = 6) -> str:
    """최근 cap 개 메시지를 간단 마크업으로 (글로벌 패널 — 시안 ws-msg 아님)."""
    if not messages:
        return ""
    parts = []
    for m in messages[-cap:]:
        role = m.get("role", "")
        content = _html.escape((m.get("content", "") or "")[:600])
        content = content.replace("\n", "<br>")
        if role == "user":
            parts.append(
                f'<div style="display:flex; justify-content:flex-end; margin:6px 0;">'
                f'<div style="max-width:75%; padding:8px 12px; background:#2563EB; '
                f'color:#fff; border-radius:12px 12px 4px 12px; font-size:13px; line-height:1.5;">'
                f'{content}'
                f'</div></div>'
            )
        else:
            parts.append(
                f'<div style="display:flex; justify-content:flex-start; margin:6px 0;">'
                f'<div style="max-width:75%; padding:8px 12px; background:#F1F5F9; '
                f'color:#0F172A; border-radius:12px 12px 12px 4px; font-size:13px; line-height:1.5;">'
                f'<div style="font-size:11px; color:#475569; font-weight:700; margin-bottom:2px;">🤖 SOLA</div>'
                f'{content}'
                f'</div></div>'
            )
    return (
        '<div style="max-height:360px; overflow-y:auto; padding:4px 2px;">'
        + "".join(parts)
        + '</div>'
    )


def render(persona: Persona, area_key: str) -> None:
    """area 본문 끝에 글로벌 채팅 패널 렌더.

    - 활성 thread 의 최근 메시지 노출 (없으면 area 별 안내 카드)
    - chat_input — Streamlit 하단 자동 고정. send 시 sola_workshop_v2 의
      pending flag(`_do_sola_send`) 로 위임 → 다음 run 에서 LLM 호출 + 응답 append.
    """
    # 의존성 lazy import — 순환 회피 (sola_workshop_v2 가 이 모듈을 안 씀)
    from ui import sola_workshop_v2 as sw

    # SOLA workshop area 자체는 자기 풀스크린 채팅이 있으니 미니 패널 미렌더
    if area_key == "🤖 SOLA 작업실":
        return

    st.divider()
    title_safe = _html.escape(area_key)
    st.html(
        f'<div style="font-size:14px; font-weight:700; color:#0F172A; '
        f'margin:8px 0 6px;">💬 SOLA 와 대화 · <span style="color:#64748B; '
        f'font-weight:600;">{title_safe} 컨텍스트로</span></div>'
    )

    # 활성 thread 메시지 load
    try:
        messages = sw._load_messages()
    except Exception:
        messages = []

    if not messages:
        st.html(_intro_card_html(area_key))
    else:
        st.html(_format_recent_messages(messages))

    # chat_input — area 별 key 로 중복 회피.
    # 송신은 sola_workshop_v2 의 pending flag 위임 → 다음 run 의 _consume_send_if_any
    # 가 LLM 호출 + 메시지 append + chat_log 영구화 + rerun.
    safe_area = quote(area_key, safe="")
    user_input = st.chat_input(
        "SOLA 에게 질문하세요 — 위 추천 질문 그대로 적어도 됩니다",
        key=f"_global_chat_input_{safe_area}",
    )
    if user_input:
        st.session_state["_do_sola_send"] = user_input
        st.rerun()


def render_side(persona: Persona, area_key: str) -> None:
    """우측 컬럼 SOLA 채팅 (Phase A) — 모든 area 본문 우측에 **실제 작동** 채팅.

    이전 `app_shell.render_app_sola` 의 disabled 목업을 대체한다.
    - 활성 thread 의 최근 메시지(없으면 area 별 안내 카드).
    - `st.form`(text_area + submit) 송신 → `_do_sola_send` pending → 다음 run 의
      `consume_send_if_any` 가 LLM 호출 + append + chat_log 영구화.
    - `st.chat_input` 은 뷰포트 하단 전폭 고정이라 컬럼에 담기지 않으므로 form 사용.

    `.side-chat-marker` 는 `streamlit-overrides.css` 가 컬럼을 sticky 패널로 만드는 훅.
    """
    from ui import sola_workshop_v2 as sw

    title_safe = _html.escape(area_key)
    dot = "#15803D" if _llm_ready() else "#B45309"
    st.html(
        '<div class="side-chat-marker"></div>'
        '<div style="display:flex; align-items:center; gap:8px; '
        'padding:0 2px 10px; border-bottom:1px solid #E5E7EB; margin-bottom:10px;">'
        f'<span style="width:8px; height:8px; border-radius:50%; background:{dot};"></span>'
        '<span style="font-weight:800; font-size:15px; color:#0F172A;">SOLA</span>'
        f'<span style="font-size:12px; color:#64748B; font-weight:600;">· {title_safe}</span>'
        '</div>'
    )

    try:
        messages = sw._load_messages()
    except Exception:
        messages = []

    if not messages:
        st.html(_intro_card_html(area_key))
    else:
        st.html(_format_recent_messages(messages))

    safe_area = quote(area_key, safe="")
    with st.form(key=f"_side_chat_form_{safe_area}", clear_on_submit=True):
        user_input = st.text_area(
            "SOLA 에게 질문",
            key=f"_side_chat_input_{safe_area}",
            placeholder="이 화면에 대해 무엇이든 물어보세요…",
            label_visibility="collapsed",
            height=130,
        )
        sent = st.form_submit_button("➤ 보내기", use_container_width=True)
    if sent and user_input and user_input.strip():
        st.session_state["_do_sola_send"] = user_input.strip()
        st.rerun()


def consume_send_if_any(persona: Persona) -> None:
    """글로벌 채팅 전송 핸들러 — app.py 최상단에서 호출.

    sola_workshop_v2._consume_send_if_any 와 동일 흐름이지만 어느 area 에서든
    동작하도록 분리. 실제 LLM 호출은 sw 의 함수 위임.
    """
    from ui import sola_workshop_v2 as sw

    # _consume_send_if_any 가 _do_sola_send pending 을 소비 + LLM 호출 + append + rerun
    sw._consume_send_if_any(persona)
