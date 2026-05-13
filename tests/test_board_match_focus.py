"""Phase 6-C 후속: 매트릭스 셀 → 매칭 뉴스 점프 헬퍼 단위 테스트.

`ui.board_tab._matches_for_focus` 는 (dept, lv3) 셀 점프용 stateless 헬퍼.
streamlit 의존 없이 직접 호출 가능.
"""
from __future__ import annotations

import pandas as pd

from ui import board_tab


def _sample_news() -> pd.DataFrame:
    return pd.DataFrame([
        {"title": "용접 자동화 로봇", "press": "조선", "summary": "",
         "keywords": "용접, 자동화, 로봇", "link": "n1"},
        {"title": "강재 절단 라인", "press": "AI Times", "summary": "",
         "keywords": "강재, 절단", "link": "n2"},
        {"title": "도장 공정 비전 AI", "press": "오토메이션", "summary": "",
         "keywords": "도장, 비전, AI", "link": "n3"},
    ])


def _sample_roadmap() -> pd.DataFrame:
    return pd.DataFrame([
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "가공",
         "task": "절단", "sub_task": "강재 절단", "task_def": "",
         "sws_no": "", "sws_name": "절단 작업"},
        {"dept": "조립부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "형강",
         "task": "용접", "sub_task": "B/up 용접", "task_def": "",
         "sws_no": "", "sws_name": "용접 작업"},
        {"dept": "선각부", "lv1": "실행분과", "lv2": "도장", "lv3": "외판",
         "task": "도장", "sub_task": "외판 도장", "task_def": "",
         "sws_no": "", "sws_name": "외판 도장"},
    ])


def test_matches_for_focus_returns_subset_only():
    out = board_tab._matches_for_focus(_sample_news(), _sample_roadmap(), "조립부", "형강")
    assert not out.empty
    # 결과의 모든 행이 (조립부 / 형강) 셀에 속해야 함
    assert (out["dept"] == "조립부").all()
    assert (out["lv3"] == "형강").all()


def test_matches_for_focus_empty_when_no_match():
    out = board_tab._matches_for_focus(_sample_news(), _sample_roadmap(), "조립부", "존재하지않음")
    assert out.empty


def test_matches_for_focus_empty_when_dept_missing():
    out = board_tab._matches_for_focus(_sample_news(), _sample_roadmap(), "없는부서", "가공")
    assert out.empty


def test_matches_for_focus_empty_news_returns_empty():
    out = board_tab._matches_for_focus(pd.DataFrame(), _sample_roadmap(), "가공부", "가공")
    assert out.empty


def test_matches_for_focus_empty_roadmap_returns_empty():
    out = board_tab._matches_for_focus(_sample_news(), pd.DataFrame(), "가공부", "가공")
    assert out.empty


def test_matches_for_focus_missing_columns_returns_empty():
    """roadmap 에 dept/lv3 컬럼이 없는 깨진 스키마도 graceful."""
    bad = pd.DataFrame([{"foo": "bar"}])
    out = board_tab._matches_for_focus(_sample_news(), bad, "가공부", "가공")
    assert out.empty


def test_matches_for_focus_score_columns_present():
    """반환 DataFrame 에 score 가 있어야 UI 카드 score 표시 가능."""
    out = board_tab._matches_for_focus(_sample_news(), _sample_roadmap(), "가공부", "가공")
    if not out.empty:
        assert "score" in out.columns
        assert "news_title" in out.columns
        assert "link" in out.columns
