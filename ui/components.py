"""Reusable HTML component builders for the Streamlit UI.

The helpers return escaped HTML strings so callers can render them via
`st.markdown(..., unsafe_allow_html=True)` without duplicating markup.
"""
from __future__ import annotations

import html as _html
from collections.abc import Iterable

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
    """Build a compact KPI card with a large value and optional caption."""
    return f"""
    <div class="metric-card{_tone_class(tone)}">
      <div class="metric-card-top">
        {f'<span class="metric-card-icon">{_html.escape(icon)}</span>' if icon else ''}
        <span class="metric-card-label">{_html.escape(label)}</span>
      </div>
      <div class="metric-card-value">{_html.escape(str(value))}</div>
      {f'<div class="metric-card-caption">{_html.escape(caption)}</div>' if caption else ''}
    </div>
    """


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
    return f"""
    <div class="status-card{_tone_class(status)}">
      <div class="status-card-icon">{_html.escape(icon or '•')}</div>
      <div>
        <div class="status-card-title">{_html.escape(title)}</div>
        <div class="status-card-body">{_html.escape(body)}</div>
      </div>
    </div>
    """


def action_card(icon: str, title: str, body: str, *, tone: str = "") -> str:
    """Build one quick-action card."""
    return f"""
    <div class="action-card{_tone_class(tone)}">
      <div class="action-card-icon">{_html.escape(icon)}</div>
      <div class="action-card-title">{_html.escape(title)}</div>
      <div class="action-card-body">{_html.escape(body)}</div>
    </div>
    """


def action_grid(cards: Iterable[str]) -> str:
    """Wrap prebuilt action cards in the standard responsive action grid."""
    return '<div class="action-grid">' + "".join(cards) + "</div>"

def step_item(number: str | int, title: str, body: str, *, active: bool = False) -> str:
    """Build one process step for guided workflows."""
    cls = "step-item active" if active else "step-item"
    return f"""
    <div class="{cls}">
      <div class="step-number">{_html.escape(str(number))}</div>
      <div>
        <div class="step-title">{_html.escape(title)}</div>
        <div class="step-body">{_html.escape(body)}</div>
      </div>
    </div>
    """


def step_guide(items: Iterable[str]) -> str:
    """Wrap prebuilt step items in the standard horizontal guide."""
    return '<div class="step-guide">' + "".join(items) + "</div>"
