"""Phase 6-B: scraping.run_daily.collect_batch 단위 테스트.

네트워크 없이 search 함수를 monkeypatch 해서 디스패치·저장·에러 격리 검증.
"""
from __future__ import annotations

from scraping import run_daily
from store import news_db
from store.paths import news_dir_for


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


def _fake_tech_search_all(max_results_per_site: int = 10) -> list[dict]:
    return [
        {"title": "AI Times A", "link": "https://aitimes.example/a", "press": "AI Times",
         "date": "2026-05-13", "summary": ""},
        {"title": "AutomationWorld B", "link": "https://aw.example/b",
         "press": "AutomationWorld", "date": "2026-05-13", "summary": ""},
    ]


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
    monkeypatch.setattr(run_daily.tech_sites, "search_all", lambda max_results_per_site=10: [])

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

    def _fake_collect(keywords, *, sources, max_results, on_step=None):
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
