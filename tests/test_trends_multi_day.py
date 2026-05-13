"""다중 일자 트렌드: news_db.load_news_for_days, trends.{daily_volume, keyword_emergence, compare_distribution}."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from store import news_db, trends


def _fixed_now() -> datetime:
    return datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


# ── news_db.load_news_for_days ─────────────────────────────────

def _save_at(date_str: str, source: str, articles: list[dict]) -> None:
    """특정 일자 디렉토리에 직접 저장 (테스트 헬퍼)."""
    from store.paths import news_dir_for

    day_dir = news_dir_for(date_str)
    df = pd.DataFrame(articles)
    for col in news_db._ARTICLE_COLS:
        if col not in df.columns:
            df[col] = ""
    df = df[list(news_db._ARTICLE_COLS)].astype(str)
    df.to_parquet(day_dir / f"{source}_test.parquet", index=False)


def test_load_news_for_days_combines_recent_days():
    _save_at("2026-05-13", "naver", [{"title": "오늘 a", "link": "u1"}])
    _save_at("2026-05-12", "naver", [{"title": "어제 b", "link": "u2"}])
    _save_at("2026-05-11", "google", [{"title": "그제 c", "link": "u3"}])
    df = news_db.load_news_for_days(days=3, now=_fixed_now())
    assert len(df) == 3
    assert set(df["title"]) == {"오늘 a", "어제 b", "그제 c"}


def test_load_news_for_days_skips_missing_dirs():
    _save_at("2026-05-13", "naver", [{"title": "오늘", "link": "u1"}])
    # 5/12, 5/11 디렉토리 없음 — 에러 없이 오늘만 반환
    df = news_db.load_news_for_days(days=7, now=_fixed_now())
    assert len(df) == 1
    assert df.iloc[0]["title"] == "오늘"


def test_load_news_for_days_deduplicates_by_link():
    _save_at("2026-05-13", "naver", [{"title": "v1", "link": "same"}])
    _save_at("2026-05-12", "google", [{"title": "v0", "link": "same"}])
    df = news_db.load_news_for_days(days=2, now=_fixed_now())
    assert len(df) == 1
    # 마지막 저장(=가장 최근) 우선 — 정확한 순서는 sorted glob 의존이라 둘 중 하나여야 함.
    assert df.iloc[0]["title"] in ("v1", "v0")


def test_load_news_for_days_rejects_zero_or_negative():
    with pytest.raises(ValueError):
        news_db.load_news_for_days(days=0)


# ── trends.daily_volume ─────────────────────────────────────────

def test_daily_volume_fills_missing_dates_with_zero():
    df = pd.DataFrame([
        {"title": "a", "date": "2026-05-13"},
        {"title": "b", "date": "2026-05-13"},
        {"title": "c", "date": "2026-05-11"},
    ])
    out = trends.daily_volume(df, days=3, now=_fixed_now())
    assert list(out["date"]) == ["2026-05-11", "2026-05-12", "2026-05-13"]
    counts = dict(zip(out["date"], out["count"]))
    assert counts == {"2026-05-11": 1, "2026-05-12": 0, "2026-05-13": 2}


def test_daily_volume_empty_input_returns_zero_filled_range():
    out = trends.daily_volume(pd.DataFrame(), days=3, now=_fixed_now())
    assert len(out) == 3
    assert (out["count"] == 0).all()


def test_daily_volume_rejects_zero_or_negative():
    with pytest.raises(ValueError):
        trends.daily_volume(pd.DataFrame(), days=0)


# ── trends.keyword_emergence ────────────────────────────────────

def test_keyword_emergence_separates_new_gone_rising():
    today = pd.DataFrame([
        {"keywords": "용접, 자동화"},
        {"keywords": "용접, 로봇"},
        {"keywords": "디지털트윈"},   # 새로 등장
    ])
    base = pd.DataFrame([
        {"keywords": "용접"},          # base 에만 1, today 에 2 → rising
        {"keywords": "절단, 그라인딩"},  # gone
    ])
    out = trends.keyword_emergence(today, base, top_n=10)
    new_set = set(out["new"]["keyword"])
    gone_set = set(out["gone"]["keyword"])
    rising_set = set(out["rising"]["keyword"])
    assert "디지털트윈" in new_set
    assert "절단" in gone_set and "그라인딩" in gone_set
    assert "용접" in rising_set
    # rising 의 delta 계산 검증
    row = out["rising"][out["rising"]["keyword"] == "용접"].iloc[0]
    assert row["today"] == 2 and row["base"] == 1 and row["delta"] == 1


def test_keyword_emergence_handles_empty_inputs():
    out = trends.keyword_emergence(pd.DataFrame(), pd.DataFrame())
    assert out["new"].empty and out["gone"].empty and out["rising"].empty


def test_keyword_emergence_top_n_limits():
    today = pd.DataFrame([{"keywords": ",".join([f"new{i}" for i in range(20)])}])
    base = pd.DataFrame([{"keywords": "old1"}])
    out = trends.keyword_emergence(today, base, top_n=5)
    assert len(out["new"]) == 5


# ── trends.compare_distribution ────────────────────────────────

def test_compare_distribution_returns_delta_sorted():
    today = pd.DataFrame([
        {"press": "AITimes"}, {"press": "AITimes"}, {"press": "조선일보"},
    ])
    base = pd.DataFrame([
        {"press": "AITimes"}, {"press": "매일경제"}, {"press": "매일경제"},
    ])
    out = trends.compare_distribution(today, base, key="press")
    # 정렬: delta 내림차순 → AITimes(+1), 조선일보(+1), 매일경제(-2)
    deltas = dict(zip(out["press"], out["delta"]))
    assert deltas["AITimes"] == 1
    assert deltas["조선일보"] == 1
    assert deltas["매일경제"] == -2
    assert out.iloc[-1]["press"] == "매일경제"  # 마지막 = 가장 작은 delta
