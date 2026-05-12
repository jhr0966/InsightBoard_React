"""뉴스 저장소·룰 기반 매칭 단위 테스트."""
from __future__ import annotations

import pandas as pd

from roadmap.ingest import ingest_excel
from store.match import score_matches
from store.news_db import load_all_today, load_latest, save_articles


def _sample_articles() -> list[dict]:
    return [
        {
            "title": "조선소 용접 자동화 로봇 도입",
            "press": "AITimes", "date": "1시간 전", "link": "https://x.com/1",
            "summary": "용접 자동화 로봇 신기술", "keywords": "용접, 자동화, 로봇",
            "source": "naver", "query": "조선소 자동화",
        },
        {
            "title": "강재 절단 공정 효율화",
            "press": "AutomationWorld", "date": "2시간 전", "link": "https://x.com/2",
            "summary": "강재 절단 효율", "keywords": "강재, 절단",
            "source": "naver", "query": "강재 절단",
        },
    ]


def test_save_and_load_articles():
    path = save_articles(_sample_articles(), source="naver")
    assert path is not None and path.exists()

    df = load_latest(source="naver")
    assert len(df) == 2
    assert "title" in df.columns

    all_df = load_all_today()
    assert len(all_df) == 2


def test_save_empty_returns_none():
    assert save_articles([], source="naver") is None


def test_score_matches_finds_overlap():
    news = pd.DataFrame(_sample_articles())
    roadmap = pd.DataFrame([
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "전처리",
         "task": "강재선별", "sub_task": "크레인", "task_def": "", "sws_no": "", "sws_name": "강재 하역"},
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "가공",
         "task": "절단", "sub_task": "강재 절단", "task_def": "", "sws_no": "", "sws_name": "절단 작업"},
    ])
    matches = score_matches(news, roadmap, top_k=2)
    assert not matches.empty
    cutting = matches[matches["task"] == "절단"]
    assert not cutting.empty
    assert cutting.iloc[0]["link"] == "https://x.com/2"
