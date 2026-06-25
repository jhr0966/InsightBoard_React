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
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()):
        text = enrich.fetch_content("https://example.com/article/1")
    assert "비전 AI" in text
    assert "noise()" not in text  # script stripped
    assert "nav" not in text  # header stripped


def test_fetch_article_extracts_representative_image():
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()):
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
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session(html)):
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
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session(_HTML_PORTAL_CHROME)):
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
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session(_HTML_NO_SELECTORS_NO_P)):
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

    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()), \
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

    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()), \
         patch.object(enrich, "_llm_keywords", _fake_kw), \
         patch.object(enrich, "_llm_summary", _fake_sum):
        enrich.enrich_one(article1, with_llm=True)
        enrich.enrich_one(article2, with_llm=True)

    # 동일 본문 → 캐시 히트로 kw+sum 합쳐 총 2회만 호출
    assert calls["n"] == 2


def test_enrich_one_skips_llm_when_with_llm_false():
    cache.clear()
    article = {"link": "https://example.com/a", "source": "naver"}
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()):
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
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()):
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

    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()):
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
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session(html)):
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
    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session(html)):
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

    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session(html)):
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

    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()), \
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

    with patch.object(enrich, "build_session", lambda *a, **k: _fake_session()), \
         patch.object(enrich, "fetch_article", _maybe_fail):
        out = enrich.enrich_articles(articles, with_llm=False, progress_cb=_cb)

    assert progress == [1, 2]
    assert "비전 AI" in out[0]["content"]
    assert out[1]["content"] == ""


def test_fetch_article_retries_blocked_with_warmup_and_browser_headers():
    """WAF 403 차단 시 홈 워밍업(쿠키) + 강화 헤더·네이버 referer 로 1회 재시도해야 한다.

    thebell 등 구형 ASP/WAF 사이트가 직접 진입을 403 으로 막아 본문·사진이 통째로
    비던 문제의 회귀 방지.
    """
    calls: list[tuple[str, dict]] = []

    class BlockingSession:
        def get(self, url, headers=None, timeout=None):
            calls.append((url, headers or {}))
            if len(calls) == 1:
                return _FakeResp("Forbidden", status=403)  # 최초 기사 요청 차단
            if url.endswith("/"):
                return _FakeResp("<html>home</html>")       # 홈 워밍업
            return _FakeResp(_HTML_WITH_BODY)               # 재시도 성공

    art = enrich.fetch_article("https://www.thebell.co.kr/front/newsview.asp?key=1",
                               session=BlockingSession())
    assert "비전 AI" in art["content"]
    assert art["image_url"].endswith("/photo.jpg")
    assert len(calls) == 3
    assert calls[1][0] == "https://www.thebell.co.kr/"      # 홈 워밍업
    retry_headers = calls[2][1]
    assert retry_headers.get("Sec-Fetch-Mode") == "navigate"  # 강화 브라우저 시그널
    assert "search.naver.com" in retry_headers.get("Referer", "")


def test_fetch_article_no_retry_on_success():
    """정상(200) 응답이면 차단 재시도 없이 1회 요청으로 끝나야 한다."""
    calls: list[str] = []

    class OkSession:
        def get(self, url, headers=None, timeout=None):
            calls.append(url)
            return _FakeResp(_HTML_WITH_BODY)

    art = enrich.fetch_article("https://example.com/a", session=OkSession())
    assert "비전 AI" in art["content"]
    assert len(calls) == 1


def test_clean_article_text_drops_publisher_ui_buttons_and_meta_lines():
    """퍼블리셔 페이지 UI 버튼(번역/beta/kaka i/닫기/폰트)·섹션명·날짜 단독 라인 제거."""
    raw = "\n".join([
        "사회",
        "[단독] 수험생 안경 이상한데… 잡고 보니 AI 글라스 커닝",
        "2026. 6. 10. 00:09",
        "번역",
        "beta",
        "kaka i",
        "닫기",
        "작은 폰트",
        "큰 폰트",
        "전기기사 등 국가기술자격 시험서 부정행위가 적발됐다.",
        "감독관 눈썰미로 3명이 적발돼 경찰에 고발됐다.",
    ])
    cleaned = enrich._clean_article_text(raw)
    assert "부정행위가 적발됐다" in cleaned and "경찰에 고발됐다" in cleaned
    for noise in ("번역", "beta", "kaka i", "닫기", "작은 폰트", "큰 폰트",
                  "2026. 6. 10. 00:09"):
        assert noise not in cleaned.splitlines(), noise
    assert "사회" not in cleaned.splitlines()


