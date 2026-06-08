"""뉴스 라이브러리 필터(출처·기간·정렬) — `_news_cards_html` 필터 로직 + 폼 렌더.

순수 단위 테스트는 `_news_db.load_news_for_days` 를 patch 해 카드 HTML 을 검증하고,
AppTest 스모크는 실제 `st.form` 이 데이터 관리 jobs 탭에서 정상 렌더되는지(=bare
'active form' 누수 없이) 확인한다.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ui import data_management_v2 as dm


def _news_df() -> pd.DataFrame:
    return pd.DataFrame({
        "title": ["A robot vision", "B 용접 자동화", "C 도장 결함", "D ai news"],
        "content": ["", "", "", ""],
        "summary": ["", "", "", ""],
        "keywords": [[], [], [], []],
        "source": ["AI Times", "네이버 기술", "AI Times", "Google RSS"],
        "collected_at": ["2026-06-05T10:00:00Z", "2026-06-04T10:00:00Z",
                         "2026-06-03T10:00:00Z", "2026-06-02T10:00:00Z"],
        "link": ["a", "b", "c", "d"],
    })


# ── _news_cards_html 필터 로직 ─────────────────────────────────────

def test_default_no_filter_preserves_strong_first_no_banner():
    dm._news_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        html = dm._news_cards_html("", (), 0, "newest")
    assert "dm-art-strong" in html        # 첫 장 강조 = 기존 기본 동작 유지
    assert "✕ 필터 해제" not in html       # 필터 비활성 → 배너 없음


def test_source_filter_limits_to_selected_sources():
    dm._news_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        html = dm._news_cards_html("", ("AI Times",), 7, "newest")
    assert "✕ 필터 해제" in html           # 필터 활성 → 배너
    assert "grid-column:1/-1" in html      # 배너는 그리드 전체 폭(한 칸에 끼이지 않게)
    assert "robot vision" in html and "도장 결함" in html   # AI Times 2건
    assert "용접 자동화" not in html        # 네이버 기술 제외
    assert "dm-art-strong" not in html     # 필터 뷰는 강조 카드 없음


def test_period_select_passes_days_to_loader():
    dm._news_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()) as m:
        dm._news_cards_html("", (), 30, "newest")
    assert m.call_args.kwargs.get("days") == 30


def test_search_only_widens_window_to_30_days():
    dm._news_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()) as m:
        dm._news_cards_html("robot", (), 0, "newest")   # 기간 미선택(0) + 검색어
    assert m.call_args.kwargs.get("days") == 30          # 검색 시 자동 30일로 확대


def test_default_browse_uses_3_days():
    dm._news_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()) as m:
        dm._news_cards_html("", (), 0, "newest")
    assert m.call_args.kwargs.get("days") == 3


def test_sort_oldest_reverses_order():
    dm._news_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        html_new = dm._news_cards_html("", ("AI Times",), 7, "newest")
    dm._news_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        html_old = dm._news_cards_html("", ("AI Times",), 7, "oldest")
    # newest: robot(06-05) 먼저 / oldest: 도장 결함(06-03) 먼저
    assert html_new.index("robot vision") < html_new.index("도장 결함")
    assert html_old.index("도장 결함") < html_old.index("robot vision")


def test_filter_no_match_shows_no_match_message():
    dm._news_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        html = dm._news_cards_html("존재하지않는키워드", (), 7, "newest")
    assert "일치하는" in html and "뉴스가 없어요" in html


def test_source_options_distinct_sorted():
    dm._news_source_options.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        opts = dm._news_source_options()
    assert opts == ["AI Times", "Google RSS", "네이버 기술"]   # distinct + 가나다 정렬


# ── AppTest 스모크 — 실제 st.form 렌더 (bare 'active form' 누수 검증) ───────

def _dm_app():
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona
    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state["app_area"] = "🗞 뉴스 수집"
    return at


def test_collect_renders_category_browser_not_filter_form():
    """개편: 뉴스 라이브러리 필터 폼(출처 멀티셀렉트·기간·정렬·'적용')은 제거됨.
    대신 카드 브라우저(빈 데이터=빈 상태) + 액션바가 예외 없이 렌더된다."""
    dm._sc_browse_records.clear(); dm._sc_cards_html.clear()
    at = _dm_app()
    at.run()
    assert not at.exception
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "뉴스 라이브러리 필터" not in combined          # 구 필터 폼 헤더 제거
    labels = {s.label for s in at.selectbox}
    assert "기간" not in labels and "정렬" not in labels   # 필터 셀렉트 제거
    assert "sc-empty" in combined or "sc-grid" in combined  # 카드 브라우저 렌더


def test_clear_search_query_resets_search():
    """`?dm_clear_q=1` → 상단 검색어(_news_search_q)·입력 위젯이 비워진다.
    (뉴스 라이브러리 필터는 제거됐고 상단 검색만 유지된다.)"""
    at = _dm_app()
    at.session_state["_news_search_q"] = "robot"
    at.session_state["_topbar_q"] = "robot"
    at.query_params["dm_clear_q"] = "1"
    at.run()
    assert not at.exception
    assert at.session_state["_news_search_q"] == ""
