"""글로벌 SOLA 채팅 패널 — 모든 area 본문 우측 컬럼에 노출되는 채팅.

설계:
  - 활성 thread (sola_threads) 의 메시지 load + `st.form`(text_area + 보내기)
  - LLM 호출 인프라(sola_workshop_v2 의 _append_message/_load_messages/
    _build_llm_messages) 재사용 — 풀 SOLA workshop 과 같은 thread/영구화 공유
  - 빈 thread 일 때: area 별 "이 화면에서 이런 걸 물어보세요" 안내 카드
  - 우측 컬럼 sticky 패널(`.side-chat-marker` + streamlit-overrides.css)
  - **부분 rerun**: 패널 본체는 `_render_side_fragment`(@st.fragment) — 메시지
    전송·추천 질문 pill 이 앱 전체가 아니라 **채팅 컬럼만** 다시 그린다.
    (예외: SOLA 작업실 form 전송과 빠른 작업 칩은 중앙 작업대가 결과를 봐야
    하므로 scope="app" 전체 rerun.)

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
from sola import client as sola_client
from sola.client import is_configured as _llm_ready
from sola.preview import format_messages_preview


_SOLA_AREA = "🤖 SOLA 작업실"


# ── area 별 안내 & 추천 질문 ─────────────────────────────────

# 추천 질문 = "이 화면에서 SOLA 를 이렇게 쓰는 겁니다" 시연 — 화면 데이터를 실제로
# 읽어야 답할 수 있는 구체적 행동(요약·비교·보고서 초안·다음 단계)으로 구성한다.
_AREA_INTROS: dict[str, dict[str, list[str] | str]] = {
    "📊 오늘의 보드": {
        "headline": "📊 오늘의 보드 — SOLA 가 이 화면 데이터를 알고 있어요",
        "suggestions": [
            "오늘 브리핑 5건 중 우리 팀이 가장 먼저 봐야 할 1건과 그 이유는?",
            "자동화 제안 1위를 PoC 로 시작한다면 다음 주 할 일 3가지 뽑아줘",
            "트렌드에서 '신규' 표시된 키워드만 골라 왜 떴는지 설명해줘",
            "오늘 화면 내용으로 팀장 보고용 3줄 요약 써줘",
            "매트릭스 우상단 후보의 기대 효과와 리스크를 표로 비교해줘",
        ],
    },
    "🗞 뉴스 수집": {
        "headline": "🗞 뉴스 수집 — 지금 보이는 기사·수집 상태를 알고 있어요",
        "suggestions": [
            "지금 화면에 보이는 기사들 핵심만 3줄로 요약해줘",
            "오늘 수집분에서 우리 부서가 참고할 기사 3건 골라 이유와 함께",
            "출처별 7일 수집량을 보고 수집이 줄어든 출처와 원인 추정해줘",
            "지금 키워드에 추가하면 좋을 검색어 3개를 근거와 함께 추천해줘",
            "이번 주 수집 현황을 주간 리포트 초안으로 정리해줘",
        ],
    },
    "📋 작업 정의": {
        "headline": "📋 작업 정의 — 등록된 작업 정의·부서 분포를 알고 있어요",
        "suggestions": [
            "부서별 작업 정의 분포에서 빈 곳(미등록 공정)을 찾아줘",
            "등록된 작업 중 자동화 효과가 클 것 같은 3건과 이유는?",
            "최근 추가된 작업 정의를 한 줄씩 요약해줘",
            "작업 정의를 더 채우려면 어떤 항목부터 보강해야 할까?",
            "엑셀 업로드 형식(필수 컬럼)을 알려줘",
        ],
    },
    "🔎 인사이트 분석": {
        "headline": "🔎 인사이트 분석 — 트렌드·매트릭스·공정 매핑을 알고 있어요",
        "suggestions": [
            "트렌드 top 키워드의 추이를 해석하고 우리 작업과 연결해줘",
            "신규 등장 키워드가 어떤 공정에 영향을 줄지 짚어줘",
            "매트릭스 top 3 후보를 효과·난이도·근거 뉴스로 비교해줘",
            "히트맵에서 가장 뜨거운 공정×기술 조합의 다음 단계는?",
            "이 화면 내용으로 월간 기술 동향 보고 초안 써줘",
        ],
    },
    "🤖 SOLA 작업실": {
        "headline": "🤖 SOLA 작업실 — 이전 대화 thread 모두 컨텍스트에 있어요",
        "suggestions": [
            "지금 작업 중인 산출물의 약한 부분을 지적하고 보강안 줘",
            "이 제안서를 임원 보고용 1장으로 압축해줘",
            "이전 thread 에서 결정된 사항만 모아 정리해줘",
        ],
    },
    "📦 산출물 보관함": {
        "headline": "📦 산출물 보관함 — 채택·대기·기각 카드를 알고 있어요",
        "suggestions": [
            "대기 중인 제안서를 검토 우선순위 순으로 정렬하고 이유 알려줘",
            "채택된 제안서들의 공통 성공 요인을 뽑아줘",
            "기각 사유 패턴을 분석해서 다음 제안서에 반영할 점 알려줘",
            "이번 달 채택/기각 현황을 한 문단으로 보고해줘",
        ],
    },
    "페르소나 설정": {
        "headline": "👤 페르소나 설정 — 더 좋은 컨텍스트 설정을 도와드려요",
        "suggestions": [
            "내 부서·직무 기준으로 관심 공정을 추천해줘",
            "지금 설정에서 비어 있는 항목과 채우면 좋아지는 점은?",
            "뉴스가 더 잘 잡히도록 관심 키워드 5개 제안해줘",
        ],
    },
}


def _intro_card_html(area_key: str) -> str:
    """area 별 안내 카드 — 채팅 스크롤 최상단에 **항상** 노출(헤드라인 + 한 줄 안내).

    추천 질문은 안내 바로 밑의 `st.pills`(`_render_chat_suggestions`)로 렌더한다
    → 칩을 누르면 그 질문이 **바로 전송**되어 SOLA 답변까지 이어진다.
    """
    intro = _AREA_INTROS.get(area_key) or _AREA_INTROS["📊 오늘의 보드"]
    headline = _html.escape(str(intro["headline"]))
    return (
        '<div class="side-chat-intro">'
        f'<div class="side-chat-intro-h">{headline}</div>'
        '<div class="side-chat-intro-sub">'
        '아래 입력창에 직접 적거나, 추천 질문을 누르면 바로 전송됩니다.'
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


def _render_quick_action_chips(area_key: str) -> None:
    """SOLA 작업실 전용 빠른 작업 칩 — st.button 3개(소켓 rerun, 문서 reload 없음).

    직전엔 `?sola_action=` 앵커라 클릭마다 **문서 전체 reload**(흰 깜빡임)였다 →
    버튼 + `_sola_action_pending` 세션 플래그로 전환. 인계 컨텍스트(dept/lv3/from)는
    쿼리에서 읽어 보존하고, `sola_workshop_v2._consume_sola_action_from_query_if_any`
    가 쿼리보다 먼저 소비해 기존 pending flag(LLM 호출 경로)로 매핑한다.
    다른 area 는 아무것도 그리지 않는다.

    ⚠ scope="app" 필수: 이 pending 의 소비자(`sola_workshop_v2.render` 최상단)는
    **중앙 컬럼** — 채팅 fragment 바깥이다. fragment 부분 rerun 으론 중앙이 다시
    실행되지 않으므로 칩 클릭은 반드시 앱 전체 rerun 으로 승격한다.
    """
    if area_key != _SOLA_AREA:
        return
    ctx = {k: st.query_params.get(k, "") for k in ("dept", "lv3", "from")}
    with st.container(key="side_quick_actions"):
        st.html('<div class="side-chat-actions-h">빠른 작업</div>')
        cols = st.columns(len(_SOLA_QUICK_ACTIONS))
        for col, (label, action) in zip(cols, _SOLA_QUICK_ACTIONS):
            with col:
                if st.button(label, key=f"side_qa_{action}", use_container_width=True):
                    st.session_state["_sola_action_pending"] = {"action": action, **ctx}
                    st.rerun(scope="app")


def _format_recent_messages(messages: list[dict], cap: int = 6) -> str:
    """최근 cap 개 메시지를 버블 마크업으로 (시간순, 최신이 아래).

    색은 토큰(다크 추종), 버블 폭은 좁은 채팅 컬럼에 맞춰 92% 까지 넓힌다.
    스크롤은 바깥 `.st-key-side_chat_scrollwrap`(안내·추천 칩까지 함께 스크롤)이
    담당한다 — 추천 질문이 메시지와 함께 위로 밀려 올라가도록(사용자 요청).
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
    """우측 컬럼 SOLA 채팅 진입점 — 얇은 래퍼, 본체는 `_render_side_fragment`.

    app.py 가 chat_col 안에서 호출하는 공개 시그니처는 그대로 두고, 실제 렌더는
    @st.fragment 본체에 위임 → 패널 내부 상호작용(전송·추천 질문 pill)이
    **채팅 컬럼만** 부분 rerun 한다(본문·사이드바·topbar 재실행 없음).
    """
    _render_side_fragment(persona, area_key)


