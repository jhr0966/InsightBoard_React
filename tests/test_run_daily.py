"""Phase 6-B: scraping.run_daily.collect_batch 단위 테스트.

네트워크 없이 search 함수를 monkeypatch 해서 디스패치·저장·에러 격리 검증.
"""
from __future__ import annotations

import pytest

from scraping import enrich as _enrich
from scraping import run_daily
from store import news_db
from store.paths import news_dir_for


@pytest.fixture(autouse=True)
def _no_enrich_network(monkeypatch):
    """collect_batch 가 enrich 하며 가짜 URL 로 실제 네트워크를 치는 것을 막아 빠르게.

    enrich(본문/이미지 fetch) 자체 동작은 test_enrich / 아래 전용 테스트가 검증한다.
    개별 테스트가 다시 setattr 하면(아래 enrich 검증) 그쪽이 우선한다.
    """
    monkeypatch.setattr(_enrich, "fetch_article",
                        lambda url, **kw: {"content": "", "image_url": ""})


def _fake_naver_search(keyword: str, max_results: int = 10) -> list[dict]:
    return [
        {"title": f"네이버-{keyword}-{i}", "link": f"https://n.example/{keyword}/{i}",
         "press": "조선일보", "date": "2026-05-13", "summary": ""}
        for i in range(min(2, max_results))
    ]


def _fake_google_search(keyword: str, max_results: int = 10, **_) -> list[dict]:
    return [
        {"title": f"구글-{keyword}", "link": f"https://g.example/{keyword}",
         "press": "Yonhap", "date": "2026-05-13", "summary": ""}
    ]


def _fake_tech_search_all(max_results_per_site: int = 10, **_) -> list[dict]:
    return [
        {"title": "AI Times A", "link": "https://aitimes.example/a", "press": "AI Times",
         "date": "2026-05-13", "summary": ""},
        {"title": "AutomationWorld B", "link": "https://aw.example/b",
         "press": "AutomationWorld", "date": "2026-05-13", "summary": ""},
    ]


def test_collect_batch_enriches_body_and_image(monkeypatch):
    """수집 시 enrich 가 호출돼 각 기사의 content(본문)·image_url 이 채워진다.

    이게 핵심 회귀 방지: 과거 collect_batch 는 enrich 를 호출하지 않아 content 가
    항상 빈 채로 저장됐다(데이터 표 본문 전부 빈칸). 이제 링크에서 본문·og:image 를
    가져와 채운다.
    """
    monkeypatch.setattr(run_daily.naver_news, "search", _fake_naver_search)
    monkeypatch.setattr(run_daily.google_news, "search", lambda *a, **k: [])
    monkeypatch.setattr(run_daily.tech_sites, "search_all", lambda *a, **k: [])
    # enrich.fetch_article 이 본문·이미지를 돌려주도록(autouse 의 빈 stub 을 덮어씀).
    monkeypatch.setattr(
        _enrich, "fetch_article",
        lambda url, **kw: {"content": f"이것은 {url} 기사의 전체 본문 내용입니다. " * 5,
                           "image_url": "https://img.example/main.jpg"},
    )
    report = run_daily.collect_batch(["로봇"], sources=("naver",), max_results=5)
    assert report.total_articles == 2

    df = news_db.load_all_today()
    assert not df.empty
    assert (df["content"].astype(str).str.len() > 50).all()        # 모든 기사 본문 채워짐
    assert (df["image_url"] == "https://img.example/main.jpg").all()  # og:image 채워짐
    assert (df["keywords"].astype(str).str.len() > 0).all()        # 빈도 키워드도 채워짐


def test_collect_batch_emits_per_tech_site_step(monkeypatch):
    """tech 수집이 사이트별로 on_step 을 발화 — 진행 모달에 AI Times·오토메이션월드가
    개별 표시된다(과거엔 tech 묶음 1줄뿐이라 오토메이션월드가 시도조차 안 되는 듯 보였다)."""
    def fake_site(name, url, max_results=10):
        n = 2 if name == "AI Times" else 1
        return [{"title": f"{name}{i}", "link": f"{url}/{i}", "source": "tech",
                 "press": name, "query": name} for i in range(n)]

    monkeypatch.setattr(run_daily.tech_sites, "search_site", fake_site)
    monkeypatch.setattr(_enrich, "enrich_parallel", lambda arts, **k: arts)
    steps: list[tuple] = []
    run_daily.collect_batch([], sources=("tech",), max_results=5, do_enrich=True,
                            on_step=lambda s, k, f: steps.append((s, k, f)))
    assert ("tech", "AI Times", 2) in steps
    assert ("tech", "오토메이션월드", 1) in steps


def test_collect_batch_can_disable_enrich(monkeypatch):
    """do_enrich=False 면 enrich 를 건너뛴다(검색 결과 그대로 저장)."""
    called = {"n": 0}
    monkeypatch.setattr(run_daily.naver_news, "search", _fake_naver_search)
    monkeypatch.setattr(run_daily.google_news, "search", lambda *a, **k: [])
    monkeypatch.setattr(run_daily.tech_sites, "search_all", lambda *a, **k: [])
    monkeypatch.setattr(_enrich, "enrich_parallel",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1) or a[0])
    run_daily.collect_batch(["로봇"], sources=("naver",), max_results=5, do_enrich=False)
    assert called["n"] == 0


