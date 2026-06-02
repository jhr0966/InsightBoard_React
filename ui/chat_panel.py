"""글로벌 SOLA 채팅 패널 — 모든 area 본문 우측 컬럼에 노출되는 채팅.

설계:
  - 활성 thread (sola_threads) 의 메시지 load + `st.form`(text_area + 보내기)
  - LLM 호출 인프라(sola_workshop_v2._consume_send_if_any/_build_llm_messages)
    재사용 — 풀 SOLA workshop 과 같은 thread/영구화 공유
  - 빈 thread 일 때: area 별 "이 화면에서 이런 걸 물어보세요" 안내 카드
  - 우측 컬럼 sticky 패널(`.side-chat-marker` + streamlit-overrides.css)

각 area 의 진입점:
    chat_panel.render_side(persona, area_key="📊 오늘의 보드")
        → 우측 컬럼에 실제 작동 채팅 (app.py 가 chat_col 안에서 호출)
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
    """area 별 안내 + 추천 질문 카드 — 채팅 스크롤 최상단에 **항상** 노출.

    추천 질문 chip 은 `?sola_prefill=<질문>` 링크라 클릭하면 입력창에 그대로
    채워진다(`_consume_prefill` 이 소비). 색은 모두 토큰 → 다크 추종.
    """
    intro = _AREA_INTROS.get(area_key) or _AREA_INTROS["📊 오늘의 보드"]
    headline = _html.escape(str(intro["headline"]))
    items = intro["suggestions"]
    chip_html = "".join(
        f'<a class="side-chat-chip" href="?sola_prefill={quote(str(s), safe="")}" '
        f'target="_self">{_html.escape(str(s))}</a>'
        for s in items
    )
    return (
        '<div class="side-chat-intro">'
        f'<div class="side-chat-intro-h">{headline}</div>'
        '<div class="side-chat-intro-sub">'
        '아래 입력창에 직접 적거나, 추천 질문을 눌러 시작하세요.'
        '</div>'
        f'<div class="side-chat-chips">{chip_html}</div>'
        '</div>'
    )


def _format_recent_messages(messages: list[dict], cap: int = 6) -> str:
    """최근 cap 개 메시지를 버블 마크업으로. 스크롤은 바깥 `.side-chat-scroll` 가 담당.

    색은 토큰(다크 추종), 버블 폭은 좁은 채팅 컬럼에 맞춰 92% 까지 넓힌다.
    """
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
                f'<div style="max-width:92%; padding:8px 12px; background:var(--accent-primary); '
                f'color:#fff; border-radius:12px 12px 4px 12px; font-size:13px; line-height:1.5; '
                f'word-break:break-word;">'
                f'{content}'
                f'</div></div>'
            )
        else:
            parts.append(
                f'<div style="display:flex; justify-content:flex-start; margin:6px 0;">'
                f'<div style="max-width:92%; padding:8px 12px; background:var(--surface-soft); '
                f'color:var(--text-primary); border:1px solid var(--surface-divider); '
                f'border-radius:12px 12px 12px 4px; font-size:13px; line-height:1.5; word-break:break-word;">'
                f'<div style="font-size:11px; color:var(--text-secondary); font-weight:700; margin-bottom:2px;">🤖 SOLA</div>'
                f'{content}'
                f'</div></div>'
            )
    return "".join(parts)


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
        'padding:0 2px 10px; border-bottom:1px solid var(--surface-divider); margin-bottom:10px;">'
        f'<span style="width:8px; height:8px; border-radius:50%; background:{dot};"></span>'
        '<span style="font-weight:800; font-size:15px; color:var(--text-primary);">SOLA</span>'
        f'<span style="font-size:12px; color:var(--text-muted); font-weight:600;">· {title_safe}</span>'
        '</div>'
    )

    try:
        messages = sw._load_messages()
    except Exception:
        messages = []

    safe_area = quote(area_key, safe="")
    input_key = f"_side_chat_input_{safe_area}"

    # 추천 질문 chip 클릭(`?sola_prefill=…`) → 입력창에 채움. 위젯 생성 전에 소비.
    _consume_prefill(input_key)

    # 안내 + 추천 질문은 **항상** 스크롤 최상단에 두고 그 아래 대화 — 대화를
    # 시작해도 위로 스크롤하면 안내·추천이 그대로 남아있다.
    st.html(
        '<div class="side-chat-scroll">'
        + _intro_card_html(area_key)
        + _format_recent_messages(messages)
        + '</div>'
    )

    with st.form(key=f"_side_chat_form_{safe_area}", clear_on_submit=True):
        user_input = st.text_area(
            "SOLA 에게 질문",
            key=input_key,
            placeholder="이 화면에 대해 무엇이든 물어보세요…",
            label_visibility="collapsed",
            height=120,
        )
        sent = st.form_submit_button("➤ 보내기", use_container_width=True)
    if sent and user_input and user_input.strip():
        st.session_state["_do_sola_send"] = user_input.strip()
        st.rerun()


def _consume_prefill(input_key: str) -> None:
    """추천 질문 chip(`?sola_prefill=`) 을 입력창 위젯 값으로 주입 후 쿼리 파라미터 제거.

    `st.text_area` 위젯 생성 **전에** session_state 를 세팅해야 초기값으로 반영된다
    (사이드바 nav 의 query_params 패턴과 동일 — on_click 미사용).
    """
    val = st.query_params.get("sola_prefill")
    if not val:
        return
    st.session_state[input_key] = val
    del st.query_params["sola_prefill"]


def consume_send_if_any(persona: Persona) -> None:
    """글로벌 채팅 전송 핸들러 — app.py 최상단에서 호출.

    sola_workshop_v2._consume_send_if_any 와 동일 흐름이지만 어느 area 에서든
    동작하도록 분리. 실제 LLM 호출은 sw 의 함수 위임.
    """
    from ui import sola_workshop_v2 as sw

    # _consume_send_if_any 가 _do_sola_send pending 을 소비 + LLM 호출 + append + rerun
    sw._consume_send_if_any(persona)
