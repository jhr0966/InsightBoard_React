"""⑦ 키워드 관리 wire — × 삭제(mute / del_user) + 즉시 수집."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture
def isolated_persona(tmp_path, monkeypatch):
    """페르소나 JSON 영구 저장소를 임시 디렉토리로 격리."""
    monkeypatch.setenv("NEWS_DATA_ROOT", str(tmp_path / "data"))
    import config
    monkeypatch.setattr(config, "DATA_ROOT", tmp_path / "data")
    from persona import store as persona_store
    monkeypatch.setattr(
        persona_store, "_profile_path",
        lambda: tmp_path / "data" / "persona" / "profile.json",
    )
    (tmp_path / "data" / "persona").mkdir(parents=True, exist_ok=True)
    import streamlit as st
    for k in ("_kw_action_toast", "persona"):
        st.session_state.pop(k, None)
    yield persona_store


# ── URL 빌더 ────────────────────────────────────────────────

def test_kw_action_href_encodes_payload():
    from ui import board_v2
    href = board_v2._kw_action_href("mute", keyword="AI")
    assert "app_area=" in href
    assert "kw_action=mute" in href
    assert "keyword=AI" in href


def test_kw_action_href_omits_keyword_for_collect():
    from ui import board_v2
    href = board_v2._kw_action_href("collect")
    assert "keyword=" not in href
    assert "kw_action=collect" in href


# ── persona 스키마: muted_keywords 필드 ─────────────────────

def test_persona_muted_keywords_default_empty():
    from persona.schema import Persona
    p = Persona()
    assert p.muted_keywords == []


def test_persona_muted_keywords_roundtrip():
    from persona.schema import Persona
    p = Persona(muted_keywords=["AI", "로봇"])
    d = p.to_dict()
    p2 = Persona.from_dict(d)
    assert p2.muted_keywords == ["AI", "로봇"]


# ── consume_kw_action_if_any — del_user ─────────────────────

def test_consume_kw_action_del_user_removes_from_interest(isolated_persona):
    from ui import board_v2
    from persona.schema import Persona
    import streamlit as st

    p = Persona(dept="도장", interest_tasks=["비전 검사", "로봇 용접"], interest_lv3=["검사"])
    st.session_state["persona"] = p
    isolated_persona.save(p)

    st.query_params.clear()
    st.query_params["kw_action"] = "del_user"
    st.query_params["keyword"] = "비전 검사"

    result = board_v2.consume_kw_action_if_any()
    assert result == ("del_user", "비전 검사")

    saved = isolated_persona.load()
    assert "비전 검사" not in saved.interest_tasks
    assert "로봇 용접" in saved.interest_tasks
    toast = st.session_state.get("_kw_action_toast")
    assert toast and toast[0] == "ok" and "제거" in toast[1]
    # query 정리
    assert "kw_action" not in st.query_params
    assert "keyword" not in st.query_params


def test_consume_kw_action_del_user_no_match_noop(isolated_persona):
    """관심사에 없는 키워드 삭제 시도 → save 는 되지만 안내 메시지."""
    from ui import board_v2
    from persona.schema import Persona
    import streamlit as st

    p = Persona(dept="도장", interest_tasks=["비전 검사"])
    st.session_state["persona"] = p
    isolated_persona.save(p)

    st.query_params.clear()
    st.query_params["kw_action"] = "del_user"
    st.query_params["keyword"] = "없는키워드"
    board_v2.consume_kw_action_if_any()

    saved = isolated_persona.load()
    assert saved.interest_tasks == ["비전 검사"]
    toast = st.session_state.get("_kw_action_toast")
    assert toast and toast[0] == "ok"


# ── consume_kw_action_if_any — mute ─────────────────────────

def test_consume_kw_action_mute_adds_to_muted_keywords(isolated_persona):
    from ui import board_v2
    from persona.schema import Persona
    import streamlit as st

    p = Persona(dept="도장")
    st.session_state["persona"] = p
    isolated_persona.save(p)

    st.query_params.clear()
    st.query_params["kw_action"] = "mute"
    st.query_params["keyword"] = "AI"
    result = board_v2.consume_kw_action_if_any()
    assert result == ("mute", "AI")

    saved = isolated_persona.load()
    assert "AI" in saved.muted_keywords
    toast = st.session_state.get("_kw_action_toast")
    assert toast and toast[0] == "ok" and "숨겼" in toast[1]


def test_consume_kw_action_mute_dedup(isolated_persona):
    from ui import board_v2
    from persona.schema import Persona
    import streamlit as st

    p = Persona(dept="도장", muted_keywords=["AI"])
    st.session_state["persona"] = p
    isolated_persona.save(p)

    st.query_params.clear()
    st.query_params["kw_action"] = "mute"
    st.query_params["keyword"] = "AI"
    board_v2.consume_kw_action_if_any()

    saved = isolated_persona.load()
    assert saved.muted_keywords == ["AI"]


# ── consume_kw_action_if_any — collect ──────────────────────

def test_consume_kw_action_collect_calls_batch_with_persona_keywords(isolated_persona):
    from ui import board_v2
    from persona.schema import Persona
    from scraping.run_daily import CollectionReport
    import streamlit as st

    p = Persona(dept="도장", interest_tasks=["비전 검사"], interest_lv3=["도장 검사"])
    st.session_state["persona"] = p
    isolated_persona.save(p)

    st.query_params.clear()
    st.query_params["kw_action"] = "collect"

    fake_report = CollectionReport(
        saved=[{"source": "naver", "keywords": ["비전 검사"], "count": 3, "path": "x.parquet"}],
        errors=[],
    )
    with patch("scraping.run_daily.collect_batch", return_value=fake_report) as mock_cb:
        board_v2.consume_kw_action_if_any()

    mock_cb.assert_called_once()
    kws = mock_cb.call_args.args[0]
    assert "비전 검사" in kws
    assert "도장 검사" in kws

    toast = st.session_state.get("_kw_action_toast")
    assert toast and toast[0] == "ok" and "수집" in toast[1]


def test_consume_kw_action_collect_no_keywords_noop(isolated_persona):
    from ui import board_v2
    from persona.schema import Persona
    import streamlit as st

    p = Persona(dept="도장")
    st.session_state["persona"] = p
    isolated_persona.save(p)

    st.query_params.clear()
    st.query_params["kw_action"] = "collect"
    with patch("scraping.run_daily.collect_batch") as mock_cb:
        board_v2.consume_kw_action_if_any()
    mock_cb.assert_not_called()
    toast = st.session_state.get("_kw_action_toast")
    assert toast and toast[0] == "ok" and "키워드" in toast[1]


# ── 모르는 액션 무시 ────────────────────────────────────────

def test_consume_kw_action_noop_for_unknown(isolated_persona):
    from ui import board_v2
    import streamlit as st

    st.query_params.clear()
    st.query_params["kw_action"] = "nuke"
    st.query_params["keyword"] = "X"
    try:
        assert board_v2.consume_kw_action_if_any() is None
        # query 유지(디버깅용)
        assert st.query_params.get("kw_action") == "nuke"
    finally:
        st.query_params.clear()


def test_consume_kw_action_noop_when_missing(isolated_persona):
    from ui import board_v2
    import streamlit as st
    st.query_params.clear()
    assert board_v2.consume_kw_action_if_any() is None


# ── _board_kw_mgr_html — × 가 <a> 로 렌더 ──────────────────

def _fake_news_30():
    """기본 30일 뉴스 DataFrame fixture."""
    rows = []
    for i in range(20):
        rows.append({
            "title": f"AI 도입 사례 {i}",
            "summary": "로봇 비전 검사",
            "summary_llm": "",
            "keywords": "AI, 로봇, 비전",
            "keywords_llm": "",
            "content": "AI 비전 검사 자동화",
            "source": "naver" if i % 2 else "google",
        })
    return pd.DataFrame(rows)


def test_kw_mgr_renders_a_hrefs_for_x_buttons(isolated_persona):
    from ui import board_v2
    from persona.schema import Persona

    persona = Persona(dept="도장", interest_tasks=["비전 검사"])
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=_fake_news_30()), \
         patch.object(board_v2._trends, "top_keywords",
                      return_value=pd.DataFrame({"keyword": ["AI", "로봇"], "count": [10, 5]})):
        html = board_v2._board_kw_mgr_html(persona)

    # × 가 <a> 로 렌더
    assert '<a class="db-kchip-x"' in html
    # 자동 추출(mute) URL
    assert "kw_action=mute" in html
    # 사용자 키워드(del_user) URL
    assert "kw_action=del_user" in html
    # 즉시 수집 <a>
    assert 'class="db-kw-sum-cta"' in html
    assert "kw_action=collect" in html
    # disabled 자취 없음
    assert "disabled>×" not in html
    assert "disabled>지금 즉시 수집" not in html


def test_kw_mgr_filters_muted_from_auto_chips(isolated_persona):
    """muted_keywords 에 있는 키워드는 자동 추출 그룹에서 제외된다."""
    from ui import board_v2
    from persona.schema import Persona

    persona = Persona(dept="도장", muted_keywords=["AI"])
    fake_top = pd.DataFrame(
        {"keyword": ["AI", "로봇", "비전"], "count": [20, 10, 5]}
    )
    with patch.object(board_v2._news_db, "load_news_for_days", return_value=_fake_news_30()), \
         patch.object(board_v2._trends, "top_keywords", return_value=fake_top):
        html = board_v2._board_kw_mgr_html(persona)

    # mute 액션은 로봇/비전 만 노출 — AI 는 자동 추출에서 빠짐
    assert "kw_action=mute&keyword=%EB%A1%9C%EB%B4%87" in html  # 로봇
    assert "kw_action=mute&keyword=AI" not in html


# ── toast 렌더 ──────────────────────────────────────────────

def test_kw_action_toast_renders_and_clears_session_state():
    from ui import board_v2
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state["_kw_action_toast"] = ("ok", "✅ 수집 완료")
        board_v2.render_kw_action_toast_if_needed()
    assert captured and "수집 완료" in captured[0]
    assert "_kw_action_toast" not in st.session_state


def test_kw_action_toast_noop_when_empty():
    from ui import board_v2
    import streamlit as st
    captured = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)):
        st.session_state.pop("_kw_action_toast", None)
        board_v2.render_kw_action_toast_if_needed()
    assert captured == []
