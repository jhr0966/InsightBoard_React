"""자동화 기회 카드 보류/채택 wire — URL 빌더 + 1회-소비 + bookmark 추가."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture
def isolated_bookmarks(tmp_path, monkeypatch):
    """bookmarks 임시 디렉토리 격리."""
    bookmarks_dir = tmp_path / "bookmarks"
    bookmarks_dir.mkdir(parents=True, exist_ok=True)
    from store import bookmarks as bm
    monkeypatch.setattr(bm, "_path", lambda: bookmarks_dir / "items.jsonl")
    import streamlit as st
    for k in ["_opp_action_toast"]:
        st.session_state.pop(k, None)
    yield bm


# ── URL 빌더 ────────────────────────────────────────────────

def test_opp_action_href_encodes_payload():
    from ui import board_v2
    href = board_v2._opp_action_href("accept", dept="도장 1팀", lv3="비전 검사", title="T")
    # area + opp_action + dept + lv3 + title
    assert "app_area=" in href
    assert "opp_action=accept" in href
    assert "dept=" in href
    assert "lv3=" in href
    assert "title=" in href


def test_opp_action_href_omits_empty_title():
    from ui import board_v2
    href = board_v2._opp_action_href("hold", dept="도장", lv3="비전")
    assert "title=" not in href
    assert "opp_action=hold" in href


# ── consume_opp_action_if_any — 1회 소비 + bookmark 추가 ─────

def test_consume_opp_action_accept_creates_adopted_bookmark(isolated_bookmarks):
    from ui import board_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["opp_action"] = "accept"
    st.query_params["dept"] = "도장1팀"
    st.query_params["lv3"] = "비전 검사"
    st.query_params["title"] = "도장1팀 · 비전 검사 자동화 기회"

    result = board_v2.consume_opp_action_if_any()
    assert result == ("accept", "도장1팀", "비전 검사")

    # bookmark 추가됨
    items = isolated_bookmarks.list_all(type_="proposal")
    assert len(items) == 1
    bm = items[0]
    assert bm.status == "adopted"
    assert "도장1팀 · 비전 검사" in bm.title
    assert "도장1팀" in bm.tags
    assert "비전 검사" in bm.tags

    # toast set
    toast = st.session_state.get("_opp_action_toast")
    assert toast and toast[0] == "ok"
    assert "채택" in toast[1]

    # query 정리
    for k in ("opp_action", "dept", "lv3", "title"):
        assert k not in st.query_params


def test_consume_opp_action_hold_creates_pending_bookmark(isolated_bookmarks):
    from ui import board_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["opp_action"] = "hold"
    st.query_params["dept"] = "용접"
    st.query_params["lv3"] = "비드 검사"

    board_v2.consume_opp_action_if_any()
    items = isolated_bookmarks.list_all(type_="proposal")
    assert len(items) == 1
    assert items[0].status == "pending"
    toast = st.session_state.get("_opp_action_toast")
    assert toast and toast[0] == "ok"
    assert "보류" in toast[1]


def test_consume_opp_action_noop_when_missing(isolated_bookmarks):
    from ui import board_v2
    import streamlit as st

    st.query_params.clear()
    assert board_v2.consume_opp_action_if_any() is None
    assert isolated_bookmarks.list_all(type_="proposal") == []


def test_consume_opp_action_noop_for_unknown_action(isolated_bookmarks):
    """알 수 없는 action 은 무시 + query 유지(디버깅 용)."""
    from ui import board_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["opp_action"] = "nuke"
    st.query_params["dept"] = "X"
    st.query_params["lv3"] = "Y"
    try:
        assert board_v2.consume_opp_action_if_any() is None
        assert isolated_bookmarks.list_all(type_="proposal") == []
        # query 유지
        assert st.query_params.get("opp_action") == "nuke"
    finally:
        st.query_params.clear()


def test_consume_opp_action_default_title_when_missing(isolated_bookmarks):
    """title 없으면 dept · lv3 자동화 기회 로 자동 채움."""
    from ui import board_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["opp_action"] = "accept"
    st.query_params["dept"] = "도장"
    st.query_params["lv3"] = "비전"

    board_v2.consume_opp_action_if_any()
    items = isolated_bookmarks.list_all(type_="proposal")
    assert len(items) == 1
    assert items[0].title == "도장 · 비전 자동화 기회"


# ── 카드 HTML 변경 검증 ─────────────────────────────────────

def test_opp_card_renders_a_hrefs_for_hold_and_accept():
    from ui import board_v2

    row = pd.Series({
        "dept": "도장", "lv3": "비전 검사", "cell_score": 95.0,
        "matched_news": 40, "matched_tasks": 18,
        "sample_tasks": "AI 도막 검사", "sample_news": "",
        "sample_objectives": "",
    })
    html = board_v2._opp_card_html(row)
    # 보류/채택 모두 <a> 로 렌더
    assert 'class="db-prop-hold" href="' in html
    assert 'class="db-prop-accept" href="' in html
    # disabled 자취 없음
    assert '<button class="db-prop-hold"' not in html
    assert '<button class="db-prop-accept"' not in html
    # URL payload
    assert "opp_action=hold" in html
    assert "opp_action=accept" in html


# ── toast 렌더 ──────────────────────────────────────────────

def test_opp_action_toast_renders_and_clears_session_state():
    from ui import board_v2
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state["_opp_action_toast"] = ("ok", "✅ 채택 완료")
        board_v2.render_opp_action_toast_if_needed()
    assert captured and "채택 완료" in captured[0]
    assert "_opp_action_toast" not in st.session_state


def test_opp_action_toast_noop_when_empty():
    from ui import board_v2
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state.pop("_opp_action_toast", None)
        board_v2.render_opp_action_toast_if_needed()
    assert captured == []
