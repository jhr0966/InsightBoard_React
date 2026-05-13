"""Phase 6-B 후속: scripts.daily_scrape 의 enrich 자동 호출 단위 테스트.

네트워크/LLM 없이 monkeypatch 로 collect_batch + fetch_content + LLM 호출을 가짜로 대체.
"""
from __future__ import annotations

from scraping import run_daily
from store import news_db


def _seed_today_news(*, with_content: bool = False) -> None:
    """conftest 의 tmp NEWS_DIR 안에 오늘자 parquet 시드."""
    articles = [
        {
            "title": f"제목-{i}",
            "press": "조선",
            "date": "2026-05-13",
            "link": f"https://ex.example/{i}",
            "summary": "",
            "source": "naver",
            "content": ("본문 " * 30) if with_content else "",
        }
        for i in range(3)
    ]
    news_db.save_articles(articles, source="naver")


def _fake_fetch_content(url: str, *, session=None) -> str:
    return "본문 텍스트 " * 20


def test_main_invokes_enrich_when_articles_collected(monkeypatch):
    """collect_batch 가 기사를 저장하면 enrich 단계가 호출되고 LLM 미사용으로 진행."""
    _seed_today_news(with_content=False)

    def _fake_collect(keywords, *, sources, max_results, on_step=None):
        # 실제 저장은 시드에서 했으니, summary_lines 만 의미 있는 report 리턴
        return run_daily.CollectionReport(
            saved=[{"source": "naver", "keywords": list(keywords), "count": 3, "path": "x"}],
            errors=[],
        )

    from scripts import daily_scrape
    from scraping import enrich as enrich_mod

    monkeypatch.setattr(daily_scrape, "collect_batch", _fake_collect)
    monkeypatch.setattr(enrich_mod, "fetch_content", _fake_fetch_content)

    rc = daily_scrape.main(["--keywords", "로봇", "--no-llm", "--enrich-max", "10"])
    assert rc == 0

    df = news_db.load_all_today()
    # 모든 시드 기사가 본문 확보 (50자 이상)
    assert (df["content"].str.len() >= 50).all()
    # source 컬럼 보존 — upsert 동작
    assert "naver" in df["source"].values


def test_main_skips_enrich_when_enrich_max_zero(monkeypatch):
    """--enrich-max 0 이면 enrich 호출 안 함."""
    _seed_today_news(with_content=False)

    def _fake_collect(keywords, *, sources, max_results, on_step=None):
        return run_daily.CollectionReport(
            saved=[{"source": "naver", "keywords": list(keywords), "count": 3, "path": "x"}],
        )

    called = {"enrich": 0}

    def _spy_enrich(*a, **kw):
        called["enrich"] += 1
        return list(a[0]) if a else []

    from scripts import daily_scrape
    from scraping import enrich as enrich_mod

    monkeypatch.setattr(daily_scrape, "collect_batch", _fake_collect)
    monkeypatch.setattr(enrich_mod, "enrich_articles", _spy_enrich)

    rc = daily_scrape.main(["--keywords", "로봇", "--enrich-max", "0"])
    assert rc == 0
    assert called["enrich"] == 0


def test_main_skips_enrich_when_total_zero(monkeypatch):
    """수집 결과 0건이면 enrich 단계 자체 호출 안 함 (불필요 IO 방지)."""

    def _fake_collect(keywords, *, sources, max_results, on_step=None):
        return run_daily.CollectionReport(saved=[], errors=[])

    called = {"enrich": 0}

    def _spy_enrich(*a, **kw):
        called["enrich"] += 1
        return list(a[0]) if a else []

    from scripts import daily_scrape
    from scraping import enrich as enrich_mod

    monkeypatch.setattr(daily_scrape, "collect_batch", _fake_collect)
    monkeypatch.setattr(enrich_mod, "enrich_articles", _spy_enrich)

    rc = daily_scrape.main(["--keywords", "로봇"])
    assert rc == 0
    assert called["enrich"] == 0


