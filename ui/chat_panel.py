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
from urllib.parse import quote, urlencode

import streamlit as st

from persona.schema import Persona
from sola.client import is_configured as _llm_ready


_SOLA_AREA = "🤖 SOLA 작업실"


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
    """area 별 안내 카드 — 채팅 스크롤 최상단에 **항상** 노출(헤드라인 + 한 줄 안내).

    추천 질문은 더 이상 전체 새로고침을 일으키는 `?sola_prefill=` 앵커가 아니라
    입력창 바로 위의 `st.pills`(`_chat_composer` fragment)로 렌더한다 → 칩을 눌러도
    화면 전체가 리로드되지 않고 입력창에 텍스트만 채워진다.
    """
    intro = _AREA_INTROS.get(area_key) or _AREA_INTROS["📊 오늘의 보드"]
    headline = _html.escape(str(intro["headline"]))
    return (
        '<div class="side-chat-intro">'
        f'<div class="side-chat-intro-h">{headline}</div>'
        '<div class="side-chat-intro-sub">'
        '아래 입력창에 직접 적거나, 추천 질문을 눌러 시작하세요.'
        '</div>'
        '</div>'
    )


def _suggestions_for(area_key: str) -> list[str]:
    """area 별 추천 질문 리스트 (정의 없으면 보드 기본)."""
    intro = _AREA_INTROS.get(area_key) or _AREA_INTROS["📊 오늘의 보드"]
    return [str(s) for s in (intro.get("suggestions") or [])]


_SOLA_QUICK_ACTIONS: list[tuple[str, str]] = [
    ("📝 제안서 생성", "generate_proposal"),
    ("📰 뉴스 요약", "summarize"),
    ("➕ 새 대화", "new_thread"),
]


def _quick_actions_html(area_key: str) -> str:
    """SOLA 작업실 area 전용 — 중앙 작업대 액션을 채팅 상단 quick-action 칩으로 흡수.

    "채팅으로 통합" 결정에 따라 제안서 생성·뉴스 요약·새 대화를 채팅 단일
    진입점으로 끌어온다. 각 칩은 `?sola_action=<name>` 링크(on_click 미사용)이며
    인계 컨텍스트(dept/lv3/from)를 보존해 제안서 생성이 인계 작업을 그대로 쓴다.
    `sola_workshop_v2._consume_sola_action_from_query_if_any` 가 소비한다.
    다른 area 는 빈 문자열(칩 미노출).
    """
    if area_key != _SOLA_AREA:
        return ""
    ctx = {
        k: v for k, v in (
            ("dept", st.query_params.get("dept", "")),
            ("lv3", st.query_params.get("lv3", "")),
            ("from", st.query_params.get("from", "")),
        ) if v
    }

    def _href(action: str) -> str:
        return "?" + urlencode({"sola_action": action, **ctx})

    chip_html = "".join(
        f'<a class="side-chat-action" href="{_html.escape(_href(action))}" '
        f'target="_self">{_html.escape(label)}</a>'
        for label, action in _SOLA_QUICK_ACTIONS
    )
    return (
        '<div class="side-chat-actions">'
        '<div class="side-chat-actions-h">빠른 작업</div>'
        f'<div class="side-chat-actions-row">{chip_html}</div>'
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

    # SOLA 작업실 — 작업대 액션을 채팅 상단 quick-action 칩으로(헤더 아래 고정,
    # 스크롤에 묻히지 않음). 다른 area 는 빈 문자열이라 아무것도 그리지 않는다.
    qa_html = _quick_actions_html(area_key)
    if qa_html:
        st.html(qa_html)

    try:
        messages = sw._load_messages()
    except Exception:
        messages = []

    safe_area = quote(area_key, safe="")
    input_key = f"_side_chat_input_{safe_area}"

    # 안내(헤드라인+한 줄)와 대화는 스크롤 영역에. 추천 질문 pill·입력창은 그 아래
    # _chat_composer(fragment)로 분리 — pill 클릭이 전체 리로드 없이 입력창만 채운다.
    st.html(
        '<div class="side-chat-scroll">'
        + _intro_card_html(area_key)
        + _format_recent_messages(messages)
        + '</div>'
    )

    _chat_composer(area_key, input_key, safe_area)


@st.fragment
def _chat_composer(area_key: str, input_key: str, safe_area: str) -> None:
    """추천 질문 pill + 입력 form — **fragment 스코프**.

    pill 클릭은 이 fragment 만 rerun 한다(전체 리로드/흰 깜빡임 없음): 선택값을
    입력창에 채우고 pill 선택을 즉시 해제해, 채운 뒤 사용자가 편집·재선택해도
    값이 덮어써지지 않는다(`__reset_pills` → 위젯 재생성 전에 선택 해제).
    보내기는 전체 rerun(`_do_sola_send` → app.py 상단 `consume_send_if_any`).
    """
    pills_key = f"{input_key}__pills"
    # (위젯 생성 전) 직전 pill 선택 해제 → pending prefill 주입 → 북마크 URL prefill.
    if st.session_state.pop(f"{input_key}__reset_pills", False):
        st.session_state[pills_key] = None
    _apply_pending_prefill(input_key)
    _consume_prefill(input_key)

    with st.container(key="side_chat_suggest"):
        picked = st.pills(
            "추천 질문",
            _suggestions_for(area_key),
            selection_mode="single",
            key=pills_key,
            label_visibility="collapsed",
        )
    if picked:
        st.session_state[f"{input_key}__prefill"] = picked
        st.session_state[f"{input_key}__reset_pills"] = True
        st.rerun(scope="fragment")

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


def _apply_pending_prefill(input_key: str) -> bool:
    """추천 질문 pill 클릭으로 세팅된 pending 값을 입력창 위젯 값으로 주입.

    `st.text_area` 위젯 생성 **전에** 호출해야 초기값으로 반영된다(on_click 미사용).
    pill 클릭은 query_param 을 건드리지 않으므로 전체가 아닌 fragment rerun 만 난다.
    """
    pend = st.session_state.pop(f"{input_key}__prefill", None)
    if pend is None:
        return False
    st.session_state[input_key] = pend
    return True


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
