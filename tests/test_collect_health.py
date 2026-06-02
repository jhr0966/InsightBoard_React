"""데이터 관리 '수집 헬스' readout — run_log.latest_run() 기반 (Phase F)."""
from __future__ import annotations

from types import SimpleNamespace

from store import run_log
from ui import data_management_v2 as dm


def _rep(saved=None, errors=None):
    return SimpleNamespace(saved=saved or [], errors=errors or [])


def test_health_li_empty_when_no_runs():
    assert dm._collect_health_li() == ""


def test_health_li_shows_ok_run_summary():
    run_log.record_run(
        _rep(saved=[{"source": "naver", "count": 7, "path": "p"}]),
        trigger="cron", run_id="r1",
    )
    out = dm._collect_health_li()
    assert "최근 수집" in out
    assert "정상" in out
    assert "7건" in out
    assert "자동(cron)" in out  # 트리거 한국어 라벨


def test_health_li_flags_error_sources():
    run_log.record_run(
        _rep(
            saved=[{"source": "naver", "count": 1, "path": "p"}],
            errors=[{"source": "google", "keyword": "x", "error": "timeout"}],
        ),
        trigger="manual", run_id="r2",
    )
    out = dm._collect_health_li()
    assert "오류" in out
    assert "google" in out  # 오류 소스 노출 → 조용한 실패 가시화