@st.fragment
def _render_side_fragment(persona: Persona, area_key: str) -> None:
    """우측 컬럼 SOLA 채팅 본체 — 부분 rerun 경계(@st.fragment).

    이전 `app_shell.render_app_sola` 의 disabled 목업을 대체한다.
    - 활성 thread 의 최근 메시지(없으면 area 별 안내 카드).
    - 레이아웃: 안내 카드(상단) → 추천 질문 칩(`_render_chat_suggestions`, 안내 바로
      밑 — 클릭 = 즉시 전송) → 대화 스크롤(중단) → 입력 form(`_render_chat_input`,
      컬럼 하단 고정). 칩은 위에, 입력+보내기는 항상 맨 아래 핀.
    - `st.form`(text_area + submit) 송신 → `_do_sola_send` pending → fragment rerun
      최상단의 `consume_send_if_any(scope="fragment")` 가 LLM 호출 + append +
      chat_log 영구화 → 새 메시지가 **이 fragment rerun 안에서** 바로 그려진다.
      (SOLA 작업실만 scope="app" 전송 — 중앙 작업대 캔버스가 같은 런에서 갱신돼야
      하므로 app.py 최상단 consume 경로를 탄다. `_render_chat_input` 참고.)
    - LLM 컨텍스트(`_chat_context_for_sola`)는 직전 풀런에서 app.py 가 세션에 저장한
      값을 `sw._build_llm_messages` 가 session_state 로 읽으므로 fragment rerun
      에서도 그대로 유효하다.
    - `st.chat_input` 은 뷰포트 하단 전폭 고정이라 컬럼에 담기지 않으므로 form 사용.

    `.side-chat-marker` 는 `streamlit-overrides.css` 가 컬럼을 sticky 패널로 만드는 훅.
    """
    # 부분 rerun 경로의 송신 처리 — 메시지 목록·위젯 생성 **전에** 소비해야
    # 이번 fragment rerun 에 새 user/assistant 메시지가 보인다. 풀런에서는
    # app.py 최상단 consume 가 먼저 pop 하므로 여기는 fragment rerun 에서만 발화
    # (scope="fragment" 는 fragment rerun 중에만 유효 — Streamlit 1.58 제약).
    consume_send_if_any(persona, scope="fragment")

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
    # 스크롤에 묻히지 않음). 버튼(소켓 rerun)이라 문서 reload 없음.
    _render_quick_action_chips(area_key)

    try:
        messages = sw._load_messages()
    except Exception:
        messages = []

    safe_area = quote(area_key, safe="")
    input_key = f"_side_chat_input_{safe_area}"

    # 칩 클릭(즉시 전송) 후 pill 선택 해제 — 같은 칩 재클릭이 다시 발화하도록.
    if st.session_state.pop(f"{input_key}__reset_pills", False):
        st.session_state[f"{input_key}__pills"] = None
    _consume_prefill(input_key)         # 레거시 ?sola_prefill= 북마크 URL 호환

    # 스크롤 래퍼 — 안내 카드 + 추천 질문 칩 + 대화를 **함께** 스크롤(헤더·입력창만 고정).
    # 직전엔 안내·추천 칩이 상단 고정 flex item 이라 메시지가 쌓여도 자리를 차지했다 →
    # 사용자 요청대로 추천 질문이 메시지와 함께 위로 밀려 스크롤되도록 한 컨테이너로 묶는다.
    with st.container(key="side_chat_scrollwrap"):
        st.html('<div class="side-chat-top">' + _intro_card_html(area_key) + '</div>')
        # 추천 질문 칩 — 안내 바로 밑. 클릭 시 즉시 전송.
        _render_chat_suggestions(area_key, input_key)
        # 대화 — 메시지(시간순, 최신이 아래). 스크롤은 바깥 래퍼가 담당.
        st.html('<div class="side-chat-scroll">' + _format_recent_messages(messages) + '</div>')
    # 새 메시지 도착 시 스크롤 래퍼를 최하단으로 — 시그니처(개수+마지막 내용)가
    # 바뀔 때만 스크립트가 재실행되어, 사용자가 위로 올려 읽는 중에는 건드리지 않는다.
    _inject_autoscroll(messages)
    # 입력창 + 보내기 — 하단 고정(CSS margin-top:auto)
    _render_chat_input(input_key, safe_area, area_key)