def test_strip_title_echo_removes_repeated_title_line_only():
    """본문 첫 줄로 반복된 제목만 제거하고 본문 문장은 보존한다."""
    title = "[단독] 수험생 안경 이상한데… 잡고 보니 AI 글라스 커닝"
    content = "\n".join([title, "전기기사 시험서 부정행위가 적발됐다.", "후속 조치가 진행된다."])
    out = enrich._strip_title_echo(content, title)
    assert title not in out.splitlines()
    assert "부정행위가 적발됐다" in out and "후속 조치" in out
    # 제목이 너무 짧으면(오삭제 위험) 건드리지 않는다.
    assert enrich._strip_title_echo("짧은 제목\n본문", "짧은 제목") == "짧은 제목\n본문"


def test_enrich_one_strips_title_echo_from_content():
    """enrich_one 경로에서도 제목 반복 라인이 본문에서 제거돼야 한다(모달 이중 노출 방지)."""
    cache.clear()
    title = "[단독] 수험생 안경 이상한데… 잡고 보니 AI 글라스 커닝"
    body = ("전기기사 등 국가기술자격 시험에서 AI 글라스를 이용한 부정행위가 적발됐다. "
            "감독관 눈썰미로 3명이 적발돼 경찰에 고발됐고 토익시험에서도 2건이 확인됐다.")
    art = {"title": title, "link": "https://example.com/a",
           "content": f"{title}\n{body}", "image_url": "https://example.com/i.jpg"}
    out = enrich.enrich_one(art, with_llm=False)
    assert title not in out["content"].splitlines()
    assert "부정행위가 적발됐다" in out["content"]


def test_fetch_article_falls_back_to_tls_impersonation_when_still_blocked():
    """워밍업+강화 헤더로도 403 이면 curl_cffi TLS 위장 폴백을 써야 한다(thebell 류).

    위장 응답이 200 이면 그 본문으로 파싱, 위장 불가(None)면 기존(차단) 응답 유지.
    """
    import requests as _rq

    class Blocked(_FakeResp):
        def raise_for_status(self):
            raise _rq.HTTPError(f"HTTP {self.status_code}")

    class AlwaysBlockedSession:
        def get(self, url, headers=None, timeout=None):
            return Blocked("Forbidden", status=403)

    with patch.object(enrich, "fetch_impersonated",
                      return_value=_FakeResp(_HTML_WITH_BODY)) as imp:
        art = enrich.fetch_article("https://www.thebell.co.kr/front/newsview.asp?key=1",
                                   session=AlwaysBlockedSession())
    imp.assert_called_once()
    assert "비전 AI" in art["content"]
    assert art["image_url"].endswith("/photo.jpg")

    # 위장 폴백 불가(None) → 차단 응답 유지 → 빈 결과(예외 없이)
    with patch.object(enrich, "fetch_impersonated", return_value=None):
        art2 = enrich.fetch_article("https://www.thebell.co.kr/front/newsview.asp?key=1",
                                    session=AlwaysBlockedSession())
    assert art2 == {"content": "", "image_url": ""}


def test_fetch_article_handles_response_without_apparent_encoding():
    """curl_cffi 응답엔 apparent_encoding 이 없어도 utf-8 폴백으로 파싱돼야 한다."""
    class NoApparent:
        def __init__(self):
            self.text = _HTML_WITH_BODY
            self.status_code = 200
            self.encoding = None

        def raise_for_status(self):
            pass

    class Sess:
        def get(self, url, headers=None, timeout=None):
            return NoApparent()

    art = enrich.fetch_article("https://example.com/a", session=Sess())
    assert "비전 AI" in art["content"]


def test_img_src_from_attrs_supports_froala_lazy_attr():
    """ND소프트/Froala(slist 등) 의 data-fr-src lazy 속성에서 이미지를 찾아야 한다."""
    html = """<html><body><article id="article-view-content-div">
      <p>싱글리스트 기사 본문이 충분히 길게 들어있다. 자동화 동향 기사 본문 문단으로
      이미지 lazy 속성 회귀를 검증한다. 본문 길이를 채우기 위한 문장.</p>
      <img data-fr-src="https://cdn.slist.kr/news/photo/202606/744335_1.jpg">
    </article></body></html>"""

    class Sess:
        def get(self, url, headers=None, timeout=None):
            return _FakeResp(html)

    art = enrich.fetch_article("https://www.slist.kr/news/articleView.html?idxno=744335",
                               session=Sess())
    assert art["image_url"] == "https://cdn.slist.kr/news/photo/202606/744335_1.jpg"


