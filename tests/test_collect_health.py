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
    assert "구글 뉴스" in out  # 오류 소스 노출(표시 라벨) → 조용한 실패 가시화


# ── 최근 수집 런 타임라인 (run_log 기반 고도화) ──────────────

def test_run_timeline_empty_when_no_runs():
    assert dm._run_timeline_html() == ""


def test_run_timeline_renders_cell_per_run():
    for i in range(3):
        run_log.record_run(
            _rep(saved=[{"source": "naver", "count": i + 1, "path": "p"}]),
            trigger="cron", run_id=f"t{i}",
        )
    out = dm._run_timeline_html()
    assert "최근 수집 런" in out
    assert out.count('class="dm-run-cell"') == 3
    assert "3/3 정상" in out  # 전부 오류 0건 → ok


def test_run_timeline_marks_ok_and_error_runs():
    run_log.record_run(
        _rep(saved=[{"source": "naver", "count": 5, "path": "p"}]),
        trigger="cron", run_id="ok1",
    )
    run_log.record_run(
        _rep(
            saved=[{"source": "naver", "count": 1, "path": "p"}],
            errors=[{"source": "google", "error": "boom"}],
        ),
        trigger="manual", run_id="err1",
    )
    out = dm._run_timeline_html()
    assert "var(--semantic-success)" in out  # 정상 런 = 초록
    assert "var(--semantic-warning)" in out  # 오류 런 = 주황
    assert "1/2 정상" in out


def test_run_timeline_caps_at_limit():
    for i in range(dm._RUN_TIMELINE_N + 5):
        run_log.record_run(
            _rep(saved=[{"source": "naver", "count": 1, "path": "p"}]),
            trigger="cron", run_id=f"c{i}",
        )
    out = dm._run_timeline_html()
    assert out.count('class="dm-run-cell"') == dm._RUN_TIMELINE_N


# ── 14일 sparkline 일별 런 성공/실패 스트립 ──────────────────

def test_runstatus_strip_empty_when_no_runs():
    assert dm._runstatus_strip_html() == ""


def test_runstatus_strip_renders_14_cells_with_colors():
    from datetime import datetime, timezone
    run_log.record_run(
        _rep(saved=[{"source": "naver", "count": 2, "path": "p"}]),
        trigger="cron", run_id="rs", ts=datetime.now(timezone.utc).isoformat(),
    )
    out = dm._runstatus_strip_html()
    assert "dm-runstatus" in out
    assert out.count("dm-runstatus-cell") == 14
    assert "var(--semantic-success)" in out  # 오늘 ok 칸
    assert "var(--surface-divider)" in out   # 런 없는 날 = divider


# ── 수집 degraded 경고 배너 (개선 백로그 #1) ──────────────────

def test_collect_alert_empty_when_no_runs():
    assert dm._collect_alert_html() == ""


def test_collect_alert_silent_on_recent_ok_run():
    from datetime import datetime, timezone
    run_log.record_run(_rep(saved=[{"source": "naver", "count": 5, "path": "p"}]),
                       trigger="cron", run_id="ok", ts=datetime.now(timezone.utc).isoformat())
    assert dm._collect_alert_html() == ""   # 정상 + 최근 → 경고 없음


def test_collect_alert_danger_on_failed_run():
    from datetime import datetime, timezone
    run_log.record_run(
        _rep(saved=[{"source": "naver", "count": 1, "path": "p"}],
             errors=[{"source": "google", "error": "blocked"}]),
        trigger="cron", run_id="er", ts=datetime.now(timezone.utc).isoformat())
    out = dm._collect_alert_html()
    assert "var(--semantic-danger)" in out and "구글 뉴스" in out


def test_collect_alert_warning_on_stale_run():
    from datetime import datetime, timezone, timedelta
    old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    run_log.record_run(_rep(saved=[{"source": "naver", "count": 5, "path": "p"}]),
                       trigger="cron", run_id="st", ts=old)
    out = dm._collect_alert_html()
    assert "var(--semantic-warning)" in out and "갱신되지" in out
