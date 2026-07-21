"""수집 관측지표·튜닝 env (PR #57 보강 — Phase 0) 회귀 테스트.

병합 판단·운영 튜닝의 근거가 되는 지표(본문/이미지 확보·캐시 적중·데드라인 중단)가
run 로그에 남고, 튜닝 노브가 env 로 조정 가능(기본값 = 검증값)함을 가드한다.
"""
from __future__ import annotations

from unittest.mock import patch

from scraping import run_daily
from store import run_log


def _fake_search(keyword: str, max_results: int = 10) -> list[dict]:
    return [
        {"title": f"{keyword} 기사1", "link": f"https://x/{keyword}/1",
         "content": "본문 " * 30, "image_url": "https://x/img1.jpg"},
        {"title": f"{keyword} 기사2", "link": f"https://x/{keyword}/2", "content": ""},
    ]


def _collect(**kw) -> run_daily.CollectionReport:
    with patch.object(run_daily.naver_news, "search", side_effect=_fake_search):
        return run_daily.collect_batch(
            ["용접"], sources=("naver",), do_enrich=False, **kw)


def test_report_stats_content_image_ready():
    """저장 기사 중 본문(≥50자)·이미지 확보 수가 report.stats 에 집계된다."""
    report = _collect()
    assert report.total_articles == 2
    assert report.stats["content_ready"] == 1   # 기사1만 본문 충분
    assert report.stats["image_ready"] == 1     # 기사1만 이미지
    assert report.stats["cache_hits"] == 0      # do_enrich=False → 캐시 미사용
    assert report.stats["deadline_abandoned"] == 0


def test_run_log_entry_includes_metrics():
    """run_log 엔트리에 확보율·캐시·데드라인 지표가 기록된다 (병합 판단 원자료)."""
    report = _collect()
    entry = run_log.entry_from_report(report, trigger="manual", duration_s=3.21)
    assert entry["duration_s"] == 3.21
    assert entry["content_ready"] == 1 and entry["content_rate_pct"] == 50.0
    assert entry["image_ready"] == 1 and entry["image_rate_pct"] == 50.0
    assert entry["cache_hits"] == 0
    assert entry["deadline_abandoned"] == 0
    assert entry["enrich_skipped_cap"] == 0


def test_run_log_entry_backward_compatible_without_stats():
    """stats 없는 과거 형식 report(dict)도 지표 0 으로 안전 기록."""
    entry = run_log.entry_from_report(
        {"saved": [{"source": "naver", "count": 3, "keywords": ["a"], "path": "p"}],
         "errors": []})
    assert entry["total_articles"] == 3
    assert entry["content_ready"] == 0 and entry["content_rate_pct"] == 0.0
    assert entry["cache_hits"] == 0


def test_cache_hits_counted_in_stats():
    """enrich 캐시 적중 수가 stats 로 흘러간다 (apply_cached 반환 합산)."""
    from scraping import enrich as _enrich

    with patch.object(run_daily.naver_news, "search", side_effect=_fake_search), \
         patch.object(_enrich, "load_today_enriched_index",
                      return_value={"https://x/용접/2": {
                          "content": "캐시 본문 " * 30, "image_url": "https://x/c.jpg",
                          "keywords": ""}}), \
         patch.object(_enrich, "enrich_parallel", side_effect=lambda a, **k: a):
        report = run_daily.collect_batch(["용접"], sources=("naver",), do_enrich=True)
    assert report.stats["cache_hits"] == 1


def test_enrich_env_knobs_defaults_and_override(monkeypatch):
    """튜닝 노브 기본값 = PR #57 검증값, env 로 오버라이드 가능."""
    import importlib

    import config
    from scraping import enrich as _enrich

    # 기본값 (env 미설정)
    assert _enrich.ENRICH_MAX_WORKERS == 6
    assert _enrich.ENRICH_BATCH_DEADLINE == 90.0
    assert _enrich._FETCH_BUDGET_S == 25.0
    assert _enrich.ENRICH_MAX_ARTICLES == 0

    # env 오버라이드 → 모듈 재로드 시 반영 (배포 재시작 시나리오)
    monkeypatch.setenv("INSIGHTBOARD_ENRICH_WORKERS", "8")
    monkeypatch.setenv("INSIGHTBOARD_ENRICH_DEADLINE_S", "120")
    assert config.env_int("INSIGHTBOARD_ENRICH_WORKERS", 4) == 8
    assert config.env_float("INSIGHTBOARD_ENRICH_DEADLINE_S", 90.0) == 120.0
    # 잘못된 값은 default 폴백 (배포 오타가 수집을 죽이지 않게)
    monkeypatch.setenv("INSIGHTBOARD_ENRICH_WORKERS", "abc")
    assert config.env_int("INSIGHTBOARD_ENRICH_WORKERS", 4) == 4
    monkeypatch.delenv("INSIGHTBOARD_ENRICH_WORKERS")
    monkeypatch.delenv("INSIGHTBOARD_ENRICH_DEADLINE_S")
    importlib.reload(_enrich)  # 다른 테스트에 영향 없게 원복
    assert _enrich.ENRICH_MAX_WORKERS == 6


def test_enrich_parallel_stats_out_reports_abandoned():
    """데드라인 초과 시 stats_out.abandoned 에 중단 기사 수가 기록된다."""
    import time as _time

    from scraping import enrich as _enrich

    arts = [{"title": f"t{i}", "link": f"https://slow/{i}"} for i in range(3)]
    with patch.object(_enrich, "enrich_one", side_effect=lambda a, **k: _time.sleep(5)):
        stats: dict = {}
        _enrich.enrich_parallel(arts, max_workers=1, deadline_s=0.3, stats_out=stats)
    assert stats["abandoned"] >= 1
    assert stats["processed"] + stats["abandoned"] == 3


def test_enrich_parallel_cap_skips_excess(monkeypatch):
    """INSIGHTBOARD_ENRICH_MAX_ARTICLES 상한 초과분은 건너뛰고 수를 기록한다."""
    from scraping import enrich as _enrich

    monkeypatch.setattr(_enrich, "ENRICH_MAX_ARTICLES", 2)
    calls: list[str] = []
    arts = [{"title": f"t{i}", "link": f"https://x/{i}"} for i in range(5)]
    with patch.object(_enrich, "enrich_one",
                      side_effect=lambda a, **k: calls.append(a["link"])):
        stats: dict = {}
        out = _enrich.enrich_parallel(arts, stats_out=stats)
    assert len(out) == 5            # 반환 리스트는 전체 유지 (저장은 전부)
    assert len(calls) == 2          # enrich 는 상한까지만
    assert stats["skipped_cap"] == 3