_ARC_SPA_HTML = """<html><head>
<meta property="og:image" content="https://img.chosun.com/photo/1.jpg">
<script type="application/ld+json">
{"@type":"NewsArticle","headline":"제목","articleBody":"조선소 협동로봇 도입으로 용접 품질 편차가 줄었다. 비전 센서가 갭을 실시간 보정한다. ld+json 전문이 여기에 있다."}
</script>
<script>window.Fusion=window.Fusion||{};Fusion.globalContent={"content_elements":[
{"type":"text","content":"조선소 협동로봇 도입으로 용접 품질 편차가 줄었다."},
{"type":"image","url":"https://img.chosun.com/photo/1.jpg"},
{"type":"text","content":"비전 센서가 갭을 실시간 측정해 위빙 폭을 보정하고, 작업자는 티칭과 검수에 집중한다."},
{"type":"raw_html","content":"<p>재작업률이 한 자릿수로 내려왔다는 평가다.</p>"}
]};Fusion.globalContentConfig={"source":"x"};</script>
</head><body><div id="root"><h1>제목</h1><span>구독</span></div></body></html>"""


def test_fetch_article_extracts_spa_body_from_structured_data():
    """조선닷컴류 Arc SPA — DOM 에 본문이 없어도 ld+json/Fusion JSON 에서 전문 복원."""
    class Sess:
        def get(self, url, headers=None, timeout=None):
            return _FakeResp(_ARC_SPA_HTML)

    art = enrich.fetch_article("https://www.chosun.com/economy/x/", session=Sess())
    assert "용접 품질 편차" in art["content"]
    assert "위빙 폭" in art["content"] or "ld+json 전문" in art["content"]
    assert art["image_url"] == "https://img.chosun.com/photo/1.jpg"


def test_fetch_article_prefers_dom_when_longer_than_structured():
    """서버렌더 사이트 — ld+json 이 요약 수준이면 기존 DOM 셀렉터 본문을 유지해야 한다."""
    html = """<html><head><script type="application/ld+json">
    {"@type":"NewsArticle","articleBody":"짧은 티저 요약입니다. 본문보다 훨씬 짧은 두 문장짜리 메타 요약이라 길이가 모자랍니다."}
    </script></head><body><article itemprop="articleBody">
    <p>이번 발표에서 회사는 비전 AI 기반 용접 검사 시스템을 공개했다.</p>
    <p>해당 기술은 6축 매니퓰레이터와 결합해 검사 시간을 30% 단축한다.</p>
    <p>현장 적용은 가공·조립 공정에서 우선 진행되며, 향후 도장·탑재 공정으로 확대될 예정이다.</p>
    <p>회사 측은 연내 두 개 야드에 추가 공급 계약을 협의 중이라고 밝혔다.</p>
    </article></body></html>"""

    class Sess:
        def get(self, url, headers=None, timeout=None):
            return _FakeResp(html)

    art = enrich.fetch_article("https://example.com/a", session=Sess())
    assert "비전 AI" in art["content"] and "매니퓰레이터" in art["content"]
    assert "짧은 티저" not in art["content"]


def test_arc_fusion_body_handles_missing_marker_and_bad_json():
    assert enrich._arc_fusion_body("<html>no marker</html>") == ""
    assert enrich._arc_fusion_body("Fusion.globalContent = {broken") == ""