def test_main_enrich_failure_isolated(monkeypatch):
    """enrich 단계가 raise 해도 main 은 exit 0 (cron 안정성)."""
    _seed_today_news(with_content=False)

    def _fake_collect(keywords, *, sources, max_results, on_step=None):
        return run_daily.CollectionReport(
            saved=[{"source": "naver", "keywords": list(keywords), "count": 3, "path": "x"}],
        )

    def _boom(*a, **kw):
        raise RuntimeError("LLM 서버 다운")

    from scripts import daily_scrape
    from scraping import enrich as enrich_mod

    monkeypatch.setattr(daily_scrape, "collect_batch", _fake_collect)
    monkeypatch.setattr(enrich_mod, "enrich_articles", _boom)

    rc = daily_scrape.main(["--keywords", "로봇", "--enrich-max", "5"])
    assert rc == 0


def test_main_enrich_max_caps_batch_size(monkeypatch):
    """--enrich-max N 이 enrich 대상 기사 수를 N 으로 제한."""
    _seed_today_news(with_content=False)  # 3건 시드

    def _fake_collect(keywords, *, sources, max_results, on_step=None):
        return run_daily.CollectionReport(
            saved=[{"source": "naver", "keywords": list(keywords), "count": 3, "path": "x"}],
        )

    seen_batch_size = {"n": -1}

    def _spy_enrich(articles, *, with_llm=True, progress_cb=None):
        seen_batch_size["n"] = len(articles)
        for a in articles:
            a["content"] = "본문 텍스트 " * 20
        return articles

    from scripts import daily_scrape
    from scraping import enrich as enrich_mod

    monkeypatch.setattr(daily_scrape, "collect_batch", _fake_collect)
    monkeypatch.setattr(enrich_mod, "enrich_articles", _spy_enrich)

    rc = daily_scrape.main(["--keywords", "로봇", "--enrich-max", "2"])
    assert rc == 0
    assert seen_batch_size["n"] == 2


def _run_with_flag_and_capture_with_llm(monkeypatch, extra_args):
    """공통 헬퍼: cron 한 번 실행 후 enrich 의 with_llm 인자 캡처."""
    _seed_today_news(with_content=False)

    def _fake_collect(keywords, *, sources, max_results, on_step=None):
        return run_daily.CollectionReport(
            saved=[{"source": "naver", "keywords": list(keywords), "count": 3, "path": "x"}],
        )

    seen = {"v": None}

    def _spy_enrich(articles, *, with_llm=True, progress_cb=None):
        seen["v"] = with_llm
        for a in articles:
            a["content"] = "본문 텍스트 " * 20
        return articles

    from scripts import daily_scrape
    from scraping import enrich as enrich_mod

    monkeypatch.setattr(daily_scrape, "collect_batch", _fake_collect)
    monkeypatch.setattr(enrich_mod, "enrich_articles", _spy_enrich)

    daily_scrape.main(["--keywords", "로봇", "--enrich-max", "5", *extra_args])
    return seen["v"]


def test_main_enrich_no_llm_flag_forwarded(monkeypatch):
    """--no-llm 이 enrich_articles 의 with_llm=False 로 전달."""
    assert _run_with_flag_and_capture_with_llm(monkeypatch, ["--no-llm"]) is False


def test_main_enrich_default_uses_llm(monkeypatch):
    """기본(--no-llm 없음) 에서 with_llm=True 로 전달."""
    assert _run_with_flag_and_capture_with_llm(monkeypatch, []) is True


def test_main_enrich_skips_already_enriched(monkeypatch):
    """이미 content 있는 기사는 enrich 대상에서 제외 (LLM 예산 보호)."""
    _seed_today_news(with_content=True)  # 본문 이미 있음

    def _fake_collect(keywords, *, sources, max_results, on_step=None):
        return run_daily.CollectionReport(
            saved=[{"source": "naver", "keywords": list(keywords), "count": 3, "path": "x"}],
        )

    seen = {"n": -1}

    def _spy_enrich(articles, *, with_llm=True, progress_cb=None):
        seen["n"] = len(articles)
        return articles

    from scripts import daily_scrape
    from scraping import enrich as enrich_mod

    monkeypatch.setattr(daily_scrape, "collect_batch", _fake_collect)
    monkeypatch.setattr(enrich_mod, "enrich_articles", _spy_enrich)

    rc = daily_scrape.main(["--keywords", "로봇", "--enrich-max", "10"])
    assert rc == 0
    # spy_enrich 자체가 호출되지 않거나(없으면 -1), 호출되어도 0
    assert seen["n"] in (-1, 0)
