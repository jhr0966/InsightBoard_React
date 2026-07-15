"""기사 식별(article_id·URL 정규화) + 필드 단위 중복 병합 (Step 2) 회귀 테스트."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from store import news_db
from store.article_id import IDENTITY_VERSION, article_id, canonical_url

_NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _iso(**delta) -> str:
    return (_NOW - timedelta(**delta)).isoformat()


def _clear_memos():
    news_db._day_frame_memo.clear()
    news_db._news_window_memo.clear()


def _save(articles: list[dict], fname: str):
    """오늘 디렉토리에 고유 파일명으로 저장.

    save_articles 는 파일명이 `{source}_{HHMMSSZ}` 라 같은 초 내 같은 소스 재저장이
    덮어써진다(알려진 한계 — run_daily docstring). 병합 테스트는 레코드가 각각
    남아야 하므로 파일명을 직접 지정한다.
    """
    from store.paths import news_dir_for

    news_db._to_df(articles).to_parquet(news_dir_for() / f"{fname}.parquet", index=False)


# ── URL 정규화 ──────────────────────────────────────────────

def test_tracking_params_removed_same_id():
    """추적 파라미터(utm/fbclid/gclid)만 다른 URL 은 같은 article_id."""
    base = "https://news.example.com/article?idxno=123"
    variants = [
        base,
        base + "&utm_source=news&utm_medium=rss",
        base + "&fbclid=abc123",
        base + "&gclid=xyz&utm_campaign=daily",
        "https://NEWS.example.com/article?idxno=123#comment",  # 호스트 대소문자·fragment
    ]
    ids = {article_id(u) for u in variants}
    assert len(ids) == 1


def test_identifying_params_kept_different_id():
    """기사 식별 파라미터(idxno·articleId 등)는 유지 — 다른 기사는 다른 ID (오합침 금지)."""
    assert article_id("https://n.com/read?idxno=1") != article_id("https://n.com/read?idxno=2")
    assert article_id("https://n.com/news?articleId=100") != article_id("https://n.com/news?articleId=101")
    assert article_id("https://n.com/a?id=7&seq=1") != article_id("https://n.com/a?id=7&seq=2")


def test_collision_distinct_articles():
    """경로·도메인이 다른 기사는 절대 합쳐지지 않는다 (충돌 가드)."""
    urls = [
        "https://a.com/news/1", "https://a.com/news/2",
        "https://b.com/news/1", "https://a.com/news/1/photo",
    ]
    assert len({article_id(u) for u in urls}) == len(urls)


def test_param_order_and_trailing_slash_normalized():
    assert canonical_url("https://a.com/x?b=2&a=1") == canonical_url("https://a.com/x/?a=1&b=2")


def test_bad_or_empty_url_safe():
    assert article_id("") == ""
    assert article_id("not a url") != ""  # 원문 그대로 해시 — 크래시 없음
    assert IDENTITY_VERSION >= 1


# ── 필드 단위 병합 ──────────────────────────────────────────

def _load7():
    _clear_memos()
    return news_db.load_news_for_days(days=7)


def test_merge_combines_time_content_image_across_records():
    """정확한 게시시각(레코드1)·본문(레코드2)·이미지(레코드3)가 한 행으로 병합된다."""
    link = "https://x.com/art?utm_source=rss"
    link_clean = "https://x.com/art"
    _save([{  # ① 원본: 게시시각만 정확, 본문 없음
        "title": "원본", "link": link, "source": "naver",
        "published_at": _iso(hours=5),
    }], "naver_000001Z")
    _save([{  # ② 보강: 본문만 풍부 (추적 파라미터 제거된 URL)
        "title": "보강", "link": link_clean, "source": "naver",
        "content": "풍부한 본문 " * 30,
    }], "naver_000002Z")
    _save([{  # ③ 재보강: 이미지 + LLM 키워드
        "title": "재보강", "link": link_clean, "source": "naver",
        "image_url": "https://x.com/img.jpg", "keywords_llm": "용접, 로봇",
        "enriched_at": _iso(hours=1),
    }], "naver_000003Z")

    df = _load7()
    assert len(df) == 1                                   # 3개 레코드 → 1행
    row = df.iloc[0]
    assert row["published_at_norm"] == _iso(hours=5)      # ①의 게시시각 보존
    assert "풍부한 본문" in row["content"]                  # ②의 본문 보존
    assert row["image_url"] == "https://x.com/img.jpg"    # ③의 이미지 보존
    assert row["keywords_llm"] == "용접, 로봇"              # ③의 최신 LLM 결과
    assert int(row["merged_record_count"]) == 3
    assert link in row["original_urls"] and link_clean in row["original_urls"]


def test_merge_pre_and_post_enrich_duplicates():
    """enrich 이전/이후 레코드 중복 — 본문은 enrich 본, 게시시각은 원본."""
    _save([{"title": "t", "link": "https://y.com/1", "source": "google",
            "published_at": _iso(hours=9), "content": ""}], "google_000001Z")
    _save([{"title": "t", "link": "https://y.com/1", "source": "google",
            "content": "enrich 본문 " * 20,
            "enriched_at": _iso(hours=2)}], "google_000002Z")
    df = _load7()
    assert len(df) == 1
    assert "enrich 본문" in df.iloc[0]["content"]
    assert df.iloc[0]["published_at_norm"] == _iso(hours=9)


def test_no_merge_without_link():
    """link 없는 행들은 서로 합쳐지지 않고 전부 남는다 (과거 link dedup 은 전부 붕괴시켰음)."""
    news_db.save_articles([
        {"title": "a", "link": "", "source": "naver"},
        {"title": "b", "link": "", "source": "naver"},
    ], source="naver")
    df = _load7()
    assert set(df["title"]) == {"a", "b"}


def test_merge_deterministic_and_idempotent():
    """같은 데이터를 두 번 로드해도 동일 결과 (병합·정렬 결정성)."""
    _save([
        {"title": "p", "link": "https://z.com/1?utm_source=a", "source": "naver",
         "published_at": _iso(hours=3)},
        {"title": "q", "link": "https://z.com/1", "source": "naver",
         "content": "본문 " * 30},
        {"title": "r", "link": "https://z.com/2", "source": "naver",
         "published_at": _iso(hours=1)},
    ], "naver_000001Z")
    a = _load7()
    b = _load7()
    assert list(a["article_id"]) == list(b["article_id"])
    assert list(a["content"]) == list(b["content"])
    assert len(a) == 2 and a.iloc[0]["link"].endswith("/2")  # 최신순 유지


def test_sorted_by_merged_published_time():
    """병합 후 sort_at 은 병합된 게시시각 기준으로 재산출된다."""
    # 기사 A: 첫 레코드에만 게시시각(4h 전), 둘째 레코드는 시각 없음(본문만)
    _save([{"title": "A1", "link": "https://s.com/a", "source": "naver",
            "published_at": _iso(hours=4)}], "naver_000001Z")
    _save([{"title": "A2", "link": "https://s.com/a", "source": "naver",
            "content": "본문 " * 30}], "naver_000002Z")
    # 기사 B: 6h 전 게시 — A(4h 전)보다 오래됨
    _save([{"title": "B", "link": "https://s.com/b", "source": "naver",
            "published_at": _iso(hours=6)}], "naver_000003Z")
    df = _load7()
    assert list(df["link"]) == ["https://s.com/a", "https://s.com/b"]