_THEBELL_HTML = """<html><body><div class="viewBox">
<div class="viewHead">
  <p class="tit">아이티센글로벌, '2026 오픈 이노베이션' 시동
    <em>AI·웹3 생태계 확립, 글로벌 엑셀러레이터 '드레이퍼' 맞손</em></p>
  <div class="userBox"><span class="user">김인규 기자</span>
    <span class="date">2026-06-10 08:48:04</span></div>
  <div class="googleSearch"><a href="https://google.com/preferences/source?q=thebell.co.kr">
    <img src="https://image.thebell.co.kr/thebell10/img/2025/google_icon.png" width="14px">구글 검색 선호 출처로 추가</a></div>
  <div class="optionIcon"><ul>
    <li><a href="/front/NewsScrap.asp?Key=1">책갈피</a></li>
    <li><a href="javascript:do_print('1')">프린트</a></li>
    <li><a href="javascript:changeTextStyle('minus');">작게</a></li>
    <li><a href="javascript:changeTextStyle('plus');">크게</a></li></ul>
    <div class="share-wrapper"><button><img src="https://image.thebell.co.kr/thebell10/img/2025//share_icon.png"></button></div>
  </div>
</div>
<div id="article_main" class="viewSection">
  <p class="tip mgb20">이 기사는 2026년 06월 10일 08:47에 무료로 공개된 기사입니다. </p>
  <div class="article_content_banner"><a href="http://x"><img class="ADVIMG"
    src="https://image.thebell.co.kr/banner/20260602163419032.gif"></a></div>
  아이티센글로벌이 그룹 내 주요 계열사들을 이끌고 국내 유망 스타트업과의 전략적 투자 및
  협업을 통한 글로벌 시장 진출을 본격화한다고 10일 밝혔다.<br><br>
  <img alt="" height="60" src="https://image.thebell.co.kr/news/photo/2026/06/10/20260610083644372_n.jpg"
    style="float:left" width="300">아이티센글로벌은 오픈 이노베이션 프로그램을 글로벌
  액셀러레이터 네트워크 '드레이퍼 스타트업 하우스 코리아센터'와 공동 개최하고 참가
  기업을 모집한다고 10일 밝혔다.<br><br>
  이번 프로그램은 그룹 내 핵심 계열사 5개사가 참여하는 통합 이니셔티브다.
</div>
<div class="reference">&lt; 저작권자 ⓒ 자본시장 미디어 'thebell', 무단 전재, 재배포 및 AI학습 이용 금지&gt;</div>
<div class="linkNews"><p class="tit">관련기사</p><ul>
  <li><img src="https://image.thebell.co.kr/thebell10/img/time_icon.png">
    <a href="/front/newsview.asp?key=2">아이티센그룹, 에이전틱 AI 전사 도입</a></li></ul></div>
<div class="newsADBox"><a><img class="ADVIMG" src="https://image.thebell.co.kr/banner/20260602163911480.gif"></a></div>
</div></body></html>"""


def test_fetch_article_thebell_body_and_photo():
    """thebell 실마크업 — div#article_main 의 <br> 본문과 기사 사진을 정확히 수집.

    헤더 UI(구글 출처 아이콘·책갈피/프린트/폰트)·광고 배너·무료 공개 안내·관련기사가
    본문/이미지에 섞이면 안 된다.
    """
    class Sess:
        def get(self, url, headers=None, timeout=None):
            return _FakeResp(_THEBELL_HTML)

    art = enrich.fetch_article("https://www.thebell.co.kr/front/newsview.asp?key=1",
                               session=Sess())
    body = art["content"]
    assert "아이티센글로벌이 그룹 내" in body and "드레이퍼 스타트업 하우스" in body
    assert "통합 이니셔티브" in body
    for noise in ("무료로 공개된", "구글 검색 선호", "책갈피", "프린트", "관련기사", "저작권자"):
        assert noise not in body, noise
    # 사진 — 구글 아이콘/배너가 아니라 기사 사진
    assert art["image_url"] == ("https://image.thebell.co.kr/news/photo/2026/06/10/"
                                "20260610083644372_n.jpg")


def test_is_junk_image_flags_ui_icons_and_banners():
    from scraping.extract import is_junk_image
    assert is_junk_image("https://image.thebell.co.kr/thebell10/img/2025/google_icon.png")
    assert is_junk_image("https://image.thebell.co.kr/banner/20260602163419032.gif")
    assert is_junk_image("https://image.thebell.co.kr/thebell10/img/2025//share_icon.png")
    assert not is_junk_image("https://image.thebell.co.kr/news/photo/2026/06/10/1_n.jpg")


# ── 수집 효율(타임아웃·재시도·예산) ──────────────────────────

def test_get_article_response_uses_short_enrich_timeout():
    """본문 fetch 는 ENRICH_TIMEOUT(짧음) 으로 GET — 느린 호스트가 워커를 덜 점유."""
    from scraping.http import ENRICH_TIMEOUT

    calls = []

    class RecSession:
        def get(self, *a, **kw):
            calls.append(kw.get("timeout"))
            return _FakeResp(_HTML_WITH_BODY)

    enrich._get_article_response(RecSession(), "https://example.com/a")
    assert calls and calls[0] == ENRICH_TIMEOUT  # 15(REQUEST_TIMEOUT) 아님


def test_get_article_response_skips_fallback_when_over_budget(monkeypatch):
    """예산 초과면 차단 폴백(워밍업+위장) 생략 — 1건이 배치를 끌지 않게."""
    gets = []

    class BlockSession:
        def get(self, url, *a, **kw):
            gets.append(url)
            return _FakeResp("blocked", status=403)  # 항상 차단

    # 첫 GET 직후 예산을 이미 초과한 것처럼 시간 흐름 조작
    t = {"v": 0.0}
    seq = iter([0.0, 999.0, 999.0, 999.0])
    monkeypatch.setattr(enrich.time, "monotonic", lambda: next(seq, 999.0))
    enrich._get_article_response(BlockSession(), "https://example.com/a")
    # 본 요청 1번만 — 워밍업/재요청 생략(예산 초과)
    assert len(gets) == 1


