"""인사이트 매트릭스 셀 클릭 wire — `?ia_mx_select=` 1회 stateless 선택."""
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

def test_ia_mx_select_href_encodes_dept_lv3_pair():
    from ui import insights_v2
    href = insights_v2._ia_mx_select_href("도장 1팀", "비전 검사")
    assert "app_area=" + quote("🔎 인사이트 분석") in href
    assert "ia_mx_select=" + quote("도장 1팀|비전 검사") in href


def test_ia_mx_select_href_empty_clears_selection():
    from ui import insights_v2
    href = insights_v2._ia_mx_select_href("", "")
    assert "ia_mx_select=" not in href


def test_ia_mx_selected_key_reads_query():
    from ui import insights_v2
    import streamlit as st
    st.query_params.clear()
    st.query_params["ia_mx_select"] = "용접팀|비드 검사"
    try:
        assert insights_v2._ia_mx_selected_key() == "용접팀|비드 검사"
    finally:
        st.query_params.clear()


def test_ia_mx_selected_key_none_when_missing():
    from ui import insights_v2
    import streamlit as st
    st.query_params.clear()
    assert insights_v2._ia_mx_selected_key() is None


# ── _ia_matrix_svg — SVG <a> + 활성 halo ──────────────────

def test_ia_matrix_svg_bubbles_wrapped_in_a_links():
    from ui import insights_v2
    insights_v2._ia_matrix_svg.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=_synthetic_cells()):
        svg = insights_v2._ia_matrix_svg()

    # 3개 셀 모두 <a xlink:href=...> 로 wrap
    assert svg.count("<a xlink:href=") == 3
    assert "ia_mx_select=" in svg
    # disabled 자취 없음
    assert "disabled" not in svg
    # 기본 1위 활성
    assert "ia-mtx-bubble-on" in svg
    assert svg.count("ia-mtx-bubble-on") == 1


def test_ia_matrix_svg_selected_key_marks_that_bubble():
    from ui import insights_v2
    insights_v2._ia_matrix_svg.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=_synthetic_cells()):
        svg = insights_v2._ia_matrix_svg(selected_key="용접팀|비드 검사")

    assert svg.count("ia-mtx-bubble-on") == 1
    # 비활성 버블은 새 선택 href 를 가짐 (도장1팀)
    assert "ia_mx_select=" + quote("도장1팀|비전 검사") in svg
    # 활성 셀(용접팀)의 href 는 토글 해제(빈 ia_mx_select)
    # 즉, "ia_mx_select=용접팀|비드 검사" 가 svg 에 없어야 함
    assert "ia_mx_select=" + quote("용접팀|비드 검사") not in svg


def test_ia_matrix_svg_unknown_key_falls_back_to_first():
    from ui import insights_v2
    insights_v2._ia_matrix_svg.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=_synthetic_cells()):
        svg = insights_v2._ia_matrix_svg(selected_key="없는|셀")

    assert svg.count("ia-mtx-bubble-on") == 1
    # 1위(도장1팀) 가 활성 — 그 href 는 토글 해제
    assert "ia_mx_select=" + quote("도장1팀|비전 검사") not in svg


# ── _ia_mtx_rank_html — 동적 POC 리스트 ────────────────────

def test_ia_mtx_rank_html_renders_from_cells():
    from ui import insights_v2
    insights_v2._ia_mtx_rank_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=_synthetic_cells()):
        html = insights_v2._ia_mtx_rank_html()
    # 3개 cells 그대로 노출 (max 5)
    assert html.count("ia-poc-link") == 3
    # 기본 1위 활성
    assert html.count("ia-poc-on") == 1
    # 옛 mock 텍스트 흔적 없음
    assert "14명/일" not in html
    assert "9.2" not in html  # 기존 mockup score
    # 실제 score (10점 만점 환산)
    assert "10.0" in html  # 1위 (95 / 95 * 10)


def test_ia_mtx_rank_html_marks_selected():
    from ui import insights_v2
    insights_v2._ia_mtx_rank_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_load_roadmap",
                      return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=_synthetic_cells()):
        html = insights_v2._ia_mtx_rank_html(selected_key="조립팀|조립 정합")

    assert html.count("ia-poc-on") == 1
    assert html.count('aria-current="true"') == 1
    # 활성 항목 = 03 번 (조립팀)
    assert "조립팀" in html


def test_ia_mtx_rank_html_empty_state():
    from ui import insights_v2
    insights_v2._ia_mtx_rank_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(insights_v2, "_load_roadmap", return_value=pd.DataFrame()):
        html = insights_v2._ia_mtx_rank_html()
    assert "0건" in html
    assert "ia-poc-link" not in html


# ── 템플릿 placeholder ──────────────────────────────────────

def test_insights_template_has_mtx_rank_placeholder():
    from config import ASSETS_DIR
    template = (ASSETS_DIR / "v2" / "screens" / "insights_main.html").read_text(encoding="utf-8")
    assert "{{IA_MTX_RANK}}" in template
    # 옛 mock POC 리스트 mockup 사라짐 (다른 섹션의 "14명/일" 은 별개라 검사 X)
    assert "ia-poc ia-poc-on" not in template  # 정적 li 자취
    assert "ia-poc-more" not in template  # "7건 전체 보기" 버튼 자취
