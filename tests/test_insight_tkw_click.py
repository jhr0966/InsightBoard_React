"""인사이트 트렌드 키워드 클릭 wire — `?tkw=` 필터 + <a> 전환."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import quote

import pandas as pd


def _synthetic_news_30d() -> pd.DataFrame:
    """30일치 합성 뉴스. keywords 컬럼에 'AI', '로봇', '비전' 포함."""
    now = datetime.now(timezone.utc)
    rows = []
    for d in range(30):
        t = (now - timedelta(days=d)).isoformat()
        rows.append({
            "published_at": t,
            "collected_at": t,
            "title": f"AI 비전 검사 사례 {d}",
            "summary": "로봇 자동화",
            "keywords": "AI, 로봇, 비전",
            "source": "naver",
            "content": "AI 비전 자동화 사례",
        })
    return pd.DataFrame(rows)


# ── URL 빌더 ────────────────────────────────────────────────

def test_tkw_select_href_with_keyword():
    from ui import insights_v2
    href = insights_v2._tkw_select_href("AI")
    assert "app_area=" + quote("🔎 인사이트 분석") in href
    assert "tkw=AI" in href


def test_tkw_select_href_empty_keyword_clears_filter():
    from ui import insights_v2
    href = insights_v2._tkw_select_href("")
    assert "tkw=" not in href
    assert "app_area=" in href


# ── _tkw_list_html — <a> 전환 + disabled 자취 0 ─────────────

def test_tkw_list_renders_anchors_not_disabled_buttons():
    from ui import insights_v2
    news = _synthetic_news_30d()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news):
        html = insights_v2._tkw_list_html()
    assert '<a class="ia-tkw-item' in html
    assert "disabled" not in html
    # 기본(selected_kw=None) → 1위 rank 가 ia-tkw-on
    assert 'class="ia-tkw-item ia-tkw-on"' in html


def test_tkw_list_active_class_follows_selected_kw():
    """selected_kw 가 명시되면 해당 키워드만 ia-tkw-on, 1위 기본 활성 해제."""
    from ui import insights_v2
    fake_top = pd.DataFrame({"keyword": ["AI", "로봇", "비전"], "count": [20, 15, 10]})
    news = _synthetic_news_30d()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2._trends, "top_keywords", return_value=fake_top), \
         patch.object(insights_v2._trends, "keyword_emergence",
                      return_value={"new": pd.DataFrame(columns=["keyword","count"]),
                                    "rising": pd.DataFrame(columns=["keyword","today","base","delta"])}):
        html = insights_v2._tkw_list_html(selected_kw="로봇")

    # "로봇" 만 활성
    assert html.count("ia-tkw-on") == 1
    # 활성 항목의 href 는 토글 해제 (tkw 없음)
    # 비활성 항목은 tkw=<kw> 형태로 새 선택
    assert "tkw=AI" in html
    assert "tkw=%EB%A1%9C%EB%B4%87" not in html  # 활성된 로봇은 tkw 제거
    # aria-current 도 1개
    assert html.count('aria-current="true"') == 1


def test_tkw_list_active_href_toggles_off():
    """활성 키워드 클릭 href 는 빈 tkw (필터 해제)."""
    from ui import insights_v2
    fake_top = pd.DataFrame({"keyword": ["AI"], "count": [10]})
    news = _synthetic_news_30d()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2._trends, "top_keywords", return_value=fake_top), \
         patch.object(insights_v2._trends, "keyword_emergence",
                      return_value={"new": pd.DataFrame(columns=["keyword","count"]),
                                    "rising": pd.DataFrame(columns=["keyword","today","base","delta"])}):
        html = insights_v2._tkw_list_html(selected_kw="AI")
    # 활성 항목은 tkw 없는 href (toggle off)
    assert "필터 해제" in html
    assert "tkw=AI" not in html


# ── _ia_process_map_html — 키워드 필터링 ────────────────────

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


def test_process_map_with_selected_kw_uses_it_as_from_chip():
    from ui import insights_v2
    news = _synthetic_news_30d()  # 'AI' 포함
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=_synthetic_cells()), \
         patch("ui.board_v2._weekly_keyword_series",
               return_value=(["W1"], [{"name": "다른 키워드", "counts": [1]}])):
        insights_v2._ia_process_map_html.clear()
        html = insights_v2._ia_process_map_html(selected_kw="AI 비전")

    # from chip 에 selected_kw 표시 (top trending 이 아닌 사용자 선택)
    assert "AI 비전" in html
    assert "다른 키워드" not in html


def test_process_map_filters_news_by_selected_kw():
    """selected_kw 가 뉴스에 없으면 필터 후 빈 결과 → empty 메시지."""
    from ui import insights_v2
    news = _synthetic_news_30d()  # 'AI', '로봇', '비전' 만 포함
    insights_v2._ia_process_map_html.clear()
    with patch.object(insights_v2._news_db, "load_news_for_days", return_value=news), \
         patch.object(insights_v2, "_load_tasks", return_value=pd.DataFrame([{"a": 1}])), \
         patch.object(insights_v2, "_score_cells", return_value=_synthetic_cells()):
        html = insights_v2._ia_process_map_html(selected_kw="없는키워드XYZ")
    # 필터 후 0건 → 키워드별 빈 안내
    assert "없는키워드XYZ" in html
    assert "전체 보기" in html


def test_process_map_empty_selected_kw_includes_clear_link():
    """필터링 결과 0건 빈 안내에 '전체 보기' 링크 포함."""
    from ui import insights_v2
    insights_v2._ia_process_map_html.clear()
    empty_html = insights_v2._ia_pmap_empty(selected_kw="XYZ")
    assert "tkw=" not in empty_html or "tkw=&" in empty_html  # 빈 tkw href
    assert "전체 보기" in empty_html


# ── _news_filter_by_keyword 유틸 ────────────────────────────

def test_news_filter_by_keyword_substring_case_insensitive():
    from ui import insights_v2
    df = pd.DataFrame([
        {"title": "AI 자동화 사례", "summary": "", "keywords": ""},
        {"title": "수동 검사", "summary": "ai 도입 효과", "keywords": ""},
        {"title": "전혀 무관", "summary": "관련 없음", "keywords": ""},
    ])
    res = insights_v2._news_filter_by_keyword(df, "AI")
    # 1, 2 행만 (case-insensitive)
    assert len(res) == 2


def test_news_filter_by_keyword_empty_returns_input():
    from ui import insights_v2
    df = pd.DataFrame([{"title": "X"}])
    assert insights_v2._news_filter_by_keyword(df, "") is df


def test_news_filter_by_keyword_none_or_empty_df():
    from ui import insights_v2
    assert insights_v2._news_filter_by_keyword(None, "X") is None
    empty = pd.DataFrame()
    assert insights_v2._news_filter_by_keyword(empty, "X") is empty
