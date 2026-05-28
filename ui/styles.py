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
    "v2/streamlit-overrides.css",
)


def inject_global_styles() -> None:
    """Inject v2 design tokens + Streamlit overrides + legacy styles.

    순서 중요: tokens → card(components) → shell(v2 topbar) → streamlit overrides
    → legacy styles.css (점진 제거 대상, 마지막에 로드해 v2 토큰을 못 덮어쓰게 함).
    """
    parts: list[str] = []
    for rel in _V2_CSS_FILES:
        path = ASSETS_DIR / rel
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    legacy = ASSETS_DIR / "styles.css"
    if legacy.exists():
        parts.append(legacy.read_text(encoding="utf-8"))
    if not parts:
        return
    st.html("<style>" + "\n".join(parts) + "</style>")


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
