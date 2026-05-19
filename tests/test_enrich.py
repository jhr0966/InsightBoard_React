"""scraping.enrich — 본문 fetch + LLM 키워드/요약 (HTTP / LLM 모킹)."""
from __future__ import annotations

from unittest.mock import patch

from scraping import enrich
from store import cache


_HTML_WITH_BODY = """
<html><head><meta property="og:image" content="/photo.jpg"></head><body>
  <script>noise()</script>
  <header>nav</header>
  <article itemprop="articleBody">
    <p>이번 발표에서 회사는 비전 AI 기반 용접 검사 시스템을 공개했다.</p>
    <p>해당 기술은 6축 매니퓰레이터와 결합해 검사 시간을 30% 단축한다.</p>
    <p>현장 적용은 가공·조립 공정에서 우선 진행된다.</p>
  </article>
  <footer>foot</footer>
</body></html>
"""


class _FakeResp:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _fake_session(text: str = _HTML_WITH_BODY):
    class FakeSession:
        def get(self, *a, **kw):
            return _FakeResp(text)

    return FakeSession()


def test_fetch_content_extracts_article_body():
    with patch.object(enrich, "build_session", lambda: _fake_session()):
        text = enrich.fetch_content("https://example.com/article/1")
    assert "비전 AI" in text
    assert "noise()" not in text  # script stripped
    assert "nav" not in text  # header stripped


def test_fetch_article_extracts_representative_image():
    with patch.object(enrich, "build_session", lambda: _fake_session()):
        article = enrich.fetch_article("https://example.com/article/1")
    assert article["content"] and "비전 AI" in article["content"]
    assert article["image_url"] == "https://example.com/photo.jpg"


def test_fetch_content_returns_empty_for_invalid_url():
    assert enrich.fetch_content("") == ""
    assert enrich.fetch_content("not-a-url") == ""


def test_enrich_one_uses_llm_when_with_llm_true():
    cache.clear()
    article = {"link": "https://example.com/a", "source": "naver"}
    captured: dict = {"calls": 0}

    def _fake_kw(content):
        captured["calls"] += 1
        return "비전 AI, 용접 로봇, 검사 시스템"

    def _fake_sum(content):
        return "비전 AI 기반 용접 검사로 시간을 단축한다."

    with patch.object(enrich, "build_session", lambda: _fake_session()), \
         patch.object(enrich, "_llm_keywords", _fake_kw), \
         patch.object(enrich, "_llm_summary", _fake_sum):
        out = enrich.enrich_one(article, with_llm=True)

    assert out["content"] and "비전 AI" in out["content"]
    assert out["keywords_llm"].startswith("비전 AI")
    assert "단축" in out["summary_llm"]
    assert out["enriched_at"]


def test_enrich_one_caches_llm_results():
    cache.clear()
    article1 = {"link": "https://example.com/a", "source": "naver"}
    article2 = {"link": "https://example.com/b", "source": "naver"}  # 동일 본문이라 캐시 히트
    calls = {"n": 0}

    def _fake_kw(content):
        calls["n"] += 1
        return "x, y"

    def _fake_sum(content):
        calls["n"] += 1
        return "요약"

    with patch.object(enrich, "build_session", lambda: _fake_session()), \
         patch.object(enrich, "_llm_keywords", _fake_kw), \
         patch.object(enrich, "_llm_summary", _fake_sum):
        enrich.enrich_one(article1, with_llm=True)
        enrich.enrich_one(article2, with_llm=True)

    # 동일 본문 → 캐시 히트로 kw+sum 합쳐 총 2회만 호출
    assert calls["n"] == 2


def test_enrich_one_skips_llm_when_with_llm_false():
    cache.clear()
    article = {"link": "https://example.com/a", "source": "naver"}
    with patch.object(enrich, "build_session", lambda: _fake_session()):
        out = enrich.enrich_one(article, with_llm=False)
    assert out["content"]
    assert out["image_url"].endswith("/photo.jpg")
    assert "keywords_llm" not in out
    assert "summary_llm" not in out