def _inject_autoscroll(messages: list[dict]) -> None:
    """채팅에 새 내용이 추가되면 스크롤 래퍼를 **자동으로 최하단**으로 내린다.

    - nonce = 메시지 개수 + 마지막 내용 해시 → 메시지가 바뀐 rerun 에서만 마크업이
      달라져 스크립트가 재실행된다(같은 내용 재렌더에선 스크롤 위치 보존).
    - DOM 교체 직후엔 래퍼가 아직 안 자랐을 수 있어 짧게 폴링(80ms × 10회).
    - `components.inject_focus_nav` 와 동일 실행 경로: st.html(unsafe_allow_javascript)
      → 구버전 Streamlit 은 iframe 폴백(window.parent). 실패는 무해(베스트에포트).
      스크립트는 정적 문자열 + 코드 내 nonce 만 포함 — 사용자/외부 데이터 미포함(XSS 무관).
    """
    if not messages:
        return
    last_sig = hash(str(messages[-1].get("content", ""))[:80]) & 0xFFFF
    nonce = f"{len(messages)}-{last_sig:x}"
    markup = (
        "<script>\n"
        f"/* chat-autoscroll {nonce} */\n"
        "(function () {\n"
        "  var doc;\n"
        "  try { doc = (window.frameElement ? window.parent : window).document; }\n"
        "  catch (err) { return; }\n"
        "  var tries = 0;\n"
        "  var t = setInterval(function () {\n"
        "    tries += 1;\n"
        "    var w = doc.querySelector('[class*=\"st-key-side_chat_scrollwrap\"]');\n"
        "    if (w && w.scrollHeight > w.clientHeight) {\n"
        "      w.scrollTop = w.scrollHeight;\n"
        "      clearInterval(t);\n"
        "      return;\n"
        "    }\n"
        "    if (tries > 10) { clearInterval(t); }\n"
        "  }, 80);\n"
        "})();\n"
        "</script>"
    )
    try:
        try:
            st.html(markup, unsafe_allow_javascript=True)
        except TypeError:  # Streamlit <1.58 — st.html 에 JS 플래그 없음
            import streamlit.components.v1 as _stc

            _stc.html(markup, height=0)
    except Exception:  # noqa: BLE001 — 스크롤 보조 실패가 채팅을 깨면 안 됨
        pass


