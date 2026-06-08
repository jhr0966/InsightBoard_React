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


# ── 출처 탭 수집 카운트 환산 (무수집 버그 회귀 방지) ─────────────

def test_src_count_map_rolls_scraper_sources_into_display_names():
    """수집기 저장값(naver/google/tech+press)을 출처 탭 표시명으로 환산.

    표시명으로 곧장 group 하면 기본 출처 4개가 전부 '무수집'으로 보이던 버그 회귀 방지.
    """
    from ui import data_management_v2 as dm
    df = pd.DataFrame({
        "source": ["naver", "google", "tech", "tech", "조선해양 e뉴스"],
        "press":  ["",       "",       "AI Times", "오토메이션월드", ""],
        "title":  ["a", "b", "c", "d", "e"],
        "link":   ["1", "2", "3", "4", "5"],
        "collected_at": ["2026-06-08T01:00:00Z"] * 5,
    })
    with patch.object(dm._news_db, "load_news_for_days", return_value=df):
        m = dm._src_count_map()
    assert m["네이버 기술"][0] == 1
    assert m["Google RSS"][0] == 1
    assert m["AI Times"][0] == 1
    assert m["오토메이션월드"][0] == 1
    assert m["조선해양 e뉴스"][0] == 1          # 커스텀/기타는 원시 source 값 그대로
    # 원시 수집 ID(naver/google/tech)가 '기타'로 누출되지 않음
    assert "naver" not in m and "google" not in m and "tech" not in m


def test_src_count_map_recognizes_legacy_direct_source_names():
    """legacy: source 에 표시명이 직접 저장된 데이터(예: source='AI Times')도 인식."""
    from ui import data_management_v2 as dm
    df = pd.DataFrame({
        "source": ["AI Times", "google", "naver"],
        "press":  ["", "", ""],
        "title":  ["a", "b", "c"], "link": ["1", "2", "3"],
        "collected_at": ["2026-06-08T01:00:00Z"] * 3,
    })
    with patch.object(dm._news_db, "load_news_for_days", return_value=df):
        m = dm._src_count_map()
    assert m["AI Times"][0] == 1
    assert m["Google RSS"][0] == 1
    assert m["네이버 기술"][0] == 1
    assert set(m) == set(dm._DEFAULT_SOURCE_MATCH)   # 기타 누출 없음(rest 비어 있음)


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


# ── 출처 행 위젯 — pill HTML(시각) + 토글/제거 버튼(위젯) ──────
# 구 _dm_src_body_html(앵커 토글 링크)는 _render_src_table(위젯)로 교체.
# pill HTML 은 순수 함수라 직접 검증, 토글/제거는 _do_src_action pending 경로로 검증.

def test_src_row_pill_shows_name_status_without_anchor():
    from ui import data_management_v2 as dm
    html = dm._src_row_pill_html("AI Times", 5, "2026-06-05T01:00",
                                 is_enabled=True, kind="default")
    assert "AI Times" in html
    assert "dm-src-st-ok" in html        # 7일 수집 있음 = OK
    assert "dm-src-rowp" in html
    assert "<a " not in html             # 앵커 없음 — 토글은 위젯 버튼이 담당


def test_src_row_pill_off_and_custom_variants():
    from ui import data_management_v2 as dm
    off = dm._src_row_pill_html("네이버", 0, "", is_enabled=False, kind="default")
    assert "dm-src-st-off" in off and "비활성" in off and "dm-src-rowp-off" in off
    cust = dm._src_row_pill_html("MyFeed", 2, "", is_enabled=True,
                                 kind="custom", url="https://my.feed/rss")
    assert "dm-src-rowp-custom" in cust
    assert "https://my.feed/rss" in cust and "MyFeed" in cust


def test_src_header_html_shows_active_count():
    from ui import data_management_v2 as dm
    assert "활성 출처 3개" in dm._src_header_html(3)


def test_src_action_via_pending_toggles_default(isolated_sources):
    """행 토글 버튼이 세팅하는 _do_src_action pending → 활성/비활성 전환."""
    from ui import data_management_v2 as dm
    import streamlit as st
    st.session_state.pop("_do_src_action", None)
    st.session_state["_do_src_action"] = ("toggle", "AI Times")
    result = dm._consume_src_action_if_any()
    assert result == ("toggle", "AI Times")
    toast = st.session_state.get("_src_action_toast")
    assert toast and toast[0] == "ok"
    assert "AI Times" in isolated_sources.disabled_set()  # 실제 비활성됨
    assert "_do_src_action" not in st.session_state        # 1회 소비


def test_src_action_via_pending_removes_custom(isolated_sources):
    from ui import data_management_v2 as dm
    import streamlit as st
    isolated_sources.add_custom("MyFeed", "https://my.feed/rss")
    st.session_state["_do_src_action"] = ("remove", "MyFeed")
    result = dm._consume_src_action_if_any()
    assert result == ("remove", "MyFeed")
    assert all(c.name != "MyFeed" for c in isolated_sources.custom_sources())
