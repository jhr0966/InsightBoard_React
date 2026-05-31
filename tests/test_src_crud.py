"""출처 설정 CRUD wire — 기본 출처 토글 + 커스텀 RSS 추가/제거."""
from __future__ import annotations

from unittest.mock import patch
from urllib.parse import quote

import pandas as pd
import pytest


@pytest.fixture
def isolated_sources(tmp_path, monkeypatch):
    """store/sources 의 config.json 을 임시 디렉토리로 격리."""
    cfg_dir = tmp_path / "sources"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    from store import sources as src_store
    monkeypatch.setattr(src_store, "_config_path",
                        lambda: cfg_dir / "config.json")
    import streamlit as st
    for k in ("_src_action_toast", "_do_src_add"):
        st.session_state.pop(k, None)
    yield src_store


# ── store/sources.py 단위 ─────────────────────────────────

def test_disabled_set_default_empty(isolated_sources):
    assert isolated_sources.disabled_set() == frozenset()


def test_toggle_disabled_default_source(isolated_sources):
    s = isolated_sources
    # 첫 토글 → 비활성
    assert s.toggle_disabled("AI Times") is False
    assert "AI Times" in s.disabled_set()
    # 다시 토글 → 활성
    assert s.toggle_disabled("AI Times") is True
    assert "AI Times" not in s.disabled_set()


def test_toggle_unknown_source_returns_false(isolated_sources):
    s = isolated_sources
    assert s.toggle_disabled("없는출처") is False
    assert s.disabled_set() == frozenset()


def test_add_custom_basic(isolated_sources):
    s = isolated_sources
    cs = s.add_custom("조선해양 e뉴스", "https://example.com/rss")
    assert cs.name == "조선해양 e뉴스"
    assert cs.url == "https://example.com/rss"
    assert cs.added_at
    items = s.custom_sources()
    assert len(items) == 1 and items[0].name == "조선해양 e뉴스"


def test_add_custom_rejects_empty_or_bad_url(isolated_sources):
    s = isolated_sources
    with pytest.raises(ValueError):
        s.add_custom("", "https://x.com")
    with pytest.raises(ValueError):
        s.add_custom("X", "")
    with pytest.raises(ValueError):
        s.add_custom("X", "ftp://nope.com")  # http(s) 만
    with pytest.raises(ValueError):
        s.add_custom("AI Times", "https://x.com")  # 기본 출처 이름 충돌


def test_add_custom_rejects_duplicate(isolated_sources):
    s = isolated_sources
    s.add_custom("X", "https://x.com")
    with pytest.raises(ValueError):
        s.add_custom("X", "https://other.com")


def test_remove_custom(isolated_sources):
    s = isolated_sources
    s.add_custom("X", "https://x.com")
    assert s.remove_custom("X") is True
    assert s.custom_sources() == []
    # 다시 제거 → False
    assert s.remove_custom("X") is False


def test_all_active_combines_defaults_and_custom(isolated_sources):
    s = isolated_sources
    s.toggle_disabled("AI Times")  # 비활성
    s.add_custom("X", "https://x.com")
    active = s.all_active()
    assert "AI Times" not in active
    assert "오토메이션월드" in active
    assert "X" in active


# ── URL 빌더 ───────────────────────────────────────────────

def test_src_action_href_includes_dm_tab_src_and_name():
    from ui import data_management_v2 as dm
    href = dm._src_action_href("toggle", "AI Times")
    assert "dm_tab=src" in href
    assert "src_action=toggle" in href
    assert "src_name=" + quote("AI Times") in href


# ── _consume_src_action_if_any ─────────────────────────────

def test_consume_toggle_disables_and_emits_toast(isolated_sources):
    from ui import data_management_v2 as dm
    import streamlit as st
    st.query_params.clear()
    st.query_params["src_action"] = "toggle"
    st.query_params["src_name"] = "AI Times"

    result = dm._consume_src_action_if_any()
    assert result == ("toggle", "AI Times")
    assert "AI Times" in isolated_sources.disabled_set()
    toast = st.session_state.get("_src_action_toast")
    assert toast and toast[0] == "ok" and "비활성" in toast[1]
    # query 정리
    assert "src_action" not in st.query_params
    assert "src_name" not in st.query_params


