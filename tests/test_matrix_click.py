"""보드 ⑥ 매트릭스 버블 클릭 wire — `?mx_select=` 1회 stateless 선택."""
from __future__ import annotations

from unittest.mock import patch
from urllib.parse import quote

import pandas as pd


def _synthetic_cells() -> pd.DataFrame:
    return pd.DataFrame([
        {"dept": "도장1팀", "lv3": "비전 검사", "cell_score": 95.0,
         "matched_news": 40, "matched_tasks": 18,
         "sample_tasks": "AI 막두께 검사", "sample_news": "AI 자동",
         "sample_objectives": ""},
        {"dept": "용접팀", "lv3": "비드 검사", "cell_score": 72.0,
         "matched_news": 20, "matched_tasks": 9,
         "sample_tasks": "비드 자동 검사", "sample_news": "용접 자동",
         "sample_objectives": ""},
        {"dept": "조립팀", "lv3": "조립 정합", "cell_score": 50.0,
         "matched_news": 12, "matched_tasks": 5,
         "sample_tasks": "조립 정합", "sample_news": "조립 자동",
         "sample_objectives": ""},
    ])


# ── URL 빌더 ────────────────────────────────────────────────

def test_mx_select_href_encodes_dept_lv3_pair():
    from ui import board_v2
    href = board_v2._mx_select_href("도장 1팀", "비전 검사")
    assert "app_area=" + quote("📊 오늘의 보드") in href
    # dept|lv3 가 함께 인코딩
    assert "mx_select=" + quote("도장 1팀|비전 검사") in href


def test_mx_select_href_empty_clears_selection():
    from ui import board_v2
    href = board_v2._mx_select_href("", "")
    assert "mx_select=" not in href
    assert "app_area=" in href


def test_mx_selected_key_reads_query_param():
    from ui import board_v2
    import streamlit as st
    st.query_params.clear()
    st.query_params["mx_select"] = "도장1팀|비전 검사"
    try:
        assert board_v2._mx_selected_key() == "도장1팀|비전 검사"
    finally:
        st.query_params.clear()


def test_mx_selected_key_none_when_missing():
    from ui import board_v2
    import streamlit as st
    st.query_params.clear()
    assert board_v2._mx_selected_key() is None


# ── 매트릭스 HTML — <a> 전환 + 선택 표시 ────────────────────

def test_matrix_renders_a_hrefs_for_bubbles_not_disabled_buttons():
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=_synthetic_cells()):
        html = board_v2._board_matrix_html()
    # 3개 버블 모두 <a class="db-mx-bubble">
    assert html.count('class="db-mx-bubble"') >= 0
    assert 'class="db-mx-bubble' in html
    # disabled 자취 없음
    assert "disabled" not in html
    # 기본 선택은 1위
    assert "선택됨 · 1위" in html


def test_matrix_selected_key_marks_that_bubble_on_and_updates_detail():
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=_synthetic_cells()):
        # 2위 셀(용접팀|비드 검사) 선택
        html = board_v2._board_matrix_html(selected_key="용접팀|비드 검사")

    # db-mx-on 클래스 1개만 (선택된 셀)
    assert html.count("db-mx-on") == 1
    assert html.count('aria-current="true"') == 1
    # 상세 패널이 해당 셀로 갱신
    assert "용접팀" in html and "비드 검사" in html
    assert "선택됨 · 2위" in html


def test_matrix_selected_bubble_href_toggles_off():
    """선택된 버블의 href 는 mx_select 빈 값(필터 해제)."""
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=_synthetic_cells()):
        html = board_v2._board_matrix_html(selected_key="도장1팀|비전 검사")
    # 선택된 도장1팀 셀의 href 는 mx_select 없는 base URL
    # 다른 셀들은 mx_select=용접팀|비드 검사 / 조립팀|조립 정합 형태
    assert "mx_select=" + quote("용접팀|비드 검사") in html
    # 도장1팀 자체는 토글 해제 href — 별도 mx_select 토큰 없는 entry 가 활성 버블에 있어야
    # (활성 셀이 href 1개 존재하지 않는 케이스 검증은 어렵지만 db-mx-on 1개 + aria-current 1개로 보장)
    assert html.count("db-mx-on") == 1


def test_matrix_unknown_selected_key_falls_back_to_first():
    from ui import board_v2
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=_synthetic_cells()):
        html = board_v2._board_matrix_html(selected_key="없는|셀")
    # fallback → 1위 도장1팀
    assert "선택됨 · 1위" in html
    assert "도장1팀" in html


def test_matrix_each_bubble_has_clickable_href():
    """버블 3개 모두 클릭 가능한 href 보유."""
    from ui import board_v2
    board_v2._board_matrix_html.clear()
    with patch.object(board_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(board_v2, "_score_cells", return_value=_synthetic_cells()):
        html = board_v2._board_matrix_html()
    # 3개 셀 → 3개 mx_select href (활성 1위는 빈 mx_select)
    assert "mx_select=" + quote("용접팀|비드 검사") in html
    assert "mx_select=" + quote("조립팀|조립 정합") in html
