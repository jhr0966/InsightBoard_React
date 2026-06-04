"""수집 트리거 실 실행 — `?refresh=now` 가 collect_batch 호출 + 토스트."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_state():
    import streamlit as st
    st.query_params.clear()
    for k in ("_dm_refresh_toast", "persona"):
        st.session_state.pop(k, None)
    yield
    st.query_params.clear()


# ── CTA HTML — 툴팁/타이틀이 실 수집을 안내 ──────────────────

def test_refresh_cta_tooltip_mentions_collect():
    from ui import data_management_v2 as dm
    html = dm._refresh_cta_html()
    # 새 CTA 는 "캐시 무효화" 가 아니라 수집 실행을 안내
    assert "수집" in html
    assert "refresh=now" in html
    # disabled 자취 없음
    assert "disabled" not in html
    # 06:00 스케줄러 안내 문구 제거 — 이제 실제로 실행함
    assert "06:00" not in html


# ── _consume_refresh_if_any — 키워드 있음 ────────────────────

def test_refresh_calls_collect_batch_with_persona_keywords():
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport
    import streamlit as st

    st.query_params["refresh"] = "now"
    fake = CollectionReport(
        saved=[{"source": "naver", "keywords": ["비전 검사"], "count": 5, "path": "x.parquet"}],
        errors=[],
    )
    with patch("ui.board_v2._collect_keywords_for_persona",
               return_value=["비전 검사", "도장 검사"]) as mock_kw, \
         patch("scraping.run_daily.collect_batch", return_value=fake) as mock_cb:
        assert dm._consume_refresh_if_any() is True

    mock_kw.assert_called_once()
    mock_cb.assert_called_once()
    args, kwargs = mock_cb.call_args
    assert args[0] == ["비전 검사", "도장 검사"]

    toast = st.session_state.get("_dm_refresh_toast")
    assert toast[0] == "ok"
    assert "2개 키워드" in toast[1]
    assert "5건" in toast[1]


def test_refresh_includes_error_tail_when_partial_failure():
    """일부 에러 + 일부 성공 → ok 토스트에 '일부 오류 N건' 표기."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport
    import streamlit as st

    st.query_params["refresh"] = "now"
    fake = CollectionReport(
        saved=[{"source": "naver", "keywords": ["X"], "count": 3, "path": "x"}],
        errors=[{"source": "google", "keyword": "X", "error": "rate"}],
    )
    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", return_value=fake):
        dm._consume_refresh_if_any()
    toast = st.session_state.get("_dm_refresh_toast")
    assert toast[0] == "ok"
    assert "일부 오류 1건" in toast[1]


def test_refresh_error_toast_when_all_failed():
    """전부 실패(saved=[], errors=N) → error 토스트."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport
    import streamlit as st

    st.query_params["refresh"] = "now"
    fake = CollectionReport(
        saved=[],
        errors=[{"source": "naver", "keyword": "X", "error": "boom"}],
    )
    with patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", return_value=fake):
        dm._consume_refresh_if_any()
    toast = st.session_state.get("_dm_refresh_toast")
    assert toast[0] == "error"
    assert "boom" in toast[1]


# ── 페르소나 관심사 없을 때 — 기본 키워드(자동화·AI)로 폴백 ──

def test_refresh_falls_back_to_default_keywords_when_no_keywords():
    """관심사가 비어도 스킵하지 않고 기본 키워드(자동화·AI)로 collect_batch 호출."""
    from ui import data_management_v2 as dm
    from scraping.run_daily import CollectionReport
    import streamlit as st

    st.query_params["refresh"] = "now"
    fake = CollectionReport(
        saved=[{"source": "tech", "keywords": [], "count": 4, "path": "t.parquet"}],
        errors=[],
    )
    with patch("ui.board_v2._collect_keywords_for_persona", return_value=[]), \
         patch("scraping.run_daily.collect_batch", return_value=fake) as mock_cb:
        assert dm._consume_refresh_if_any() is True
    mock_cb.assert_called_once()
    assert mock_cb.call_args.args[0] == ["자동화", "AI"]
    toast = st.session_state.get("_dm_refresh_toast")
    assert toast[0] == "ok"
    assert "자동화" in toast[1] and "AI" in toast[1]


# ── 캐시 무효화는 항상 수행 ─────────────────────────────────

def test_refresh_always_clears_caches_even_on_collect_failure():
    """collect_batch 실패해도 캐시는 무효화돼야 한다."""
    from ui import data_management_v2 as dm
    import streamlit as st

    st.query_params["refresh"] = "now"
    with patch.object(dm._dm_stats, "clear") as c1, \
         patch.object(dm._news_cards_html, "clear") as c2, \
         patch("ui.board_v2._collect_keywords_for_persona", return_value=["X"]), \
         patch("scraping.run_daily.collect_batch", side_effect=RuntimeError("net")):
        dm._consume_refresh_if_any()
    c1.assert_called_once()
    c2.assert_called_once()
    toast = st.session_state.get("_dm_refresh_toast")
    assert toast[0] == "error"


# ── 토스트 렌더 — kind 별 색상 ─────────────────────────────

def test_refresh_toast_renders_ok_message():
    from ui import data_management_v2 as dm
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state["_dm_refresh_toast"] = ("ok", "✓ 잘 됐어요")
        dm._render_refresh_toast_if_needed()
    assert captured and "잘 됐어요" in captured[0]
    assert "_dm_refresh_toast" not in st.session_state


def test_refresh_toast_renders_warn_message():
    from ui import data_management_v2 as dm
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state["_dm_refresh_toast"] = ("warn", "ℹ️ 경고")
        dm._render_refresh_toast_if_needed()
    assert captured and "경고" in captured[0]
    # warn 색상 — 노란색 (#FFFBEB)
    assert "#FFFBEB" in captured[0]


def test_refresh_toast_backward_compat_true_payload():
    """이전 코드가 True 만 set 한 경우도 기본 메시지로 렌더."""
    from ui import data_management_v2 as dm
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state["_dm_refresh_toast"] = True
        dm._render_refresh_toast_if_needed()
    assert captured and "캐시" in captured[0]