def test_enrich_one_refetches_code_filled_existing_content():
    cache.clear()
    article = {
        "link": "https://example.com/a",
        "source": "naver",
        "content": "window.dataLayer.push({});\nfunction ad(){return document.cookie;}\nvar slot = googletag.defineSlot();",
    }
    with patch.object(enrich, "build_session", lambda: _fake_session()):
        out = enrich.enrich_one(article, with_llm=False)
    assert "비전 AI" in out["content"]
    assert "dataLayer" not in out["content"]
    assert out["image_url"].endswith("/photo.jpg")


def test_enrich_articles_calls_progress_cb():
    cache.clear()
    articles = [
        {"link": "https://example.com/1", "source": "naver"},
        {"link": "https://example.com/2", "source": "naver"},
    ]
    progress: list[tuple[int, int]] = []

    def _cb(done, total, _art):
        progress.append((done, total))

    with patch.object(enrich, "build_session", lambda: _fake_session()):
        enrich.enrich_articles(articles, with_llm=False, progress_cb=_cb)

    assert progress == [(1, 2), (2, 2)]


def test_clean_article_text_decodes_html_entities_and_collapses_nbsp():
    """RSS description 처럼 escape 된 HTML 이 들어와도 `&nbsp;` / `&amp;` 등이 제거돼야 한다."""
    raw = "조선소&nbsp;자동화&nbsp;뉴스&amp;정보 — 본문&lt;br&gt;세부 내용 입니다."
    cleaned = enrich._clean_article_text(raw)
    assert "&nbsp;" not in cleaned
    assert "&amp;" not in cleaned
    assert "&lt;" not in cleaned
    assert "조선소 자동화 뉴스&정보" in cleaned or "조선소 자동화 뉴스 정보" in cleaned


def test_extract_image_url_picks_picture_source_srcset():
    """본문 picture > source[srcset] 이 og:image 가 없을 때 fallback 으로 잡혀야 한다."""
    html = """
    <html><body>
      <article>
        <picture>
          <source srcset="https://cdn.example.com/a-1x.webp 1x, https://cdn.example.com/a-2x.webp 2x" type="image/webp">
          <img src="" alt="">
        </picture>
        <p>본문</p>
      </article>
    </body></html>
    """
    with patch.object(enrich, "build_session", lambda: _fake_session(html)):
        article = enrich.fetch_article("https://example.com/p")
    assert article["image_url"] == "https://cdn.example.com/a-1x.webp"


def test_extract_image_url_uses_lazy_data_src():
    """src 가 비고 data-src 만 채워진 lazy-load img 도 잡혀야 한다."""
    html = """
    <html><body>
      <article>
        <img src="" data-src="https://cdn.example.com/photo.jpg" alt="">
        <p>본문</p>
      </article>
    </body></html>
    """
    with patch.object(enrich, "build_session", lambda: _fake_session(html)):
        article = enrich.fetch_article("https://example.com/p")
    assert article["image_url"] == "https://cdn.example.com/photo.jpg"


def test_fetch_content_cleans_code_noise_and_keeps_full_body():
    html = """
    <html><body>
      <main>
        <article>
          <script>window.dataLayer.push({event: "ad"});</script>
          <style>.article { color: red; }</style>
          <pre>const token = window.document.querySelector('#x');</pre>
          <p>첫 번째 문단에서는 조선소 용접 자동화 도입 배경을 상세히 설명한다.</p>
          <p>두 번째 문단에서는 센서 데이터와 로봇 제어를 연계해 불량률을 낮춘 사례를 소개한다.</p>
          <p>세 번째 문단에서는 현장 작업자의 검수 절차와 향후 확대 계획까지 함께 다룬다.</p>
          <p>var adConfig = { slot: 'news', size: [300, 250] };</p>
          <p>무단전재 및 재배포 금지</p>
        </article>
      </main>
    </body></html>
    """

    with patch.object(enrich, "build_session", lambda: _fake_session(html)):
        text = enrich.fetch_content("https://example.com/article/full")

    assert "첫 번째 문단" in text
    assert "두 번째 문단" in text
    assert "세 번째 문단" in text
    assert "dataLayer" not in text
    assert "querySelector" not in text
    assert "adConfig" not in text
    assert "무단전재" not in text