def _render_chat_suggestions(area_key: str, input_key: str) -> None:
    """추천 질문 칩(안내 바로 밑, 상단). 칩 클릭 = **즉시 전송**.

    직전엔 칩이 입력창에 텍스트만 채워 사용자가 [보내기]를 한 번 더 눌러야 했다
    → 칩 클릭이 곧바로 `_do_sola_send` pending 을 세팅해 form 전송과 동일 경로
    (`consume_send_if_any`)로 LLM 호출까지 수행한다(on_click 미사용).
    rerun scope 는 form 전송과 동일 분기 — 일반 area 는 fragment(채팅 컬럼만),
    SOLA 작업실은 app(중앙 작업대 캔버스가 같은 런에서 답변을 반영해야 함)."""
    sugg = _suggestions_for(area_key)
    if not sugg:
        return
    pills_key = f"{input_key}__pills"
    with st.container(key="side_chat_suggest"):
        picked = st.pills(
            "추천 질문", sugg, selection_mode="single",
            key=pills_key, label_visibility="collapsed",
        )
    if picked:
        st.session_state["_do_sola_send"] = picked
        st.session_state[f"{input_key}__reset_pills"] = True
        st.rerun(scope="app" if area_key == _SOLA_AREA else "fragment")


def _render_chat_input(input_key: str, safe_area: str, area_key: str) -> None:
    """입력 form(text_area + 보내기) — 컬럼 하단 고정(streamlit-overrides.css 가
    margin-top:auto 로 핀). 제출 시 `_do_sola_send` pending → rerun → consume.

    rerun scope 분기:
      - 일반 area: scope="fragment" — fragment rerun 최상단의
        `consume_send_if_any(scope="fragment")` 가 처리 → 채팅 컬럼만 갱신.
      - SOLA 작업실: scope="app" — 중앙 작업대 캔버스('현재 산출물' = 마지막
        assistant 메시지)가 답변을 같은 런에서 반영해야 하므로 전체 rerun 으로
        승격, app.py 최상단 consume 가 본문 렌더 **전에** 처리한다.
    """
    with st.container(key="side_chat_inputbar"):
        with st.form(key=f"_side_chat_form_{safe_area}", clear_on_submit=True):
            user_input = st.text_area(
                "SOLA 에게 질문", key=input_key,
                placeholder="이 화면에 대해 무엇이든 물어보세요…",
                label_visibility="collapsed", height=120,
            )
            sent = st.form_submit_button("➤ 보내기", use_container_width=True)
    if sent and user_input and user_input.strip():
        st.session_state["_do_sola_send"] = user_input.strip()
        st.rerun(scope="app" if area_key == _SOLA_AREA else "fragment")


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


