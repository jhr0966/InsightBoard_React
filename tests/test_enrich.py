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


_HTML_NO_SELECTORS_NO_P = """
<html><head></head><body>
  <nav><a href="/a">메뉴1</a><a href="/b">메뉴2</a></nav>
  <div class="weird-body">
    이 회사는 신형 도장 로봇을 공개했다고 밝혔다. 신형 로봇은 막두께를 실시간으로 측정하며
    핀홀과 같은 표면 결함을 머신비전으로 자동 검출한다. 현장 검증 결과 도장 불량률이 절반
    이하로 줄었고, 작업자의 피로도와 무관하게 일관된 품질 판정이 가능했다는 설명이다. 회사는
    내년부터 조립과 가공 공정으로 적용 범위를 확대하고, 추가 설비 투자도 검토하고 있다고 전했다.
  </div>
</body></html>
"""


def test_fetch_article_takes_fullest_body():
    """셀렉터가 본문 일부만 잡아도 더 긴 본문 블록을 골라 전체 본문을 확보한다."""
    lead = "셀렉터에 잡히는 짧은 리드 문장입니다. " * 3        # article_view 매치(부분)
    full = "전체 본문 핵심 내용 문장입니다. " * 50             # 비표준 div(전체)
    html = (
        f'<html><body><div class="article_view">{lead}</div>'
        f'<div class="zzz-custom-body">{full}</div></body></html>'
    )
    with patch.object(enrich, "build_session", lambda: _fake_session(html)):
        art = enrich.fetch_article("https://example.com/a")
    assert "전체 본문 핵심 내용" in art["content"]
    assert len(art["content"]) > len(lead) + 200            # 리드가 아닌 전체 본문


_HTML_PORTAL_CHROME = """
<html><head><meta property="og:image" content="https://x/photo.jpg"></head><body>
<div id="mArticle">
  <div class="tts_area">음성재생 설정 남성 여성 느림 보통 빠름 닫기 번역 beta Translated by</div>
  <div class="foot_view">글자크기 설정 매우 작은 폰트 보통 폰트 큰 폰트 이 글자크기로 변경됩니다</div>
  <section class="article_view" data-translation>
    <p>애플이 8일 WWDC에서 음성비서 시리를 전면 개편한 시리 AI를 공개했다고 밝혔다.</p>
    <p>새 시리 AI는 한 번의 명령에 그치지 않고 여러 차례 말을 주고받으며 대화의 맥락을 이해한다.</p>
    <p>개발자용 시험판은 이날부터 배포되며 일반 베타는 다음 달, 정식 출시는 가을로 예정됐다.</p>
  </section>
  <div class="relate_news"><a href="/x">정청래 환송 불참</a><a href="/y">장동혁 득표수</a></div>
  <div class="txt_copyright">Copyright © 동아일보. 무단 전재, 재배포 및 AI학습 이용 금지. 해당 언론사로 이동합니다.</div>
</div>
</body></html>
"""


def test_fetch_article_strips_portal_chrome_keeps_body():
    """포털(다음 스타일) 기사 — 본문 컨테이너만 취하고 TTS/글자크기/번역/관련기사/저작권
    chrome 은 제외한다(셀렉터 신뢰 + 노이즈 제거)."""
    with patch.object(enrich, "build_session", lambda: _fake_session(_HTML_PORTAL_CHROME)):
        art = enrich.fetch_article("https://v.daum.net/v/123")
    body = art["content"]
    assert "시리 AI" in body and "대화의 맥락" in body        # 실제 본문 포함
    assert "음성재생 설정" not in body                        # TTS 위젯 제외
    assert "글자크기 설정" not in body and "매우 작은 폰트" not in body
    assert "Translated by" not in body                        # 번역 위젯 제외
    assert "정청래" not in body                               # 관련기사 제외
    assert "무단 전재" not in body                            # 저작권 제외


def test_fetch_article_largest_block_fallback():
    """표준 셀렉터·<p> 가 없어도 링크 적은 최대 텍스트 블록을 폴백으로 추출(참고 스크래퍼 패턴)."""
    with patch.object(enrich, "build_session", lambda: _fake_session(_HTML_NO_SELECTORS_NO_P)):
        article = enrich.fetch_article("https://example.com/x")
    assert "도장 로봇" in article["content"]
    assert "막두께" in article["content"]
    assert "메뉴1" not in article["content"]  # nav(노이즈)는 제거
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


def test_strip_noise_survives_tag_without_attrs_dict():
    """bs4 4.14+/py3.14 환경에서 find_all(style=True) 가 attrs dict 가 깨진 tag 를 내놓아도 죽지 않는다.

    실제 bs4 soup 를 미리 깨면 앞단의 `soup.select(...)` 가 먼저 터지므로,
    `_strip_noise` 가 의존하는 인터페이스(find_all/select/decompose)만 흉내내는
    fake soup 로 방어 가드 자체를 검증한다.
    """
    class _BrokenTag:
        attrs = None  # bs4 가 어떤 이유로 dict 가 아닌 값을 넣었다고 가정.
        decomposed = False

        def decompose(self):
            self.decomposed = True

    class _GoodHidden:
        attrs = {"style": "display:none"}
        decomposed = False

        def decompose(self):
            self.decomposed = True

    broken = _BrokenTag()
    hidden = _GoodHidden()

    class _FakeSoup:
        def find_all(self, *args, **kwargs):
            if kwargs.get("style") is True:
                return [broken, hidden]
            return []  # comment 검색 케이스.

        def select(self, *args, **kwargs):
            return []

    enrich._strip_noise(_FakeSoup())
    # 깨진 tag 는 건드리지 않고 스킵, 정상 hidden tag 는 decompose 호출됨.
    assert broken.decomposed is False
    assert hidden.decomposed is True


def test_fetch_article_returns_empty_on_parse_exception():
    """파싱 단계가 예외를 던져도 fetch_article 은 빈 dict 를 반환해 batch 를 보호해야 한다."""
    def _boom(*_a, **_kw):
        raise AttributeError("boom")

    with patch.object(enrich, "build_session", lambda: _fake_session()), \
         patch.object(enrich, "_strip_noise", _boom):
        result = enrich.fetch_article("https://example.com/p")
    assert result == {"content": "", "image_url": ""}


def test_enrich_articles_skips_failing_article(monkeypatch):
    """한 기사 파싱이 실패해도 나머지는 정상 수집되어야 한다 (수집 batch 전체 멈춤 방지)."""
    cache.clear()
    articles = [
        {"link": "https://example.com/ok", "source": "naver"},
        {"link": "https://example.com/bad", "source": "naver"},
    ]
    progress: list[int] = []

    def _cb(done, total, _art):
        progress.append(done)

    real_fetch = enrich.fetch_article

    def _maybe_fail(url, *, session=None):
        if "bad" in url:
            return {"content": "", "image_url": ""}
        return real_fetch(url, session=session)

    with patch.object(enrich, "build_session", lambda: _fake_session()), \
         patch.object(enrich, "fetch_article", _maybe_fail):
        out = enrich.enrich_articles(articles, with_llm=False, progress_cb=_cb)

    assert progress == [1, 2]
    assert "비전 AI" in out[0]["content"]
    assert out[1]["content"] == ""
