"""store.run_log — 수집 런 로그 영속/구조화 (Phase F 관측성)."""
from __future__ import annotations

from types import SimpleNamespace

from store import run_log


def _report(saved=None, errors=None):
    return SimpleNamespace(saved=saved or [], errors=errors or [])


def test_entry_from_report_builds_schema_and_totals():
    rep = _report(
        saved=[
            {"source": "naver", "count": 20, "keywords": ["용접 로봇"], "path": "/x/a.parquet"},
            {"source": "google", "count": 22, "keywords": ["디지털 트윈"], "path": "/x/b.parquet"},
        ],
    )
    e = run_log.entry_from_report(rep, trigger="cron", duration_s=3.14159)
    assert e["trigger"] == "cron"
    assert e["ok"] is True
    assert e["total_articles"] == 42
    assert e["total_files"] == 2
    assert e["duration_s"] == 3.14  # 소수 2자리 반올림
    assert [s["source"] for s in e["sources"]] == ["naver", "google"]
    assert e["sources"][0]["ok"] is True and e["sources"][0]["keywords"] == ["용접 로봇"]
    assert e["error_sources"] == []
    assert len(e["run_id"].split("-")) == 3  # 날짜-시각-hex


def test_entry_ok_false_and_error_sources_deduped():
    rep = _report(
        saved=[{"source": "naver", "count": 5, "path": "p"}],
        errors=[
            {"source": "google", "keyword": "a", "error": "timeout"},
            {"source": "google", "keyword": "b", "error": "500"},
            {"source": "tech", "keyword": "", "error": "selector"},
        ],
    )
    e = run_log.entry_from_report(rep)
    assert e["ok"] is False
    assert e["error_sources"] == ["google", "tech"]  # 중복 제거 + 정렬
    assert len(e["errors"]) == 3
    assert e["total_articles"] == 5  # saved 기준 (오류 소스 미포함)


def test_entry_accepts_dict_report_and_explicit_ids():
    rep = {"saved": [{"source": "tech", "count": 3, "path": "p"}], "errors": []}
    e = run_log.entry_from_report(rep, run_id="fixed-id", ts="2026-06-02T00:00:00+00:00")
    assert e["run_id"] == "fixed-id"
    assert e["ts"] == "2026-06-02T00:00:00+00:00"
    assert e["duration_s"] is None  # 미지정 시 None


def test_record_and_load_runs_round_trip_most_recent_first():
    run_log.record_run(_report(saved=[{"source": "naver", "count": 1, "path": "p"}]), trigger="cron", run_id="r1")
    run_log.record_run(_report(saved=[{"source": "google", "count": 2, "path": "p"}]), trigger="manual", run_id="r2")
    runs = run_log.load_runs()
    assert [r["run_id"] for r in runs] == ["r2", "r1"]  # 최신 우선
    assert runs[0]["trigger"] == "manual"


def test_load_runs_empty_when_no_file():
    assert run_log.load_runs() == []
    assert run_log.latest_run() is None


def test_latest_run_returns_most_recent():
    run_log.record_run(_report(saved=[{"source": "naver", "count": 1, "path": "p"}]), run_id="r1")
    run_log.record_run(_report(saved=[{"source": "naver", "count": 9, "path": "p"}]), run_id="r2")
    assert run_log.latest_run()["run_id"] == "r2"


def test_load_runs_limit_and_skips_corrupt_lines():
    for i in range(3):
        run_log.record_run(_report(saved=[{"source": "naver", "count": i, "path": "p"}]), run_id=f"r{i}")
    # 깨진 줄을 섞어 robust 파싱 확인
    with run_log._runs_path().open("a", encoding="utf-8") as f:
        f.write("{ not json\n")
    runs = run_log.load_runs(limit=2)
    assert len(runs) == 2
    assert all("run_id" in r for r in runs)
