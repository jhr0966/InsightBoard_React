"""scraping.tech_sites — 사이트 메인 페이지에서 기사 링크 추출."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from scraping import tech_sites


_AITIMES_HTML = """
<html><body>
  <a href="/login">로그인</a>
  <a href="/news/articleView.html?idxno=12345">조선소 비전 AI 도입 확대 기사</a>
  <a href="/news/articleView.html?idxno=22345">로봇 용접 효율화 신기술 발표</a>
  <a href="/tag/automation">자동화 태그</a>
  <a href="https://external.com/page">외부 사이트 기사로 보이는 긴 제목</a>
  <a href="#section">앵커</a>
  <a href="/news/articleView.html?idxno=12345">조선소 비전 AI 도입 확대 기사</a>
</body></html>
"""


class _FakeResp:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _fake_session(text: str, status: int = 200):
    class FakeSession:
        def get(self, *a, **kw):
            return _FakeResp(text, status)

    return FakeSession()


def _no_rss():
    """RSS 폴백 강제용 — rss.fetch 가 빈손이면 homepage 휴리스틱으로 폴백."""
    return patch.object(tech_sites.rss, "fetch", lambda *a, **k: [])


_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>오토메이션월드 첫 기사 자동화 로봇</title>
    <link>https://automation-world.co.kr/news/articleView.html?idxno=1</link>
    <pubDate>Mon, 22 Jun 2026 09:00:00 +0900</pubDate>
    <description>본문 요약 &lt;img src="https://automation-world.co.kr/img/1.jpg"/&gt;</description></item>
  <item><title>오토메이션월드 둘째 기사 디지털 트윈</title>
    <link>https://automation-world.co.kr/news/articleView.html?idxno=2</link>
    <pubDate>Mon, 22 Jun 2026 08:00:00 +0900</pubDate>
    <description>두번째 요약</description></item>
</channel></rss>"""


def test_search_site_uses_rss_first():
    """RSS 가 기사를 주면 그대로 사용 — source=tech, press=사이트명 으로 보정."""
    # rss.fetch 는 자신의 build_session(scraping.http)을 쓰므로 rss 모듈 쪽을 패치.
    with patch.object(tech_sites.rss, "build_session", lambda: _fake_session(_RSS_XML)):
        articles = tech_sites.search_site("오토메이션월드", "https://automation-world.co.kr", max_results=10)
    assert len(articles) == 2
    assert articles[0]["title"] == "오토메이션월드 첫 기사 자동화 로봇"
    assert all(a["source"] == "tech" for a in articles)
    assert all(a["press"] == "오토메이션월드" for a in articles)
    assert articles[0]["link"].endswith("idxno=1")
    # RSS description 의 <img> 가 image_url 로, 태그 제거된 요약이 summary 로.
    assert articles[0]["image_url"].endswith("1.jpg")
    assert "본문 요약" in articles[0]["summary"]


def test_search_site_falls_back_to_html_when_rss_empty():
    with _no_rss(), patch.object(tech_sites, "build_session", lambda: _fake_session(_AITIMES_HTML)):
        articles = tech_sites.search_site("AI Times", "https://www.aitimes.com", max_results=10)
    titles = [a["title"] for a in articles]
    assert "조선소 비전 AI 도입 확대 기사" in titles
    assert "로봇 용접 효율화 신기술 발표" in titles
    # 차단되어야 할 것들
    assert "로그인" not in titles
    assert "자동화 태그" not in titles
    assert all("external.com" not in a["link"] for a in articles)
    # 중복 제거
    assert len(articles) == len(set(a["link"] for a in articles))


def test_search_site_dedupes_titles():
    with _no_rss(), patch.object(tech_sites, "build_session", lambda: _fake_session(_AITIMES_HTML)):
        articles = tech_sites.search_site("AI Times", "https://www.aitimes.com", max_results=10)
    titles = [a["title"] for a in articles]
    assert len(titles) == len(set(titles))


# 실패 격리 테스트용 2-사이트 구성 — 실제 TECH_SITES 목록과 무관하게 동작을 가드.
_TWO_SITES = {"AI Times": "https://www.aitimes.com", "테스트사이트": "https://example.com"}


def test_search_all_aggregates_and_swallows_failure():
    def _fake_search(name, url, max_results=10):
        if name == "AI Times":
            return [{"title": "ok", "press": name, "link": url + "/x", "source": "tech",
                     "query": name, "summary": "", "keywords": "", "date": "",
                     "published_at": ""}]
        raise RuntimeError("fail")

    with patch.object(tech_sites, "TECH_SITES", _TWO_SITES), \
         patch.object(tech_sites, "search_site", _fake_search):
        out = tech_sites.search_all(max_results_per_site=5)
    assert len(out) == 1
    assert out[0]["press"] == "AI Times"


def test_search_site_propagates_http_failure():
    import requests

    class FailSession:
        def get(self, *a, **kw):
            raise requests.RequestException("net down")

    with _no_rss(), patch.object(tech_sites, "build_session", lambda: FailSession()):
        with pytest.raises(RuntimeError):
            tech_sites.search_site("AI Times", "https://www.aitimes.com")


def test_search_site_raises_on_bad_status():
    """403/500 등 HTTP 오류 상태는 RuntimeError 로 표면화 (naver/google 과 일관)."""
    with _no_rss(), patch.object(tech_sites, "build_session", lambda: _fake_session(_AITIMES_HTML, 403)):
        with pytest.raises(RuntimeError):
            tech_sites.search_site("AI Times", "https://www.aitimes.com")


def test_search_all_reports_each_site_via_on_site():
    """on_site 콜백이 사이트마다(성공=건수, 실패=0) 호출 — 진행표시 가시성."""
    def _fake_search(name, url, max_results=10):
        if name == "AI Times":
            return [{"title": "a", "link": url + "/a", "source": "tech"},
                    {"title": "b", "link": url + "/b", "source": "tech"}]
        raise RuntimeError("403")  # 둘째 사이트 실패 시뮬

    sites: list[tuple] = []
    with patch.object(tech_sites, "TECH_SITES", _TWO_SITES), \
         patch.object(tech_sites, "search_site", _fake_search):
        out = tech_sites.search_all(on_site=lambda n, c: sites.append((n, c)))
    assert len(out) == 2
    # 두 사이트 모두 통보됨 — 실패한 사이트도 0건으로 '시도했음'이 보인다.
    assert ("AI Times", 2) in sites
    assert ("테스트사이트", 0) in sites


def test_search_all_surfaces_errors_via_on_error():
    """on_error 콜백이 있으면 사이트별 실패를 통보 → 수집 헬스 노출용."""
    def _fake_search(name, url, max_results=10):
        if name == "AI Times":
            return [{"title": "ok", "press": name, "link": url + "/x", "source": "tech",
                     "query": name, "summary": "", "keywords": "", "date": "", "published_at": ""}]
        raise RuntimeError("403")

    seen: list[tuple] = []
    with patch.object(tech_sites, "TECH_SITES", _TWO_SITES), \
         patch.object(tech_sites, "search_site", _fake_search):
        out = tech_sites.search_all(max_results_per_site=5, on_error=lambda n, m: seen.append((n, m)))
    assert len(out) == 1  # 성공 사이트 결과는 보존
    assert seen and seen[0][1] == "403"  # 실패 사이트는 콜백으로 통보
