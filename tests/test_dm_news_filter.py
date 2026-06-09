"""뉴스 수집 카드 브라우저 — 옛 라이브러리 필터 폼 제거 회귀 + 상단 검색 해제.

(#133 재설계로 출처·기간·정렬 필터 폼은 제거됐다 — 상단 토픽 검색 + 대분류 탭·출처칩이
대체.) 카드 브라우저 단위 로직은 tests/test_collect_browser.py 가 덮는다.
"""
from __future__ import annotations

from ui import data_management_v2 as dm


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
    """옛 필터 폼(출처 멀티셀렉트·기간·정렬·'적용')은 없고, 카드 브라우저가 렌더된다."""
    dm._sc_browse_records.clear()
    at = _dm_app()
    at.run()
    assert not at.exception
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "뉴스 라이브러리 필터" not in combined          # 구 필터 폼 헤더 제거
    labels = {s.label for s in at.selectbox}
    assert "기간" not in labels and "정렬" not in labels   # 필터 셀렉트 제거
    assert "sc-empty" in combined or "sc-grid" in combined  # 카드 브라우저 렌더


def test_clear_search_query_resets_search():
    """`?dm_clear_q=1` → 상단 검색어(_news_search_q)·입력 위젯이 비워진다."""
    at = _dm_app()
    at.session_state["_news_search_q"] = "robot"
    at.session_state["_topbar_q"] = "robot"
    at.query_params["dm_clear_q"] = "1"
    at.run()
    assert not at.exception
    assert at.session_state["_news_search_q"] == ""
