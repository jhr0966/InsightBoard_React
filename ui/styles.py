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
    "v2/scale.css",
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


def inject_screen_css(name: str) -> None:
    """화면별 CSS 로드 — `assets/v2/screens/<name>.css` 가 있으면 inject.

    글로벌이 아닌 화면 전용 스타일(예: 보드 화면의 .db-greet/.db-stories 등)
    을 화면 진입 시 한 번 주입한다. 같은 화면에 머무는 동안 매 rerun 마다
    재주입되지만 브라우저가 같은 텍스트를 중복 적용해도 시각적 변화는 없음.

    ⚠️ 알려진 이슈 (2026-06): 이 `st.html("<style>")` 가 mid-render 에서
    실제 DOM 에 주입되지 않는 경우가 확인됨 (전역 `inject_global_styles`
    는 정상). 즉 screen CSS 클래스(.dm-*/.td-* 등)가 적용 안 될 수 있음.
    동적 `st.html` 콘텐츠는 inline style 을 병행하는 게 안전 (예: PR-5
    diff 미리보기, 작업 정의 관리 UI). 근본 수정은 별도 작업. → MILESTONE_1.md §3
    """
    path = ASSETS_DIR / "v2" / "screens" / f"{name}.css"
    if not path.exists():
        return
    st.html(f"<style>{path.read_text(encoding='utf-8')}</style>")


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