def consume_send_if_any(persona: Persona, *, scope: str = "app") -> None:
    """글로벌 채팅 전송 핸들러 — `_do_sola_send` pending → LLM → append → rerun.

    호출 지점 2곳 (같은 pending 키를 pop 하므로 이중 처리는 구조적으로 불가):
      1. **app.py 최상단** (scope="app", 기본) — SOLA 작업실 form 전송과 인계 자동
         전송(`sw._consume_prefill_ask_if_any`)처럼 **앱 전체 rerun 으로 도착하는**
         send 를 본문 렌더 전에 처리한다. 작업실 중앙 캔버스('현재 산출물' =
         마지막 assistant 메시지)가 같은 런에서 답변을 반영하려면 필수.
      2. **`_render_side_fragment` 최상단** (scope="fragment") — 그 외 area 의
         form 전송을 채팅 컬럼 부분 rerun 안에서 처리(앱 전체 재실행 없음).

    sw._consume_send_if_any 위임을 풀고 같은 빌딩블록(_append_message /
    _load_messages / _build_llm_messages)으로 재구성한 이유: sw 버전은 끝에서
    `st.rerun()`(전체 rerun)을 고정 호출해 fragment 부분 rerun 을 깨기 때문.
    화면 컨텍스트는 `sw._build_llm_messages` 가 session_state 의
    `_chat_context_for_sola`(직전 풀런에서 각 화면이 저장)를 읽어 첨부한다.

    오류는 assistant 메시지로 노출(UX 단절 방지), LLM 미설정은 `sola.preview`
    미리보기로 폴백 — sw._consume_send_if_any 와 동일 정책.
    """
    payload = st.session_state.pop("_do_sola_send", None)
    if not payload:
        return
    user_text = str(payload).strip()
    if not user_text:
        return

    from ui import sola_workshop_v2 as sw

    sw._append_message("user", user_text)
    msgs = sw._load_messages()
    llm_messages = sw._build_llm_messages(persona, msgs)

    try:
        with st.spinner("SOLA 가 답변을 작성하고 있어요…"):
            answer = sola_client.chat(llm_messages)
        sw._append_message("assistant", answer)
    except sola_client.LLMNotConfigured:
        preview = format_messages_preview(
            llm_messages,
            header="ℹ️ LLM 미설정 — 아래는 실제로 전달될 입력 컨텍스트입니다.",
            footer_hint=True,
        )
        sw._append_message("assistant", preview)
    except Exception as exc:
        sw._append_message("assistant", f"⚠️ 응답 생성 실패: {type(exc).__name__}: {exc}")
    st.rerun(scope=scope)  # type: ignore[arg-type]
