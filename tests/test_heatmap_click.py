"""인사이트 SECTION C 히트맵 cell 클릭 wire — `?hm_select=` 1회 stateless."""
from __future__ import annotations

from unittest.mock import patch
from urllib.parse import quote

import pandas as pd


def _synthetic_cells():
    return pd.DataFrame([
        {"dept": "도장1팀", "lv3": "비전 검사", "cell_score": 95.0,
         "matched_news": 40, "matched_tasks": 18,
         "sample_tasks": "AI", "sample_news": "AI", "sample_objectives": ""},
        {"dept": "용접팀", "lv3": "비드 검사", "cell_score": 72.0,
         "matched_news": 20, "matched_tasks": 9,
         "sample_tasks": "비드", "sample_news": "용접", "sample_objectives": ""},
    ])


def _synthetic_news():
    """비전 + 검사 모두 포함하는 뉴스 다수."""
    rows = []
    for i in range(20):
        rows.append({
            "title": f"AI 비전 검사 도장 도입 사례 {i}",
            "summary": "비전 시스템",
            "keywords": "비전, 협동 로봇",
            "source": "naver",
            "link": f"https://x.com/{i}",
            "collected_at": f"2026-05-{30 - i % 10:02d}T06:00:00+00:00",
            "content": "비전 검사 자동화",
        })
    # 추가: 다른 키워드
    for i in range(5):
        rows.append({
            "title": f"디지털 트윈 사례 {i}",
            "summary": "디지털 트윈 도입",
            "keywords": "디지털 트윈, AI",
            "source": "google",
            "link": f"https://y.com/{i}",
            "collected_at": "2026-05-29T06:00:00+00:00",
            "content": "디지털 트윈",
        })
    return pd.DataFrame(rows)


# ── URL 빌더 ────────────────────────────────────────────────

def test_hm_select_href_encodes_pair():
    from ui import insights_v2
    href = insights_v2._hm_select_href("비전 검사", "협동 로봇")
    assert "app_area=" + quote("🔎 인사이트 분석") in href
    assert "hm_select=" + quote("비전 검사|협동 로봇") in href


def test_hm_select_href_empty_clears():
    from ui import insights_v2
    href = insights_v2._hm_select_href("", "")
    assert "hm_select=" not in href


def test_hm_selected_key_reads_query():
    from ui import insights_v2
    import streamlit as st
    st.query_params.clear()
    st.query_params["hm_select"] = "비전 검사|AI"
    try:
        assert insights_v2._hm_selected_key() == "비전 검사|AI"
    finally:
        st.query_params.clear()


def test_hm_selected_key_none_when_missing():
    from ui import insights_v2
    import streamlit as st
    st.query_params.clear()
    assert insights_v2._hm_selected_key() is None


# ── 카운트 / 클래스 ────────────────────────────────────────

def test_hm_count_in_news_basic():
    from ui import insights_v2
    df = pd.DataFrame([
        {"title": "AI 비전 검사 도장 사례", "summary": "", "keywords": ""},
        {"title": "디지털 트윈 사례", "summary": "", "keywords": ""},
        {"title": "도장 검사", "summary": "AI 비전", "keywords": ""},
    ])
    # 도장 AND 비전 — 1, 3 행이 포함 (case-insensitive substring)
    assert insights_v2._hm_count_in_news(df, "도장", "비전") == 2
    # 비전 AND 디지털 — 0 (어느 row 에도 둘 다 없음)
    assert insights_v2._hm_count_in_news(df, "비전", "디지털 트윈") == 0


def test_hm_count_zero_for_empty_or_missing_args():
    from ui import insights_v2
    assert insights_v2._hm_count_in_news(None, "X", "Y") == 0
    assert insights_v2._hm_count_in_news(pd.DataFrame(), "X", "Y") == 0
    assert insights_v2._hm_count_in_news(pd.DataFrame([{"title": "t"}]), "", "Y") == 0


def test_hm_cell_class_buckets():
    from ui import insights_v2
    assert "ia-hm-c-empty" in insights_v2._hm_cell_class(0)
    assert "ia-hm-c-low" in insights_v2._hm_cell_class(2)
    cls7 = insights_v2._hm_cell_class(7)
    assert "ia-hm-c-low" not in cls7 and "ia-hm-c-mid" not in cls7  # 기본
    assert "ia-hm-c-mid" in insights_v2._hm_cell_class(10)
    assert "ia-hm-c-strong" in insights_v2._hm_cell_class(50)


