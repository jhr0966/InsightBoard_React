"""구글 뉴스 RSS 파서 회귀 테스트 (네트워크 mock)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from scraping import google


_SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Google News</title>
    <item>
      <title>조선소 용접 자동화 로봇 도입 - 한국경제</title>
      <link>https://news.google.com/rss/articles/CAAB1</link>
      <pubDate>Mon, 12 May 2026 09:15:00 GMT</pubDate>
      <description>설명1</description>
      <source url="https://www.hankyung.com">한국경제</source>
    </item>
    <item>
      <title>중공업 디지털 트윈 가속 - 매일경제</title>
      <link>https://news.google.com/rss/articles/CAAB2</link>
      <pubDate>Mon, 12 May 2026 08:00:00 GMT</pubDate>
      <description>설명2</description>
      <source url="https://www.mk.co.kr">매일경제</source>
    </item>
  </channel>
</rss>
"""


class _FakeResp:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _fake_session(text: str = _SAMPLE_RSS):
    class FakeSession:
        def get(self, *a, **kw):
            return _FakeResp(text)

    return FakeSession()


def test_google_search_parses_items():
    with patch.object(google, "build_session", lambda: _fake_session()):
        articles = google.search("용접 자동화", max_results=10)
    assert len(articles) == 2
    assert articles[0]["title"] == "조선소 용접 자동화 로봇 도입"
    assert articles[0]["press"] == "한국경제"
    assert articles[0]["source"] == "google"
    assert articles[0]["published_at"].startswith("2026-05-12T09:15")


def test_google_search_empty_keyword_returns_empty():
    assert google.search("   ", max_results=5) == []


def test_google_search_dedupes_links():
    rss_with_dup = _SAMPLE_RSS.replace("CAAB2", "CAAB1")
    with patch.object(google, "build_session", lambda: _fake_session(rss_with_dup)):
        articles = google.search("test", max_results=10)
    assert len(articles) == 1


def test_google_search_propagates_http_failure():
    import requests

    class FailSession:
        def get(self, *a, **kw):
            raise requests.RequestException("boom")

    with patch.object(google, "build_session", lambda: FailSession()):
        with pytest.raises(RuntimeError):
            google.search("x")
