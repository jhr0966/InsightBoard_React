"""뉴스 조회 결정적 최신순 계약 회귀 테스트 (`fix-news-ordering`).

버그 배경: load_news_for_days 는 일자 프레임을 과거→오늘 순으로 concat 만 하고
정렬하지 않았다 → 다운스트림 head(limit) 이 "가장 오래된" 기사를 취했고,
윈도우 기사 수가 limit 를 넘으면 최신 날짜 기사가 통째로 잘렸다.
계약(모듈 docstring): sort_at desc + link asc, 파싱 실패 행도 유실 없이 맨 뒤.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api.main import app
from store import news_db

client = TestClient(app)

_NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _iso(**delta) -> str:
    return (_NOW - timedelta(**delta)).isoformat()


def _clear_memos():
    news_db._day_frame_memo.clear()
    news_db._news_window_memo.clear()


def _write_day(day: str, articles: list[dict], *, fname: str = "naver_000001Z.parquet"):
    """지정 일자 디렉토리에 직접 parquet 저장 (과거 일자 시드용)."""
    from config import NEWS_DIR

    day_dir = NEWS_DIR / day
    day_dir.mkdir(parents=True, exist_ok=True)
    news_db._to_df(articles).to_parquet(day_dir / fname, index=False)


def test_newest_first_across_days():
    """① 과거→오늘 순으로 로드돼도 최신 기사가 먼저 나온다."""
    yday = (_NOW - timedelta(days=1)).strftime("%Y-%m-%d")
    _write_day(yday, [{"title": "어제 기사", "link": "https://x/old", "source": "naver",
                       "published_at": _iso(days=1)}])
    news_db.save_articles([{"title": "오늘 기사", "link": "https://x/new", "source": "naver",
                            "published_at": _iso(hours=1)}], source="naver")
    _clear_memos()
    df = news_db.load_news_for_days(days=7)
    assert list(df["link"]) == ["https://x/new", "https://x/old"]


def test_limit_keeps_latest_day_articles():
    """② 윈도우 기사 수 > limit 여도 가장 최근 날짜 기사가 살아남는다 (핵심 회귀)."""
    yday = (_NOW - timedelta(days=1)).strftime("%Y-%m-%d")
    _write_day(yday, [
        {"title": f"어제{i}", "link": f"https://x/y{i}", "source": "naver",
         "published_at": _iso(days=1, minutes=i)} for i in range(3)
    ])
    news_db.save_articles([{"title": "오늘 최신", "link": "https://x/today", "source": "naver",
                            "published_at": _iso(minutes=5)}], source="naver")
    _clear_memos()
    res = client.get("/api/news", params={"days": 7, "limit": 2})
    assert res.status_code == 200
    links = [r["link"] for r in res.json()]
    assert len(links) == 2
    assert links[0] == "https://x/today"  # 과거엔 어제 기사 2건이 반환되고 오늘이 잘렸다


def test_mixed_timestamp_formats_sort_chronologically():
    """③ ISO+offset · RFC822 · date-only 혼재 포맷이 실제 시간순으로 정렬된다."""
    news_db.save_articles([
        # 01:00 UTC (KST 10:00, offset 유지형 — google/rss 출력)
        {"title": "b", "link": "https://x/b", "source": "google",
         "published_at": "2026-06-22T10:00:00+09:00"},
        # 02:00 UTC (RFC822 — 과거 데이터)
        {"title": "a", "link": "https://x/a", "source": "naver",
         "published_at": "Mon, 22 Jun 2026 11:00:00 +0900"},
        # 00:00 UTC (date-only → UTC 자정 간주)
        {"title": "c", "link": "https://x/c", "source": "naver",
         "published_at": "2026-06-22"},
    ], source="naver")
    _clear_memos()
    df = news_db.load_all_today()
    assert list(df["link"]) == ["https://x/a", "https://x/b", "https://x/c"]
    # 정규화 컬럼은 전부 UTC ISO 로 통일
    assert df.iloc[0]["sort_at"].endswith("+00:00")


def test_sort_falls_back_to_collected_at_then_day():
    """④ published_at 이 없으면 collected_at, 둘 다 없으면 일자 디렉토리 날짜로 폴백.

    파싱 실패/시각 전무 행도 목록에서 사라지지 않는다(맨 뒤 배치).
    """
    yday = (_NOW - timedelta(days=1)).strftime("%Y-%m-%d")
    _write_day(yday, [
        # 시각 전무 — sort_at = 어제 날짜 자정 폴백 (레거시 parquet 시뮬레이션)
        {"title": "no-ts", "link": "https://x/none", "source": "naver"},
    ])
    news_db.save_articles([
        # published 없음 → collected_at(=enriched_at 폴백 규칙으로 채워짐) 사용
        {"title": "col", "link": "https://x/col", "source": "naver",
         "enriched_at": _iso(hours=2)},
        {"title": "pub", "link": "https://x/pub", "source": "naver",
         "published_at": _iso(hours=1)},
    ], source="naver")
    _clear_memos()
    df = news_db.load_news_for_days(days=7)
    assert list(df["link"]) == ["https://x/pub", "https://x/col", "https://x/none"]
    assert set(df["link"]) == {"https://x/pub", "https://x/col", "https://x/none"}  # 유실 없음


def test_equal_sort_at_ties_break_by_link_deterministically():
    """⑤ 같은 시간값이어도 link 오름차순 tie-break 로 매번 같은 순서."""
    ts = _iso(hours=3)
    news_db.save_articles([
        {"title": "z", "link": "https://x/zz", "source": "naver", "published_at": ts},
        {"title": "a", "link": "https://x/aa", "source": "naver", "published_at": ts},
        {"title": "m", "link": "https://x/mm", "source": "naver", "published_at": ts},
    ], source="naver")
    orders = []
    for _ in range(3):
        _clear_memos()  # 메모이즈 우회 — 재계산해도 동일해야 진짜 결정적
        orders.append(list(news_db.load_news_for_days(days=1)["link"]))
    assert orders[0] == ["https://x/aa", "https://x/mm", "https://x/zz"]
    assert orders[0] == orders[1] == orders[2]


def test_today_endpoint_is_deterministic_and_newest_first():
    """⑥ /api/news/today (load_all_today) 도 결정적 최신순을 보장한다."""
    news_db.save_articles([{"title": "old", "link": "https://x/1", "source": "aitimes",
                            "published_at": _iso(hours=9)}], source="aitimes")
    # 파일명 사전순(aitimes < naver)과 무관하게 시간이 이겨야 한다
    news_db.save_articles([{"title": "new", "link": "https://x/2", "source": "naver",
                            "published_at": _iso(hours=1)}], source="naver")
    _clear_memos()
    first = client.get("/api/news/today").json()
    _clear_memos()
    second = client.get("/api/news/today").json()
    assert [r["link"] for r in first] == ["https://x/2", "https://x/1"]
    assert first == second
