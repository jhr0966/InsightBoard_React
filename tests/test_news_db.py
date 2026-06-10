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
    assert "image_url" in df.columns

    all_df = load_all_today()
    assert len(all_df) == 2


def test_save_empty_returns_none():
    assert save_articles([], source="naver") is None


def test_score_matches_finds_overlap():
    news = pd.DataFrame(_sample_articles())
    tasks = pd.DataFrame([
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "전처리",
         "task": "강재선별", "sub_task": "크레인", "task_def": "", "sws_no": "", "sws_name": "강재 하역"},
        {"dept": "가공부", "lv1": "실행분과", "lv2": "구조내업", "lv3": "가공",
         "task": "절단", "sub_task": "강재 절단", "task_def": "", "sws_no": "", "sws_name": "절단 작업"},
    ])
    matches = score_matches(news, tasks, top_k=2)
    assert not matches.empty
    cutting = matches[matches["task"] == "절단"]
    assert not cutting.empty
    assert cutting.iloc[0]["link"] == "https://x.com/2"


# ── 데이터-계약 (C1: collected_at · C2: null→"") ──────────────

def test_collected_at_filled_from_enriched_then_published():
    """collected_at 정규화 — enriched_at 우선, 없으면 published_at (D4/C1)."""
    arts = [
        {"title": "a", "link": "l1", "source": "naver",
         "published_at": "2026-06-01T00:00:00", "enriched_at": "2026-06-02T09:00:00"},
        {"title": "b", "link": "l2", "source": "naver",
         "published_at": "2026-05-30T00:00:00"},  # enriched 없음 → published 폴백
    ]
    save_articles(arts, source="naver")
    df = load_latest(source="naver")
    assert "collected_at" in df.columns  # board 데일리 브리핑 select 컬럼 존재 (C1 회귀 방지)
    by = df.set_index("link")
    assert by.loc["l1", "collected_at"] == "2026-06-02T09:00:00"  # enriched 우선
    assert by.loc["l2", "collected_at"] == "2026-05-30T00:00:00"  # published 폴백


def test_missing_optional_field_is_empty_not_nan():
    """일부 기사에만 image_url 이 있어 NaN 이 생겨도 'nan' 문자열이 아닌 '' (C2)."""
    arts = [
        {"title": "a", "link": "l1", "source": "naver", "image_url": "http://x/a.jpg"},
        {"title": "b", "link": "l2", "source": "naver"},  # image_url 없음 → 혼합 NaN
    ]
    save_articles(arts, source="naver")
    by = load_latest(source="naver").set_index("link")
    assert by.loc["l1", "image_url"] == "http://x/a.jpg"
    assert by.loc["l2", "image_url"] == ""          # NaN → "" (not "nan")
    assert by.loc["l2", "summary"] == ""


# ── load_news_for_days 디스크 재읽기 memo (개선 백로그 #2) ──────

def test_load_news_for_days_memo_hit_invalidate_and_copy():
    from store.news_db import load_news_for_days
    save_articles([{"title": "a", "link": "l1", "source": "naver"}], source="naver")
    df1 = load_news_for_days(days=1)
    assert len(df1) == 1
    df1b = load_news_for_days(days=1)            # 캐시 hit
    assert len(df1b) == 1 and df1b is not df1    # .copy() → 다른 객체
    # 반환본을 변형해도 캐시는 오염되지 않는다
    df1b.loc[:, "title"] = "MUTATED"
    assert load_news_for_days(days=1).iloc[0]["title"] == "a"
    # 새 parquet 저장 → 디렉토리 mtime/수 변화 → 캐시 무효화 → 신규 반영
    save_articles([{"title": "b", "link": "l2", "source": "google"}], source="google")
    assert len(load_news_for_days(days=1)) == 2


def test_day_frame_memo_dedupes_disk_reads(monkeypatch, tmp_path):
    """윈도우(3/7/30일)가 달라도 같은 날짜 parquet 은 디스크에서 1회만 읽어야 한다."""
    import pandas as _pd
    from store import news_db

    news_db.save_articles(
        [{"title": "t1", "link": "https://a", "source": "naver"}], source="naver")

    calls = {"n": 0}
    real = _pd.read_parquet

    def counting(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(_pd, "read_parquet", counting)
    news_db._day_frame_memo.clear()
    news_db._news_window_memo.clear()

    news_db.load_news_for_days(days=3)
    news_db.load_news_for_days(days=7)
    news_db.load_news_for_days(days=30)
    news_db.load_all_today()
    assert calls["n"] == 1                      # 오늘 1개 파일 → 정확히 1회

    # 새 parquet 추가(수집) → 해당 일자만 재읽기(파일 2개 = +2회)
    news_db.save_articles(
        [{"title": "t2", "link": "https://b", "source": "google"}], source="google")
    df = news_db.load_news_for_days(days=7)
    assert calls["n"] == 3
    assert set(df["link"]) == {"https://a", "https://b"}  # 무효화 후 합본 정상
