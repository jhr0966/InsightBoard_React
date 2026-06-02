"""전역 CSS 주입 + 페이지 헤더 헬퍼."""
from __future__ import annotations

import html as _html
from pathlib import Path

import streamlit as st

from config import ASSETS_DIR
from sola.client import is_configured


_V2_CSS_FILES = (
    "v2/tokens.css",
    "v2/card.css",
    "v2/shell.css",
    "v2/sidebar.css",
    "v2/streamlit-overrides.css",
    "v2/scale.css",
)


def inject_global_styles() -> None:
    """Inject v2 design tokens + Streamlit overrides + legacy styles.

    순서: tokens → card(components) → shell(v2 topbar) → sidebar(네이티브 사이드바)
    → streamlit overrides → scale.

    레거시 `assets/styles.css`(V1 디자인 시스템, 1463줄)는 더 이상 로드하지 않는다 —
    유일한 라이브 소비처였던 네이티브 사이드바 스타일을 `v2/sidebar.css` 로 이전하고,
    새로고침 시 잠깐 보이던 V1 잔재(FOUC) 를 제거 (2026-06-01).

    Streamlit `st.html("<style>")` 는 큰 `<style>` 블록을 안정적으로 mount 하지
    못함이 확인됨 (수만 자 누락). `st.markdown(unsafe_allow_html=True)` 가 다른
    코드 경로로 보존하므로 그쪽 사용 — CSS 는 자체 자산이라 escape 불필요.
    """
    parts: list[str] = []
    for rel in _V2_CSS_FILES:
        path = ASSETS_DIR / rel
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    if not parts:
        return
    st.markdown("<style>" + "\n".join(parts) + "</style>", unsafe_allow_html=True)


def inject_screen_css(name: str) -> None:
    """화면별 CSS 로드 — `assets/v2/screens/<name>.css` 가 있으면 inject.

    글로벌이 아닌 화면 전용 스타일(예: 보드 화면의 .db-greet/.db-stories 등)
    을 화면 진입 시 한 번 주입한다. 같은 화면에 머무는 동안 매 rerun 마다
    재주입되지만 브라우저가 같은 텍스트를 중복 적용해도 시각적 변화는 없음.

    `inject_global_styles` 와 동일 — `st.markdown(unsafe_allow_html=True)` 사용
    (`st.html` 은 큰 `<style>` 블록 mount 실패).
    """
    path = ASSETS_DIR / "v2" / "screens" / f"{name}.css"
    if not path.exists():
        return
    st.markdown(
        f"<style>{path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def page_header(
    title: str,
    sub: str = "",
    *,
    chat_toggle_key: str | None = None,
    extra_chips: list[tuple[str, str]] | None = None,
) -> bool:
    """페이지 상단 모던 헤더.

    Args:
        title: 페이지 제목.
        sub: 부제목 (선택).
        chat_toggle_key: 채팅 패널 토글 키. 주어지면 우측에 💬 토글 버튼 노출.
        extra_chips: [(label, kind)] kind = "" | "ok" | "warn".

    Returns:
        채팅 패널 활성 여부 (chat_toggle_key 미지정 시 False).
    """
    safe_title = _html.escape(title)
    safe_sub = _html.escape(sub)

    chips_html = ""
    chip_pool = list(extra_chips or [])
    if chat_toggle_key is not None:
        chip_pool.insert(
            0,
            ("LLM 준비됨" if is_configured() else "LLM 미설정",
             "ok" if is_configured() else "warn"),
        )
    for label, kind in chip_pool:
        cls = f"app-header-chip {kind}".strip()
        chips_html += f'<span class="{cls}">{_html.escape(label)}</span>'

    st.html(
        f"""
        <div class="app-header">
          <div class="app-header-text">
            <div class="app-header-title">{safe_title}</div>
            {f'<div class="app-header-sub">{safe_sub}</div>' if sub else ''}
          </div>
          <div class="app-header-actions">{chips_html}</div>
        </div>
        """
    )

    if chat_toggle_key is None:
        return False

    # 채팅 토글 버튼 — Streamlit 위젯이라 HTML 헤더와 분리.
    # 디폴트는 펼친 상태 (main_and_chat 의 default_open=True 와 일치).
    open_key = f"_chat_open_{chat_toggle_key}"
    is_open = st.session_state.get(open_key, True)
    label = "💬 채팅 닫기" if is_open else "💬 이 화면에 대해 채팅"
    cols = st.columns([1, 1, 1, 1, 1])
    with cols[-1]:
        if st.button(label, key=f"_btn_chat_{chat_toggle_key}", use_container_width=True):
            st.session_state[open_key] = not is_open
            st.rerun()
    return st.session_state.get(open_key, True)


def section_label(text: str) -> None:
    """카드 그룹 위 작은 섹션 레이블."""
    st.html(f'<div class="sidebar-section">{_html.escape(text)}</div>')
