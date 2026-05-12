"""전역 CSS 주입 헬퍼."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from config import ASSETS_DIR


def inject_global_styles() -> None:
    css_path = ASSETS_DIR / "styles.css"
    if not css_path.exists():
        return
    st.markdown(f"<style>{Path(css_path).read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def page_header(title: str, sub: str = "") -> None:
    import html as _html

    st.markdown(
        f"""
        <div class="header-wrap">
            <span class="header-logo">{_html.escape(title)}</span>
            <span class="header-sub">{_html.escape(sub)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
