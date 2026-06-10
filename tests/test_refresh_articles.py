"""scripts/refresh_articles.py — 저장 기사 일괄 재-enrich 배치.

네트워크 없음: enrich.fetch_article 은 전부 mock. 데이터는 conftest 의
autouse `_isolated_data_dirs` 가 라우팅한 tmp data 디렉토리만 사용.
"""
from __future__ import annotations

import pandas as pd
import pytest

from scripts import refresh_articles
from store import news_db
from store.paths import news_dir_for


# 80자(_MIN_CONTENT_LEN) 이상 + 한국어 산문 → content_needs_refresh = False
_GOOD_BODY = "조선소 용접 자동화 기술이 빠르게 확산되고 있다. 비전 검사와 협동 로봇이 현장 적용 단계에 들어섰다. " * 3
# fetch 가 돌려줄 새 본문 (충분히 긴 정상 산문)
_FETCHED_BODY = "재수집된 본문이다. 용접 비드 품질을 머신비전으로 검사하는 체계가 도입되어 검사 시간이 크게 줄었다. " * 3


def _seed(articles, *, source="naver", stamp="100000Z", monkeypatch=None):
    """오늘자 tmp 디렉토리에 결정적 파일명으로 seed 저장."""
    assert monkeypatch is not None
    monkeypatch.setattr(news_db, "_utc_stamp", lambda: stamp)
    return news_db.save_articles(articles, source=source)


def _parquet_count() -> int:
    return len(list(news_dir_for().glob("*.parquet")))


# ── 선별 로직 (디스크 불필요) ────────────────────────────────

def test_select_candidates_picks_short_content_and_missing_image():
    df = pd.DataFrame([
        {"link": "http://x/short", "content": "", "image_url": "http://img/1", "source": "naver"},
        {"link": "http://x/noimg", "content": _GOOD_BODY, "image_url": "", "source": "naver"},
        {"link": "http://x/good", "content": _GOOD_BODY, "image_url": "http://img/2", "source": "naver"},
        {"link": "http://x/both", "content": "짧음", "image_url": "nan", "source": "google"},
    ])
    cands, no_link = refresh_articles.select_candidates(df)
    by_link = {rec["link"]: reason for rec, reason in cands}
    assert by_link == {
        "http://x/short": "본문",
        "http://x/noimg": "이미지",
        "http://x/both": "본문+이미지",
    }
    assert "http://x/good" not in by_link        # 본문·이미지 모두 정상 → 제외
    assert no_link == 0


def test_select_candidates_excludes_rows_without_fetchable_link():
    df = pd.DataFrame([
        {"link": "", "content": "", "image_url": "", "source": "naver"},
        {"link": "not-a-url", "content": "", "image_url": "", "source": "naver"},
        {"link": "http://x/a", "content": "", "image_url": "", "source": "naver"},
    ])
    cands, no_link = refresh_articles.select_candidates(df)
    assert [rec["link"] for rec, _ in cands] == ["http://x/a"]
    assert no_link == 2


def test_select_candidates_empty_df():
    cands, no_link = refresh_articles.select_candidates(pd.DataFrame())
    assert cands == [] and no_link == 0


# ── dry-run — fetch/저장이 일절 없어야 ───────────────────────

def test_dry_run_prints_selection_and_writes_nothing(monkeypatch, capsys):
    _seed([
        {"title": "본문 빈 기사", "link": "http://x/empty", "content": "",
         "image_url": "", "source": "naver"},
    ], monkeypatch=monkeypatch)
    before = _parquet_count()

    def _boom(url, **kwargs):  # noqa: ARG001
        raise AssertionError("dry-run 에서 fetch_article 이 호출되면 안 됨")

    monkeypatch.setattr(refresh_articles.enrich, "fetch_article", _boom)
    rc = refresh_articles.main(["--days", "1", "--dry-run"])
    assert rc == 0
    assert _parquet_count() == before            # 새 parquet 없음
    out = capsys.readouterr().out
    assert "후보 1건" in out
    assert "http://x/empty" in out
    assert "dry-run" in out


# ── 갱신 + 영속화 roundtrip (tmp data dir) ───────────────────

