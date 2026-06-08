"""HTTP 단일 진입점·날짜/키워드 추출 단위 테스트 (네트워크 호출 없음)."""
from __future__ import annotations

from datetime import datetime, timezone

from scraping.extract import extract_keywords, normalize_published_at
from scraping.http import build_session, default_headers


def test_build_session_has_retry_adapters():
    s = build_session()
    https_adapter = s.get_adapter("https://example.com")
    assert https_adapter.max_retries.total == 3
    assert 429 in https_adapter.max_retries.status_forcelist


def test_default_headers_contain_ua():
    h = default_headers()
    assert "User-Agent" in h
    assert h["Accept-Language"].startswith("ko")


def test_default_headers_referer_opt_in():
    # 기본은 referer 없음 (타 도메인에 네이버 referer 가 붙어 403 유발하던 버그 방지).
    assert "Referer" not in default_headers()
    # 호출처가 명시하면 그대로 실린다 (네이버 검색 전용).
    h = default_headers(referer="https://www.naver.com/")
    assert h["Referer"] == "https://www.naver.com/"


def test_normalize_published_at_relative():
    now = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)
    out = normalize_published_at("2시간 전", now_utc=now)
    assert out.startswith("2026-05-12T10:00")


def test_normalize_published_at_absolute():
    out = normalize_published_at("2026.04.27.")
    assert out.startswith("2026-04-27")


def test_extract_keywords_filters_stopwords():
    kw = extract_keywords("연합뉴스 기자 자동화 자동화 용접 로봇 로봇")
    assert "자동화" in kw
    assert "기자" not in kw and "연합뉴스" not in kw
