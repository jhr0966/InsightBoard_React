"""네이버 뉴스 검색 파서 회귀 테스트 (네트워크 mock).

라이브 검증이 불가한 환경(allowlist 프록시)에서도 리스트 파서가
제목·링크·언론사·날짜·요약·썸네일을 올바로 추출하는지 고정한다.
SESSIONS 가 '네이버 리스트 파서 단위테스트 부재 → 라이브 1순위 점검 대상'
으로 지적한 갭을 메운다.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from scraping import naver


# 현행 네이버 뉴스 검색 결과 구조(div.fds-news-item-list-tab > div) 기반 합성 HTML.
# item1: '네이버뉴스' 링크 보유 → n.news.naver.com 우선 + data-src 썸네일.
# item2: 네이버뉴스 링크 없음 → 언론사 원문 URL 폴백 + src 썸네일.
_SAMPLE_HTML = """
<html><body>
  <div class="fds-news-item-list-tab">
    <div>
      <a class="news_tit" href="https://www.shipnews.co.kr/article/111">스마트 조선소 AI 용접 로봇 전면 도입</a>
      <a class="info press" href="https://www.shipnews.co.kr">한국조선신문</a>
      <span class="info time">1시간 전</span>
      <a class="api_txt_lines dsc_txt" href="https://www.shipnews.co.kr/article/111">현대중공업이 차세대 스마트 조선소에 AI 기반 용접 로봇을 전면 도입한다고 밝혔다.</a>
      <a href="https://n.news.naver.com/mnews/article/001/0000000111">네이버뉴스</a>
      <img class="thumb" data-src="https://search.pstatic.net/thumb/111.jpg" src="https://search.pstatic.net/blank.gif">
    </div>
    <div>
      <a class="news_tit" href="https://www.mk.co.kr/news/222">조선업 디지털 트윈 도입 가속</a>
      <a class="info press" href="https://www.mk.co.kr">매일경제</a>
      <span class="info time">3시간 전</span>
      <div class="news_dsc">디지털 트윈으로 생산성을 끌어올린다.</div>
      <img class="thumb" src="https://search.pstatic.net/thumb/222.jpg">
    </div>
  </div>
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


def _fake_session(text: str = _SAMPLE_HTML, status: int = 200):
    class FakeSession:
        def get(self, *a, **kw):
            return _FakeResp(text, status)

    return FakeSession()


def _patched_search(keyword: str, **kw):
    # 검색 직전 random.sleep 으로 테스트가 느려지지 않도록 무력화.
    with patch.object(naver.time, "sleep", lambda *a, **k: None), \
            patch.object(naver, "build_session", lambda: _fake_session()):
        return naver.search(keyword, **kw)


def test_naver_search_parses_title_press_date_summary():
    articles = _patched_search("스마트 조선소", max_results=10)
    assert len(articles) == 2
    first = articles[0]
    assert first["title"] == "스마트 조선소 AI 용접 로봇 전면 도입"
    assert first["press"] == "한국조선신문"
    assert first["date"] == "1시간 전"
    assert "AI 기반 용접 로봇" in first["summary"]
    assert first["source"] == "naver"
    assert first["query"] == "스마트 조선소"


def test_naver_search_prefers_naver_news_link():
    """'네이버뉴스' 앵커(n.news.naver.com)가 있으면 본문 fetch 가 쉬운 그 링크를 우선."""
    articles = _patched_search("스마트 조선소", max_results=10)
    assert articles[0]["link"] == "https://n.news.naver.com/mnews/article/001/0000000111"
    # 네이버뉴스 링크가 없는 기사는 언론사 원문 URL 로 폴백.
    assert articles[1]["link"] == "https://www.mk.co.kr/news/222"


def test_naver_search_extracts_thumbnail_prefers_data_src():
    articles = _patched_search("스마트 조선소", max_results=10)
    # lazy-loading data-src 가 placeholder src 보다 우선.
    assert articles[0]["image_url"] == "https://search.pstatic.net/thumb/111.jpg"
    assert articles[1]["image_url"] == "https://search.pstatic.net/thumb/222.jpg"


def test_naver_search_respects_max_results():
    articles = _patched_search("스마트 조선소", max_results=1)
    assert len(articles) == 1


def test_naver_search_empty_keyword_returns_empty():
    assert naver.search("   ", max_results=5) == []


def test_naver_search_propagates_http_failure():
    import requests

    class FailSession:
        def get(self, *a, **kw):
            raise requests.RequestException("net down")

    with patch.object(naver.time, "sleep", lambda *a, **k: None), \
            patch.object(naver, "build_session", lambda: FailSession()):
        with pytest.raises(RuntimeError):
            naver.search("스마트 조선소")
