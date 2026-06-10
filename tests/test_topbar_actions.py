"""topbar 알림/설정 버튼 정직화 — disabled no-op → 실제 <a> 동작."""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ── _notif_count ────────────────────────────────────────────

def test_notif_count_reads_pending_from_bookmarks():
    from ui import app_shell
    app_shell._notif_count.clear()          # 60s 캐시 — 테스트 격리
    fake_summary = {"proposal_status": {"pending": 3, "adopted": 1}}
    with patch("store.bookmarks.summary_counts", return_value=fake_summary):
        assert app_shell._notif_count() == 3


def test_notif_count_zero_when_no_pending():
    from ui import app_shell
    app_shell._notif_count.clear()          # 60s 캐시 — 테스트 격리
    fake_summary = {"proposal_status": {"adopted": 2}}
    with patch("store.bookmarks.summary_counts", return_value=fake_summary):
        assert app_shell._notif_count() == 0


def test_notif_count_zero_on_exception():
    from ui import app_shell
    with patch("store.bookmarks.summary_counts", side_effect=RuntimeError("boom")):
        assert app_shell._notif_count() == 0


# ── render_topbar — 버튼이 <a> 로 정직화 ────────────────────

def _render_capture(notif: int) -> str:
    """render_topbar 1회 렌더 후 st.html 로 넘어간 마크업 반환."""
    from ui import app_shell
    captured: list[str] = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)), \
         patch.object(app_shell, "_notif_count", return_value=notif), \
         patch.object(app_shell, "_get_persona", return_value=__import__(
             "persona.schema", fromlist=["Persona"]).Persona(name="홍길동")):
        app_shell.render_topbar(page_title="오늘의 보드")
    assert captured
    return captured[0]


def test_topbar_buttons_are_anchors_not_disabled():
    html = _render_capture(notif=0)
    # 알림/설정 모두 <a class="db-hdr-btn">
    assert html.count('class="db-hdr-btn"') == 2
    # disabled no-op 자취 없음
    assert "db-hdr-btn" in html
    assert "disabled" not in html


def test_topbar_notif_links_to_archive():
    html = _render_capture(notif=0)
    # 알림 → 산출물 보관함 (URL 인코딩된 app_area)
    assert "app_area=%F0%9F%93%A6" in html  # 📦
    # 설정 → persona_editor
    assert "?persona_editor=1" in html


def test_topbar_notif_dot_and_badge_only_when_pending():
    html_with = _render_capture(notif=4)
    assert 'class="db-hdr-dot"' in html_with
    assert 'class="db-hdr-badge"' in html_with
    assert ">4<" in html_with
    # 툴팁에 개수 노출
    assert "채택 대기 4건" in html_with


def test_topbar_no_dot_when_zero_pending():
    html_zero = _render_capture(notif=0)
    assert 'class="db-hdr-dot"' not in html_zero
    assert 'class="db-hdr-badge"' not in html_zero
    assert "새 알림 없음" in html_zero


def test_topbar_badge_caps_at_99plus():
    html = _render_capture(notif=150)
    assert "99+" in html