def test_refresh_updates_and_persists_roundtrip(monkeypatch, capsys):
    _seed([
        {"title": "고장 기사", "link": "http://x/broken", "content": "",
         "image_url": "", "source": "naver",
         "keywords_llm": "용접, 비전", "summary_llm": "기존 LLM 요약"},
        {"title": "멀쩡 기사", "link": "http://x/fine", "content": _GOOD_BODY,
         "image_url": "http://img/ok.jpg", "source": "naver"},
    ], monkeypatch=monkeypatch)

    calls: list[str] = []

    def _fake_fetch(url, **kwargs):  # noqa: ARG001
        calls.append(url)
        return {"content": _FETCHED_BODY, "image_url": "http://img/new.jpg"}

    monkeypatch.setattr(refresh_articles.enrich, "fetch_article", _fake_fetch)
    # upsert 파일이 seed(100000Z)보다 뒤 이름이 되게 — keep="last" 가 갱신본을 남긴다
    monkeypatch.setattr(news_db, "_utc_stamp", lambda: "120000Z")

    rc = refresh_articles.main(["--days", "1"])
    assert rc == 0
    assert calls == ["http://x/broken"]          # 멀쩡 기사는 fetch 안 함

    df = news_db.load_news_for_days(days=1)
    assert len(df) == 2                          # link dedup — 중복 없이 대체
    broken = df[df["link"] == "http://x/broken"].iloc[0]
    assert broken["content"] == _FETCHED_BODY
    assert broken["image_url"] == "http://img/new.jpg"
    # LLM 산출·원본 컬럼은 그대로 (NO LLM)
    assert broken["keywords_llm"] == "용접, 비전"
    assert broken["summary_llm"] == "기존 LLM 요약"
    assert broken["title"] == "고장 기사"
    fine = df[df["link"] == "http://x/fine"].iloc[0]
    assert fine["content"] == _GOOD_BODY         # 비후보는 건드리지 않음

    out = capsys.readouterr().out
    assert "[OK  ]" in out and "갱신 1" in out


def test_refresh_image_only_keeps_existing_good_content(monkeypatch):
    _seed([
        {"title": "이미지만 없음", "link": "http://x/noimg", "content": _GOOD_BODY,
         "image_url": "", "source": "google"},
    ], source="google", monkeypatch=monkeypatch)
    monkeypatch.setattr(
        refresh_articles.enrich, "fetch_article",
        lambda url, **k: {"content": "짧고 다른 본문", "image_url": "http://img/x.jpg"})
    monkeypatch.setattr(news_db, "_utc_stamp", lambda: "120000Z")

    assert refresh_articles.main(["--days", "1"]) == 0
    row = news_db.load_news_for_days(days=1).iloc[0]
    assert row["image_url"] == "http://img/x.jpg"
    assert row["content"] == _GOOD_BODY          # 멀쩡한 본문은 fetch 로 덮지 않음


def test_refresh_skips_when_fetch_empty_and_writes_nothing(monkeypatch, capsys):
    _seed([
        {"title": "여전히 실패", "link": "http://x/fail", "content": "",
         "image_url": "", "source": "naver"},
    ], monkeypatch=monkeypatch)
    before = _parquet_count()
    monkeypatch.setattr(refresh_articles.enrich, "fetch_article",
                        lambda url, **k: {"content": "", "image_url": ""})
    assert refresh_articles.main(["--days", "1"]) == 0
    assert _parquet_count() == before            # 갱신 0건 → upsert 없음
    out = capsys.readouterr().out
    assert "[SKIP]" in out and "변화없음 1" in out


def test_limit_caps_processed_count(monkeypatch, capsys):
    _seed([
        {"title": f"기사{i}", "link": f"http://x/{i}", "content": "",
         "image_url": "", "source": "naver"}
        for i in range(3)
    ], monkeypatch=monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        refresh_articles.enrich, "fetch_article",
        lambda url, **k: (calls.append(url),
                          {"content": _FETCHED_BODY, "image_url": "http://i/x.jpg"})[1])
    monkeypatch.setattr(news_db, "_utc_stamp", lambda: "120000Z")

    assert refresh_articles.main(["--days", "1", "--limit", "1"]) == 0
    assert len(calls) == 1
    out = capsys.readouterr().out
    assert "후보 3건" in out and "1건만 처리" in out


def test_persist_groups_by_source(monkeypatch):
    """source 가 섞인 갱신분 → 소스별 upsert_articles 1회씩."""
    seen: list[tuple[str, int]] = []

    def _fake_upsert(rows, *, source):
        seen.append((source, len(rows)))
        return None

    monkeypatch.setattr(refresh_articles.news_db, "upsert_articles", _fake_upsert)
    updated = [
        {"link": "http://a", "source": "naver"},
        {"link": "http://b", "source": "google"},
        {"link": "http://c", "source": "naver"},
        {"link": "http://d", "source": ""},       # 빈 source → unknown 폴백
    ]
    saved = refresh_articles.persist_updates(updated)
    assert saved == {"naver": 2, "google": 1, "unknown": 1}
    assert sorted(seen) == [("google", 1), ("naver", 2), ("unknown", 1)]


def test_days_must_be_positive():
    assert refresh_articles.main(["--days", "0"]) == 2