def test_collect_batch_dispatches_each_keyword_and_source(monkeypatch):
    monkeypatch.setattr(run_daily.naver_news, "search", _fake_naver_search)
    monkeypatch.setattr(run_daily.google_news, "search", _fake_google_search)
    monkeypatch.setattr(run_daily.tech_sites, "search_all", _fake_tech_search_all)

    report = run_daily.collect_batch(
        ["용접 로봇", "디지털 트윈"],
        sources=("naver", "google", "tech"),
        max_results=5,
    )

    # 소스당 1 entry — naver/google/tech 각 1개씩
    assert len(report.saved) == 3
    assert report.errors == []
    by_src = {r["source"]: r for r in report.saved}
    # naver: 2건×2키워드 = 4
    assert by_src["naver"]["count"] == 4
    assert by_src["naver"]["keywords"] == ["용접 로봇", "디지털 트윈"]
    # google: 1건×2키워드 = 2
    assert by_src["google"]["count"] == 2
    # tech: 2건, 키워드 없음
    assert by_src["tech"]["count"] == 2
    assert by_src["tech"]["keywords"] == []

    # parquet 파일 3개 저장 (소스당 1개)
    files = list(news_dir_for().glob("*.parquet"))
    assert len(files) == 3

    # query 필드가 키워드로 채워졌는지 (네이버/구글 한정)
    df = news_db.load_all_today()
    assert "query" in df.columns
    naver_rows = df[df["title"].str.startswith("네이버")]
    assert (naver_rows["query"] != "").all()
    assert set(naver_rows["query"]) == {"용접 로봇", "디지털 트윈"}


def test_collect_batch_errors_isolated(monkeypatch):
    def _boom(keyword: str, max_results: int = 10) -> list[dict]:
        raise RuntimeError("네트워크 오류")

    monkeypatch.setattr(run_daily.naver_news, "search", _boom)
    monkeypatch.setattr(run_daily.google_news, "search", _fake_google_search)
    monkeypatch.setattr(run_daily.tech_sites, "search_all", lambda max_results_per_site=10, **_: [])

    report = run_daily.collect_batch(
        ["로봇"], sources=("naver", "google", "tech"), max_results=3
    )

    # naver 는 한 키워드만 호출하므로 에러 1건, saved 에는 안 들어감
    assert len(report.errors) == 1
    assert report.errors[0]["source"] == "naver"
    assert "네트워크" in report.errors[0]["error"]
    # google 은 정상 저장
    assert any(r["source"] == "google" for r in report.saved)
    # tech 는 빈 결과라 save_articles 가 None 반환 → entry 안 만들어짐
    # (현 구현은 빈 결과라도 entry 를 추가하지만 path 가 빈 문자열)


def test_collect_batch_partial_keyword_failure_keeps_others(monkeypatch):
    """한 키워드만 실패해도 나머지 키워드 결과는 저장된다."""
    call_count = {"n": 0}

    def _partial(keyword: str, max_results: int = 10) -> list[dict]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("첫 키워드 실패")
        return [{"title": f"네이버-{keyword}", "link": f"https://n.example/{keyword}",
                 "press": "조선", "date": "2026-05-13", "summary": ""}]

    monkeypatch.setattr(run_daily.naver_news, "search", _partial)
    report = run_daily.collect_batch(
        ["실패", "성공"], sources=("naver",), max_results=3
    )
    assert len(report.errors) == 1
    assert report.errors[0]["keyword"] == "실패"
    naver_save = next(r for r in report.saved if r["source"] == "naver")
    assert naver_save["count"] == 1
    assert naver_save["keywords"] == ["성공"]


def test_collect_batch_skips_empty_keywords(monkeypatch):
    monkeypatch.setattr(run_daily.naver_news, "search", _fake_naver_search)
    monkeypatch.setattr(run_daily.google_news, "search", _fake_google_search)
    monkeypatch.setattr(run_daily.tech_sites, "search_all", _fake_tech_search_all)

    report = run_daily.collect_batch(
        ["", "  "], sources=("naver", "google", "tech"), max_results=5
    )

    # 키워드 기반 소스는 모두 스킵, tech 만 실행
    assert len(report.saved) == 1
    assert report.saved[0]["source"] == "tech"


def test_collect_batch_respects_source_filter(monkeypatch):
    monkeypatch.setattr(run_daily.naver_news, "search", _fake_naver_search)
    monkeypatch.setattr(run_daily.google_news, "search", _fake_google_search)

    report = run_daily.collect_batch(
        ["로봇"], sources=("google",), max_results=5
    )
    assert len(report.saved) == 1
    assert report.saved[0]["source"] == "google"


def test_report_summary_lines_human_readable():
    report = run_daily.CollectionReport(
        saved=[
            {"source": "naver", "keywords": ["용접 로봇"], "count": 5, "path": "/tmp/a.parquet"},
            {"source": "tech", "keywords": [], "count": 3, "path": "/tmp/b.parquet"},
        ],
        errors=[{"source": "google", "keyword": "로봇", "error": "timeout"}],
    )
    lines = report.summary_lines()
    assert report.total_articles == 8
    assert report.total_files == 2
    assert any("naver" in line and "용접 로봇" in line for line in lines)
    assert any("오류" in line for line in lines)


def test_cli_default_keywords_used(monkeypatch):
    """scripts.daily_scrape main 이 인자 없이 호출 시 DEFAULT_DAILY_KEYWORDS 사용."""
    captured: dict = {}

    def _fake_collect(keywords, *, sources, max_results, on_step=None, extra_feeds=None):
        captured["keywords"] = list(keywords)
        captured["sources"] = sources
        return run_daily.CollectionReport()

    from scripts import daily_scrape

    monkeypatch.setattr(daily_scrape, "collect_batch", _fake_collect)
    from config import DEFAULT_DAILY_KEYWORDS

    rc = daily_scrape.main([])
    assert rc == 0
    assert captured["keywords"] == list(DEFAULT_DAILY_KEYWORDS)
    assert captured["sources"] == tuple(run_daily.SOURCE_IDS)