def test_hm_top_news_returns_sorted():
    from ui import insights_v2
    df = _synthetic_news()
    out = insights_v2._hm_top_news(df, "도장", "비전", limit=3)
    assert len(out) == 3
    assert all("title" in n and "source" in n and "link" in n for n in out)
    # 도장 비전 포함되는 뉴스만
    assert all("도장" in n["title"] or "비전" in n["title"] for n in out)


# ── _ia_heatmap_html — 동적 데이터 + 클릭 wire ─────────────

def test_heatmap_renders_cells_as_anchors_not_divs():
    from ui import insights_v2
    news = _synthetic_news()
    cells = _synthetic_cells()
    insights_v2._ia_heatmap_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells):
        html = insights_v2._ia_heatmap_html()

    # 모든 셀이 <a> 로 렌더 (2개 process × 7개 tech = 14 셀)
    assert html.count('class="ia-hm-c') >= 14
    assert "<a " in html
    assert "hm_select=" in html
    # 옛 mock 데이터 자취 없음
    assert "도장 품질검사" not in html  # 정적 mockup row name
    assert "ia-hm-trig" not in html  # 옛 "빈 칸 클릭" 버튼


def test_heatmap_marks_selected_cell():
    from ui import insights_v2
    news = _synthetic_news()
    cells = _synthetic_cells()
    insights_v2._ia_heatmap_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells):
        html = insights_v2._ia_heatmap_html(selected_key="비전 검사|비전")

    # 활성 셀 1개
    assert html.count("ia-hm-c-on") == 1
    assert html.count('aria-current="true"') == 1
    # 상세 strip 노출 — 매칭 뉴스 미리보기 + SOLA 인계
    assert "ia-hm-detail" in html
    assert "SOLA 작업실에서 더 보기" in html
    # 매칭 뉴스가 카드로 펼쳐짐
    assert "비전" in html


def test_heatmap_selected_cell_href_toggles_off():
    """선택된 셀 클릭 href = 빈 hm_select."""
    from ui import insights_v2
    news = _synthetic_news()
    cells = _synthetic_cells()
    insights_v2._ia_heatmap_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells):
        html = insights_v2._ia_heatmap_html(selected_key="비전 검사|비전")
    # 다른 (비활성) 셀의 href 는 그 셀 키로
    assert "hm_select=" + quote("비전 검사|협동 로봇") in html
    # 활성 셀(비전 검사|비전) 자신은 hm_select 없는 href
    assert "hm_select=" + quote("비전 검사|비전") not in html


def test_heatmap_detail_zero_matches_shows_empty_strip():
    """선택은 했지만 매칭 0건 → '매칭 뉴스가 없어요' 안내."""
    from ui import insights_v2
    news = _synthetic_news()
    cells = _synthetic_cells()
    insights_v2._ia_heatmap_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells):
        html = insights_v2._ia_heatmap_html(selected_key="없는공정|없는기술")
    assert "ia-hm-detail-empty" in html
    assert "매칭 뉴스가 없어요" in html


def test_heatmap_empty_data_returns_empty_state():
    from ui import insights_v2
    insights_v2._ia_heatmap_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=pd.DataFrame()), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame()):
        html = insights_v2._ia_heatmap_html()
    assert "공정 × 자동화 기술 매칭이 없어요" in html


def test_heatmap_includes_total_count_in_legend():
    from ui import insights_v2
    news = _synthetic_news()
    cells = _synthetic_cells()
    insights_v2._ia_heatmap_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=cells):
        html = insights_v2._ia_heatmap_html()
    assert "합계" in html
    assert "/ 30일" in html


# ── 템플릿 placeholder ────────────────────────────────────

def test_insights_template_has_heatmap_placeholder():
    from config import ASSETS_DIR
    template = (ASSETS_DIR / "v2" / "screens" / "insights_main.html").read_text(encoding="utf-8")
    assert "{{IA_HEATMAP}}" in template
    # 옛 정적 mockup 자취 없음 — 정적 행 헤더/트리거 모두 제거 확인
    assert 'class="ia-hm-rh">도장 품질검사' not in template
    assert 'class="ia-hm-rh">용접 비드' not in template
    assert "ia-hm-trig" not in template  # 옛 "빈 칸 클릭 → 키워드 추가 수집"
