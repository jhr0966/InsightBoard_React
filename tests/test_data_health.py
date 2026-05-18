from __future__ import annotations

import pandas as pd

from ui import data_health


def test_content_ready_count_and_enrich_percent():
    news = pd.DataFrame([
        {"content": "x" * 80, "source": "naver"},
        {"content": "short", "source": "google"},
    ])

    assert data_health.content_ready_count(news) == 1
    assert data_health.enrich_percent(news) == 50


def test_data_quality_items_warn_when_all_prerequisites_missing():
    items = data_health.data_quality_items(
        pd.DataFrame(),
        pd.DataFrame(),
        llm_configured=False,
    )

    assert [item["title"] for item in items] == [
        "뉴스 DB 준비 필요",
        "본문 Enrich 대기",
        "로드맵 DB 준비 필요",
        "LLM 설정 확인 필요",
    ]
    assert all(item["status"] == "warn" for item in items)


def test_data_quality_items_ok_when_data_ready():
    news = pd.DataFrame([
        {"content": "x" * 80, "source": "naver"},
        {"content": "y" * 90, "source": "google"},
    ])
    roadmap = pd.DataFrame([
        {"dept": "생산기술", "lv3": "용접", "task": "용접 자동화"},
        {"dept": "품질", "lv3": "검사", "task": "검사 자동화"},
    ])

    items = data_health.data_quality_items(news, roadmap, llm_configured=True)

    assert [item["title"] for item in items] == [
        "뉴스 DB 준비됨",
        "본문 Enrich 완료",
        "로드맵 DB 준비됨",
        "LLM 연결 준비됨",
    ]
    assert all(item["status"] == "ok" for item in items)


def test_data_health_html_escapes_dynamic_values():
    news = pd.DataFrame([
        {"content": "x" * 80, "source": '<script>alert("x")</script>'},
    ])
    roadmap = pd.DataFrame([
        {"dept": "생산기술<script>", "lv3": "용접", "task": "자동화"},
    ])

    html = data_health.data_health_html(news, roadmap, llm_configured=False)

    assert '<script>' not in html
    assert "data-quality-grid" in html
    assert "오늘 뉴스" in html
    assert "LLM 설정 확인 필요" in html


def test_build_data_context_summarizes_status():
    news = pd.DataFrame([
        {"content": "x" * 80, "source": "naver"},
        {"content": "", "source": "google"},
    ])
    roadmap = pd.DataFrame([{"dept": "생산기술"}])

    ctx = data_health.build_data_context(news, roadmap, llm_configured=False)

    assert "오늘 뉴스: 2건 / 본문 확보: 1건 (50%)" in ctx
    assert "로드맵 작업: 1건 / 부서: 1개" in ctx
    assert "LLM 설정: 확인 필요" in ctx
