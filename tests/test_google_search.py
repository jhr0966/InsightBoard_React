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


_RSS_TITLE_ECHO = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>[단독] 수험생 안경 잡고 보니 AI 글라스 커닝 - 스포츠경향</title>
      <link>https://news.google.com/rss/articles/CAAE1</link>
      <pubDate>Tue, 09 Jun 2026 09:00:00 GMT</pubDate>
      <description>&lt;a href="https://x"&gt;[단독] 수험생 안경 잡고 보니 AI 글라스 커닝&lt;/a&gt;&amp;nbsp;&amp;nbsp;스포츠경향</description>
      <source url="https://sports.khan.co.kr">스포츠경향</source>
    </item>
    <item>
      <title>조선소 협동로봇 확대 - 한국경제</title>
      <link>https://news.google.com/rss/articles/CAAE2</link>
      <pubDate>Tue, 09 Jun 2026 08:00:00 GMT</pubDate>
      <description>&lt;a href="https://y"&gt;조선소 협동로봇 확대&lt;/a&gt; 조선소 현장에 협동로봇 보급이 빨라지며 용접·물류 공정의 자동화율이 높아지고 있다.</description>
      <source url="https://www.hankyung.com">한국경제</source>
    </item>
  </channel>
</rss>
"""


def test_google_search_blanks_summary_that_only_echoes_title():
    """description 이 '제목(+언론사)' 반복뿐이면 summary 를 비운다(카드 제목 이중 노출 방지).

    실제 정보가 더 있는 description 은 보존해야 한다.
    """
    with patch.object(google, "build_session", lambda: _fake_session(_RSS_TITLE_ECHO)):
        arts = google.search("AI", max_results=10)
    echo, real = arts[0], arts[1]
    assert echo["summary"] == ""                        # 제목+언론사뿐 → 비움
    assert "자동화율" in real["summary"]                 # 본문 스니펫 있는 건 유지
    assert real["summary"] != real["title"]


def _cbm_token(url: str) -> str:
    """신 CBM 포맷 토큰 합성: \\x08\\x13\\x22<len><url>\\x32<len><lang>."""
    import base64
    body = b"\x08\x13\x22" + bytes([len(url)]) + url.encode() + b"\x32\x05ko-KR\x9a\x01\x06KR:ko"
    return base64.urlsafe_b64encode(body).decode().rstrip("=")


def test_decode_google_url_new_cbm_format_clean():
    """신 CBM 토큰을 길이만큼 정확히 잘라 **깨끗한** 원문 URL 반환(과거엔 뒤에 protobuf
    바이트가 붙어 깨진 URL → enrich fetch 실패 → 구글 뉴스 본문·사진 전부 비던 버그)."""
    url = "https://www.chosun.com/economy/2026/06/22/ABCDEF/"
    got = google._decode_google_url(f"https://news.google.com/rss/articles/{_cbm_token(url)}?oc=5")
    assert got == url  # 트레일링 garbage 없이 정확히 일치


def test_decode_google_url_opaque_returns_empty():
    """URL 이 없는 불투명 토큰은 빈 문자열 → 상위가 batchexecute/리디렉트로 폴백."""
    import base64
    opaque = base64.urlsafe_b64encode(b"\x08\x13\x12\x10" + bytes(range(16))).decode().rstrip("=")
    assert google._decode_google_url(f"https://news.google.com/rss/articles/{opaque}") == ""


def test_decode_google_url_rejects_google_host():
    """디코드 결과가 google.com 이면(자기참조) 빈 문자열."""
    got = google._decode_google_url(f"https://news.google.com/rss/articles/{_cbm_token('https://news.google.com/x')}")
    assert got == ""


# ── 링크 복원 개선(동의 쿠키·통계·batchexecute 재시도) ──────────────


def test_search_populates_resolve_stats():
    """stats_out 에 복원 방법별 카운트가 채워진다. description 에 비-구글 직링크가 있는
    _SAMPLE_RSS 는 direct 로 분류된다(_extract_original_link 이 우선)."""
    rss = _SAMPLE_RSS.replace("설명1", '&lt;a href="https://www.hankyung.com/a1"&gt;기사&lt;/a&gt;')
    rss = rss.replace("설명2", '&lt;a href="https://www.mk.co.kr/a2"&gt;기사&lt;/a&gt;')
    with patch.object(google, "build_session", lambda: _fake_session(rss)):
        stats: dict = {}
        google.search("자동화", max_results=10, stats_out=stats)
    assert stats.get("direct") == 2
    assert stats.get("unresolved", 0) == 0
    assert sum(stats.values()) == 2


def test_search_applies_consent_cookies():
    """search 가 세션에 구글 동의 우회 쿠키를 심는다(batchexecute 성공률↑)."""
    calls: list[tuple] = []

    class CookieJar:
        def set(self, name, value, **kw):
            calls.append((name, value, kw.get("domain")))

    class FakeSession:
        cookies = CookieJar()

        def get(self, *a, **kw):
            return _FakeResp(_SAMPLE_RSS)

    with patch.object(google, "build_session", lambda: FakeSession()):
        google.search("x", max_results=5)
    names = {c[0] for c in calls}
    assert "CONSENT" in names and "SOCS" in names
    assert all(c[2] == ".google.com" for c in calls)


def test_batchexecute_decode_retries_once_then_succeeds():
    """첫 시도가 빈 문자열이면 1회 재시도해 두 번째 성공을 취한다(간헐 봇 응답 흡수)."""
    seq = iter(["", "https://www.hani.co.kr/arti/1"])
    with patch.object(google, "_batchexecute_decode_once", lambda s, t: next(seq)):
        got = google._batchexecute_decode(object(), "TOKEN")
    assert got == "https://www.hani.co.kr/arti/1"


def test_resolve_link_method_labels_unresolved():
    """디코드·batchexecute·리디렉트 모두 실패하면 (원본, 'unresolved')."""
    class FailSession:
        def get(self, *a, **kw):
            import requests
            raise requests.RequestException("blocked")

    url = "https://news.google.com/rss/articles/OPAQUEtoken123"
    with patch.object(google, "_batchexecute_decode", lambda s, t: ""):
        link, method = google._resolve_link_method(FailSession(), url)
    assert link == url and method == "unresolved"