def test_consume_remove_custom(isolated_sources):
    from ui import data_management_v2 as dm
    import streamlit as st
    isolated_sources.add_custom("MyRSS", "https://my.rss")

    st.query_params.clear()
    st.query_params["src_action"] = "remove"
    st.query_params["src_name"] = "MyRSS"
    dm._consume_src_action_if_any()
    assert isolated_sources.custom_sources() == []
    toast = st.session_state.get("_src_action_toast")
    assert toast and "제거" in toast[1]


def test_consume_noop_for_unknown_action(isolated_sources):
    from ui import data_management_v2 as dm
    import streamlit as st
    st.query_params.clear()
    st.query_params["src_action"] = "nuke"
    st.query_params["src_name"] = "AI Times"
    try:
        assert dm._consume_src_action_if_any() is None
        assert isolated_sources.disabled_set() == frozenset()
        # query 유지(디버깅)
        assert st.query_params.get("src_action") == "nuke"
    finally:
        st.query_params.clear()


def test_consume_noop_when_missing(isolated_sources):
    from ui import data_management_v2 as dm
    import streamlit as st
    st.query_params.clear()
    assert dm._consume_src_action_if_any() is None


# ── _consume_src_add_if_any ─────────────────────────────

def test_consume_src_add_success(isolated_sources):
    from ui import data_management_v2 as dm
    import streamlit as st
    st.session_state["_do_src_add"] = ("MyFeed", "https://example.com/rss")
    dm._consume_src_add_if_any()
    customs = isolated_sources.custom_sources()
    assert len(customs) == 1 and customs[0].name == "MyFeed"
    toast = st.session_state.get("_src_action_toast")
    assert toast and "등록" in toast[1]


def test_consume_src_add_error_emits_error_toast(isolated_sources):
    from ui import data_management_v2 as dm
    import streamlit as st
    st.session_state["_do_src_add"] = ("", "https://x")
    dm._consume_src_add_if_any()
    toast = st.session_state.get("_src_action_toast")
    assert toast and toast[0] == "error"


# ── _dm_src_body_html — 토글 링크 + 커스텀 노출 ────────────

def test_src_body_renders_toggle_links_for_defaults(isolated_sources):
    from ui import data_management_v2 as dm
    with patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()):
        html = dm._dm_src_body_html({"active_sources": 4})
    # 4개 기본 출처 모두 노출 + 비활성화 링크
    assert html.count("dm-src-act") >= 4
    assert "비활성화" in html
    # disabled 자취 없음 (이전 PR 의 잔여)
    assert 'class="dm-src-row"' not in html or "disabled>" not in html


def test_src_body_disabled_row_shows_off_label(isolated_sources):
    from ui import data_management_v2 as dm
    isolated_sources.toggle_disabled("AI Times")  # 비활성
    with patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()):
        html = dm._dm_src_body_html({"active_sources": 3})
    # 비활성 상태 표시
    assert "dm-src-st-off" in html
    assert "비활성" in html
    # 토글 라벨이 "활성화" 로
    assert "활성화" in html
    # 활성 출처 카운트는 3
    assert "활성 출처 3개" in html


def test_src_body_includes_custom_rows_with_remove(isolated_sources):
    from ui import data_management_v2 as dm
    isolated_sources.add_custom("MyFeed", "https://my.feed/rss")
    with patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()):
        html = dm._dm_src_body_html({"active_sources": 5})
    assert "MyFeed" in html
    assert "dm-src-row-custom" in html
    assert "https://my.feed/rss" in html
    # 제거 링크
    assert "dm-src-act-rm" in html
    assert "제거" in html
    # 5 = 4 기본 + 1 커스텀
    assert "활성 출처 5개" in html
