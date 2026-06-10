"""Reusable HTML component builders for the Streamlit UI.

The helpers return escaped HTML strings. Use `render_html(...)` to render
them through Streamlit's native HTML element instead of Markdown escaping.
"""
from __future__ import annotations

import html as _html
import re as _re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote as _quote

import streamlit as st


_SVG_DATAURI_RE = _re.compile(r"data:image/svg\+xml;utf8,(<svg.*?</svg>)", _re.DOTALL)
_SVG_INLINE_RE = _re.compile(r"(<svg\b[^>]*>).*?</svg>", _re.DOTALL)


@st.cache_data(show_spinner=False)
def _read_asset_cached(path_str: str, mtime_ns: int) -> str:
    return Path(path_str).read_text(encoding="utf-8")


def read_asset_text(path: Path) -> str:
    """자산(CSS/HTML 템플릿) 텍스트 — (경로, mtime) 키 캐시.

    CSS 6종·화면 템플릿을 **매 rerun 디스크에서 다시 읽던** 것을 제거. 파일을 수정하면
    mtime 변경으로 자동 재읽기되므로 개발 중 핫리로드도 그대로 동작. 없으면 빈 문자열.
    """
    try:
        return _read_asset_cached(str(path), path.stat().st_mtime_ns)
    except OSError:
        return ""


def _svg_attr(open_tag: str, name: str) -> str:
    m = _re.search(name + r"""\s*=\s*(['"])(.*?)\1""", open_tag, _re.DOTALL)
    return m.group(2) if m else ""


def prepare_screen_html(markup: str) -> str:
    """`st.html` 의 두 SVG 함정을 보정해 모든 화면의 아이콘/차트가 렌더되게 한다.

    1) ``data:image/svg+xml;utf8,<svg ... fill='#2563EB'>`` (미인코딩 data-URI) —
       색상값의 ``#`` 와 공백이 URL fragment/구분자로 잘려 이미지가 **깨진다** →
       URL 인코딩 data-URI 로 재작성.
    2) 인라인 ``<svg>...</svg>`` — `st.html` 의 sanitizer 가 통째로 **제거한다** →
       class/style/width/height 를 보존한 ``<img>``(인코딩 data-URI)로 래핑.

    템플릿 HTML 을 `st.html` 로 렌더하기 직전 한 번 통과시킨다.
    """
    if not markup or "svg" not in markup:
        return markup
    # 1) data-URI 재인코딩 (먼저 — 이후 인라인 변환이 src 안 <svg> 를 건드리지 않게)
    markup = _SVG_DATAURI_RE.sub(
        lambda m: "data:image/svg+xml," + _quote(m.group(1), safe=""),
        markup,
    )

    # 2) 남은 인라인 <svg> → <img>
    def _to_img(m: "_re.Match[str]") -> str:
        full = m.group(0)
        open_tag = m.group(1)
        attrs = ""
        for name in ("class", "style", "width", "height"):
            val = _svg_attr(open_tag, name)
            if val:
                attrs += f' {name}="{val.replace(chr(34), "&quot;")}"'
        return f'<img src="data:image/svg+xml,{_quote(full, safe="")}"{attrs} alt="" />'

    return _SVG_INLINE_RE.sub(_to_img, markup)


def render_screen_html(markup: str) -> None:
    """`prepare_screen_html` 통과 후 `st.html` 렌더 — 화면 템플릿 전용 안전 진입점."""
    st.html(prepare_screen_html(markup))


def render_html(markup: str, **_ignored) -> None:
    """Render trusted component HTML without Markdown escaping.

    Streamlit's `st.markdown(..., unsafe_allow_html=True)` can be easy to miss
    and then raw `<div>...</div>` appears in the app. Centralizing rendering via
    `st.html` makes component output consistent across pages.
    """
    st.html(markup)


_ALLOWED_TONES = {"", "info", "ok", "warn", "danger", "teal"}


def _tone_class(tone: str) -> str:
    safe = tone if tone in _ALLOWED_TONES else ""
    return f" {safe}" if safe else ""


def metric_card(
    label: str,
    value: str | int,
    *,
    caption: str = "",
    icon: str = "",
    tone: str = "",
) -> str:
    """Build a compact KPI card with a large value and optional caption.

    Output starts at column 0 so that Markdown won't mistakenly treat the
    HTML as an indented code block if it ever reaches `st.markdown`.
    """
    icon_html = (
        f'<span class="metric-card-icon">{_html.escape(icon)}</span>' if icon else ""
    )
    caption_html = (
        f'<div class="metric-card-caption">{_html.escape(caption)}</div>'
        if caption else ""
    )
    return (
        f'<div class="metric-card{_tone_class(tone)}">'
        f'<div class="metric-card-top">{icon_html}'
        f'<span class="metric-card-label">{_html.escape(label)}</span>'
        f'</div>'
        f'<div class="metric-card-value">{_html.escape(str(value))}</div>'
        f'{caption_html}'
        f'</div>'
    )


def metric_grid(cards: Iterable[str]) -> str:
    """Wrap prebuilt metric cards in the standard responsive metric grid."""
    return '<div class="metric-grid">' + "".join(cards) + "</div>"


def status_card(
    title: str,
    body: str,
    *,
    status: str = "info",
    icon: str = "",
) -> str:
    """Build a status/empty-state card with a colored leading rail."""
    return (
        f'<div class="status-card{_tone_class(status)}">'
        f'<div class="status-card-icon">{_html.escape(icon or "•")}</div>'
        f'<div>'
        f'<div class="status-card-title">{_html.escape(title)}</div>'
        f'<div class="status-card-body">{_html.escape(body)}</div>'
        f'</div>'
        f'</div>'
    )


def action_card(icon: str, title: str, body: str, *, tone: str = "") -> str:
    """Build one quick-action card."""
    return (
        f'<div class="action-card{_tone_class(tone)}">'
        f'<div class="action-card-icon">{_html.escape(icon)}</div>'
        f'<div class="action-card-title">{_html.escape(title)}</div>'
        f'<div class="action-card-body">{_html.escape(body)}</div>'
        f'</div>'
    )


def action_grid(cards: Iterable[str]) -> str:
    """Wrap prebuilt action cards in the standard responsive action grid."""
    return '<div class="action-grid">' + "".join(cards) + "</div>"


def step_item(number: str | int, title: str, body: str, *, active: bool = False) -> str:
    """Build one process step for guided workflows."""
    cls = "step-item active" if active else "step-item"
    return (
        f'<div class="{cls}">'
        f'<div class="step-number">{_html.escape(str(number))}</div>'
        f'<div>'
        f'<div class="step-title">{_html.escape(title)}</div>'
        f'<div class="step-body">{_html.escape(body)}</div>'
        f'</div>'
        f'</div>'
    )


def step_guide(items: Iterable[str]) -> str:
    """Wrap prebuilt step items in the standard horizontal guide."""
    return '<div class="step-guide">' + "".join(items) + "</div>"