def test_fetch_article_uses_bounded_retry_session():
    """fetch_article 은 일시적 실패 복구로 재시도 2회(완성도 우선, 무제한 아님)."""
    captured = {}

    def _fake_build(**kw):
        captured.update(kw)
        return _fake_session()

    with patch.object(enrich, "build_session", _fake_build):
        enrich.fetch_article("https://example.com/a")
    assert captured.get("total_retries") == 2


def test_enrich_parallel_default_workers_raised():
    import inspect
    sig = inspect.signature(enrich.enrich_parallel)
    assert sig.parameters["max_workers"].default >= 10


def test_enrich_timeout_read_is_generous_enough():
    """read 타임아웃이 너무 짧으면 느린/큰 기사(Google·AI Times)에서 ReadTimeout 으로
    본문·사진이 통째로 비는 회귀가 난다 — read 는 기존 검증값(15s) 이상 유지."""
    from scraping.http import ENRICH_TIMEOUT

    assert isinstance(ENRICH_TIMEOUT, tuple) and len(ENRICH_TIMEOUT) == 2
    connect, read = ENRICH_TIMEOUT
    assert read >= 15, f"read 타임아웃 {read}s 는 너무 짧다(본문 잘림 위험)"
    assert connect >= 8


def test_enrich_parallel_reuses_one_session(monkeypatch):
    """배치 enrich 가 기사마다 새 세션을 만들지 않고 1개를 공유(연결 재사용)."""
    builds = {"n": 0}

    def _counting_build(**kw):
        builds["n"] += 1
        return _fake_session()

    monkeypatch.setattr(enrich, "build_session", _counting_build)
    arts = [{"title": f"t{i}", "link": f"https://ex.com/{i}"} for i in range(5)]
    enrich.enrich_parallel(arts, with_llm=False)
    # 5개 기사여도 세션 생성은 1회(배치 공유)
    assert builds["n"] == 1


def test_enrich_parallel_honors_deadline(monkeypatch):
    """느린 기사가 있어도 배치는 deadline 안에 반환(수집이 안 끝나는 현상 방지)."""
    import time as _t

    def _slow_enrich(art, **kw):
        _t.sleep(30)  # 데드라인보다 훨씬 김

    monkeypatch.setattr(enrich, "build_session", lambda *a, **k: _fake_session())
    monkeypatch.setattr(enrich, "enrich_one", _slow_enrich)

    arts = [{"title": f"t{i}", "link": f"https://ex.com/{i}"} for i in range(4)]
    t0 = _t.monotonic()
    out = enrich.enrich_parallel(arts, with_llm=False, deadline_s=0.5)
    elapsed = _t.monotonic() - t0
    assert out is arts          # 입력 리스트 그대로 반환
    assert elapsed < 5          # 30초짜리들을 기다리지 않고 곧 반환


# ── 반복 수집 캐시(재fetch 회피) ─────────────────────────────

def test_apply_cached_fills_content_and_skips_refetch(monkeypatch):
    """오늘 캐시에 좋은 본문이 있으면 content/image 를 채워 enrich 가 네트워크를 안 탄다."""
    index = {
        "https://ex.com/1": {
            "content": "충분히 긴 한국어 본문입니다. " * 6,
            "image_url": "https://img/x.jpg", "keywords": "용접,자동화",
        }
    }
    art = {"title": "t", "link": "https://ex.com/1", "content": "", "image_url": ""}
    n = enrich.apply_cached([art], index)
    assert n == 1 and "한국어 본문" in art["content"] and art["image_url"] == "https://img/x.jpg"

    # 채워졌으니 fetch_article 은 호출되지 않아야 함
    called = {"n": 0}
    monkeypatch.setattr(enrich, "fetch_article", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or {"content": "", "image_url": ""})
    enrich.enrich_one(art, with_llm=False)
    assert called["n"] == 0


def test_apply_cached_noop_without_index():
    assert enrich.apply_cached([{"link": "x"}], {}) == 0


def test_load_today_enriched_index_skips_bad_content():
    from store import news_db
    news_db.save_articles([
        {"title": "좋음", "link": "g1", "source": "naver", "date": "2026-06-25",
         "content": "충분히 긴 한국어 본문입니다. " * 6, "image_url": "https://img/a.jpg"},
        {"title": "빈약", "link": "b1", "source": "naver", "date": "2026-06-25", "content": "짧음"},
    ], source="naver")
    idx = enrich.load_today_enriched_index()
    assert "g1" in idx and "b1" not in idx  # 빈약한 본문은 캐시 제외
