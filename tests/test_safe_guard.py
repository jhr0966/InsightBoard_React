"""ui._safe.guard — silent except 를 로깅으로 표면화 (개선 백로그 #3)."""
from __future__ import annotations

import logging

from ui._safe import guard


def test_guard_swallows_exception_and_continues():
    reached_after = False
    with guard("테스트 연산"):
        raise ValueError("boom")
    reached_after = True  # guard 가 예외를 삼켜 여기 도달
    assert reached_after


def test_guard_preserves_prior_value_on_failure():
    x = "default"
    with guard("x 계산"):
        x = 1 / 0  # ZeroDivisionError
    assert x == "default"  # 실패 시 이전 값 보존 → 렌더 폴백 가능


def test_guard_logs_warning_with_label(caplog):
    with caplog.at_level(logging.WARNING, logger="ui"):
        with guard("매칭 로드"):
            raise RuntimeError("nope")
    assert any("매칭 로드" in r.getMessage() for r in caplog.records)
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    # 스택트레이스(exc_info)가 함께 기록된다
    assert any(r.exc_info for r in caplog.records)


def test_guard_no_log_on_success(caplog):
    with caplog.at_level(logging.WARNING, logger="ui"):
        with guard("정상 연산"):
            _ = 1 + 1
    assert not caplog.records
