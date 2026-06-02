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


def test_search_site_extracts_internal_article_links():
    with patch.object(tech_sites, "build_session", lambda: _fake_session(_AITIMES_HTML)):
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
    html = _AITIMES_HTML
    with patch.object(tech_sites, "build_session", lambda: _fake_session(html)):
        articles = tech_sites.search_site("AI Times", "https://www.aitimes.com", max_results=10)
    titles = [a["title"] for a in articles]
    assert len(titles) == len(set(titles))


def test_search_all_aggregates_and_swallows_failure():
    def _fake_search(name, url, max_results=10):
        if name == "AI Times":
            return [{"title": "ok", "press": name, "link": url + "/x", "source": "tech",
                     "query": name, "summary": "", "keywords": "", "date": "",
                     "published_at": ""}]
        raise RuntimeError("fail")

    with patch.object(tech_sites, "search_site", _fake_search):
        out = tech_sites.search_all(max_results_per_site=5)
    assert len(out) == 1
    assert out[0]["press"] == "AI Times"


def test_search_site_propagates_http_failure():
    import requests

    class FailSession:
        def get(self, *a, **kw):
            raise requests.RequestException("net down")

    with patch.object(tech_sites, "build_session", lambda: FailSession()):
        with pytest.raises(RuntimeError):
            tech_sites.search_site("AI Times", "https://www.aitimes.com")


def test_search_site_raises_on_bad_status():
    """403/500 등 HTTP 오류 상태는 RuntimeError 로 표면화 (naver/google 과 일관)."""
    with patch.object(tech_sites, "build_session", lambda: _fake_session(_AITIMES_HTML, 403)):
        with pytest.raises(RuntimeError):
            tech_sites.search_site("AI Times", "https://www.aitimes.com")


def test_search_all_surfaces_errors_via_on_error():
    """on_error 콜백이 있으면 사이트별 실패를 통보 → 수집 헬스 노출용."""
    def _fake_search(name, url, max_results=10):
        if name == "AI Times":
            return [{"title": "ok", "press": name, "link": url + "/x", "source": "tech",
                     "query": name, "summary": "", "keywords": "", "date": "", "published_at": ""}]
        raise RuntimeError("403")

    seen: list[tuple] = []
    with patch.object(tech_sites, "search_site", _fake_search):
        out = tech_sites.search_all(max_results_per_site=5, on_error=lambda n, m: seen.append((n, m)))
    assert len(out) == 1  # 성공 사이트 결과는 보존
    assert seen and seen[0][1] == "403"  # 실패 사이트는 콜백으로 통보
