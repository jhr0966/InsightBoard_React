"""뉴스 목록 커서 페이지네이션 (Step 3 `feat-news-pagination`) 회귀 테스트.

커서 = 정렬키 그대로 `"{sort_at}::{link}"` (I-14: sort_at desc·link asc).
offset 과 달리 페이지 사이에 새 수집이 끼어들어도 중복·누락이 없어야 한다.
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


def _seed(n: int, *, fname: str = "naver_000001Z"):
    from store.paths import news_dir_for

    arts = [{"title": f"기사{i}", "link": f"https://x.com/{i}", "source": "naver",
             "published_at": _iso(minutes=i)} for i in range(n)]
    news_db._to_df(arts).to_parquet(news_dir_for() / f"{fname}.parquet", index=False)
    _clear_memos()


def _page(**params) -> dict:
    res = client.get("/api/news", params=params)
    assert res.status_code == 200
    return res.json()


def test_cursor_walk_covers_all_without_dup_or_miss():
    """커서로 끝까지 걸으면 전체가 정확히 1번씩, 최신순으로 나온다."""
    _seed(7)
    seen: list[str] = []
    cursor = None
    for _ in range(10):  # 무한루프 가드
        page = _page(days=7, limit=3, **({"cursor": cursor} if cursor else {}))
        seen.extend(r["link"] for r in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == [f"https://x.com/{i}" for i in range(7)]  # 최신(0분 전)→과거
    assert len(set(seen)) == 7


def test_cursor_stable_when_new_articles_arrive():
    """1페이지 조회 후 **새 기사가 수집돼도** 2페이지에 중복·누락이 없다.

    offset 방식이면 새 기사가 앞에 끼며 1페이지 마지막 항목이 2페이지에
    중복됐을 것 — 커서(정렬키 기준)는 흔들리지 않는다.
    """
    _seed(4, fname="naver_000001Z")
    p1 = _page(days=7, limit=2)
    assert [r["title"] for r in p1["items"]] == ["기사0", "기사1"]
    # 사이에 더 최신 기사 도착
    from store.paths import news_dir_for

    news_db._to_df([{"title": "속보", "link": "https://x.com/new", "source": "naver",
                     "published_at": _iso(seconds=1)}]).to_parquet(
        news_dir_for() / "naver_000002Z.parquet", index=False)
    _clear_memos()
    p2 = _page(days=7, limit=2, cursor=p1["next_cursor"])
    assert [r["title"] for r in p2["items"]] == ["기사2", "기사3"]  # 중복·누락 없음


def test_last_page_next_cursor_null():
    _seed(3)
    page = _page(days=7, limit=10)
    assert len(page["items"]) == 3 and page["next_cursor"] is None
    # 정확히 limit 로 끝나는 경우 — 마지막 페이지에서 커서가 닫혀야 한다
    page = _page(days=7, limit=3)
    assert page["next_cursor"] is None


def test_bad_cursor_returns_400():
    _seed(1)
    assert client.get("/api/news", params={"cursor": "이상한값"}).status_code == 400


def test_source_filter_with_cursor():
    """출처 필터와 커서가 함께 동작한다."""
    from store.paths import news_dir_for

    arts = ([{"title": f"n{i}", "link": f"https://n.com/{i}", "source": "naver",
              "published_at": _iso(minutes=i)} for i in range(3)]
            + [{"title": "g", "link": "https://g.com/1", "source": "google",
                "published_at": _iso(minutes=1, seconds=30)}])
    news_db._to_df(arts).to_parquet(news_dir_for() / "mix_000001Z.parquet", index=False)
    _clear_memos()
    p1 = _page(days=7, limit=2, source="naver")
    p2 = _page(days=7, limit=2, source="naver", cursor=p1["next_cursor"])
    got = [r["link"] for r in p1["items"] + p2["items"]]
    assert got == ["https://n.com/0", "https://n.com/1", "https://n.com/2"]
