"""M3 — 캐시 / 트렌드 / 채팅 영구화 단위 테스트."""
from __future__ import annotations

import pandas as pd

from store import cache, chat_log, trends


def test_cache_roundtrip():
    key = cache.make_key("a", "b")
    assert cache.get(key) is None
    cache.put(key, "hello")
    assert cache.get(key) == "hello"


def test_cache_make_key_stable_and_distinct():
    k1 = cache.make_key("dept", "news A | news B")
    k2 = cache.make_key("dept", "news A | news B")
    k3 = cache.make_key("dept", "news A | news C")
    assert k1 == k2 and k1 != k3


def test_cache_clear():
    cache.put(cache.make_key("x"), "1")
    cache.put(cache.make_key("y"), "2")
    n = cache.clear()
    assert n >= 2
    assert cache.get(cache.make_key("x")) is None


def test_trends_by_date_uses_published_at():
    df = pd.DataFrame([
        {"published_at": "2026-05-12T09:00:00+00:00", "date": "1시간 전"},
        {"published_at": "2026-05-12T11:00:00+00:00", "date": "30분 전"},
        {"published_at": "2026-05-11T10:00:00+00:00", "date": "1일 전"},
    ])
    out = trends.by_date(df)
    assert list(out.columns) == ["date", "count"]
    assert out.iloc[0]["date"] == "2026-05-11"
    assert int(out.loc[out["date"] == "2026-05-12", "count"].iloc[0]) == 2


def test_trends_by_source_counts():
    df = pd.DataFrame([
        {"source": "naver"}, {"source": "naver"}, {"source": "google"},
    ])
    out = trends.by_source(df)
    assert out.iloc[0]["source"] == "naver"
    assert int(out.iloc[0]["count"]) == 2


def test_trends_top_keywords():
    df = pd.DataFrame([
        {"keywords": "자동화, 용접, 로봇"},
        {"keywords": "자동화, 디지털"},
        {"keywords": ""},
    ])
    out = trends.top_keywords(df, top_n=5)
    top = out.iloc[0]
    assert top["keyword"] == "자동화" and int(top["count"]) == 2


def test_chat_log_save_load_roundtrip():
    msgs = [
        {"role": "user", "content": "안녕"},
        {"role": "assistant", "content": "안녕하세요."},
    ]
    chat_log.save_history(msgs)
    out = chat_log.load_history()
    assert out == msgs
    chat_log.reset()
    assert chat_log.load_history() == []


def test_chat_log_load_handles_missing_file():
    chat_log.reset()
    assert chat_log.load_history() == []


# ── 키워드 불용어 필터 (2026-06-11) ──────────────────────────

def test_top_keywords_drops_korean_stopwords():
    """'것으로'·'등'·'관련' 같은 문법 조각/불용어는 키워드 집계에서 제외."""
    import pandas as pd
    from store import trends
    df = pd.DataFrame({
        "keywords": [
            "용접 로봇, 것으로, 자동화",
            "비전 검사, 등, 관련, 자동화",
            "것으로, 가, 용접 로봇",
        ],
    })
    top = trends.top_keywords(df, top_n=10)
    kws = top["keyword"].tolist()
    assert "용접 로봇" in kws and "자동화" in kws and "비전 검사" in kws
    for junk in ("것으로", "등", "관련", "가"):
        assert junk not in kws, f"불용어 {junk} 가 키워드에 남음"


def test_is_meaningful_keyword_rules():
    from store import trends
    assert trends._is_meaningful_keyword("용접 로봇")
    assert trends._is_meaningful_keyword("AI")
    assert not trends._is_meaningful_keyword("것으로")
    assert not trends._is_meaningful_keyword("가")          # 한 글자 한글
    assert not trends._is_meaningful_keyword("···")         # 순수 기호
    assert not trends._is_meaningful_keyword("")
