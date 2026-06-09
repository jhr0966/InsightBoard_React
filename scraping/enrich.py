"""기사 본문 fetch + LLM 키워드/요약 enrich.

흐름:
  1. link → HTML fetch (scraping.http.build_session)
  2. CONTENT_SELECTORS 시도 → 본문 추출
  3. (LLM 설정 시) 본문 → 키워드 5~10개 + 2~3문장 요약
  4. store.cache 로 (본문 해시) 키 캐싱
"""
from __future__ import annotations

import html as _html
import logging
import random
import re
import time
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import Comment

from scraping.extract import is_junk_image, soup_of
from scraping.http import REQUEST_TIMEOUT, build_session, default_headers
from store import cache

logger = logging.getLogger(__name__)


_CONTENT_SELECTORS = [
    # 한국 CMS(모우/모비 계열 — AI Times·오토메이션월드 등) 본문 컨테이너
    "div#article-view-content-div", "article#article-view-content-div",
    "div.article-view-content", "div.article_view_content",
    # 네이버
    "div#dic_area", "div#articleBodyContents", "div.newsct_article",
    "div._article_body_contents",
    # itemprop / 일반 CMS
    "div[itemprop='articleBody']", "article[itemprop='articleBody']", "div.editor-p",
    "div#cnbc-front-articleContent-area-font", "div.ab_text",
    "div#aticle_txt", "div#article_txt", "div.text_area",
    "div.article_cont", "div.news_cnt_detail",
    "div#cont_newstext", "div.detail-body", "div.news_txt",
    "div.article_content", "div.v_article", "div.art_txt", "div.view_con",
    "div#articleBody", "article#articleBody", "div.article_body", "div.article-body",
    "div#news_body_id", "div.news_body", "div#content-body",
    "div.news_content", "div.txt_article", "div.atc_body", "div.article_view",
    "main article", "article", "main",
]

_NOISE_SELECTORS = (
    "script, style, noscript, template, svg, canvas, iframe, "
    "pre, code, samp, kbd, form, button, input, textarea, select, "
    "header, footer, nav, aside, figure, figcaption, "
    ".ad, .ads, .advertisement, .banner, .sponsor, .sponsored, "
    ".share, .sns, .social, .related, .recommend, .copyright, "
    ".reply, .comment, .comments, .byline, .tag, .tags"
)

_MIN_CONTENT_LEN = 80

# '최대 텍스트 블록' 후보를 만들 때 제외할 링크 과다 블록 기준(네비/목록 컷).
_FALLBACK_MAX_LINKS = 8

_CODE_LINE_PATTERNS = (
    re.compile(r"^\s*(var|let|const|function|return|if|else|for|while|import|export)\b"),
    re.compile(r"^\s*[.#]?[A-Za-z0-9_-]+\s*\{[^}]*\}\s*$"),
    re.compile(r"^\s*[{\[]\s*[\"'][A-Za-z0-9_-]+[\"']\s*:"),
    re.compile(r"\b(window|document|navigator|jQuery|dataLayer|googletag|webpack)\."),
    re.compile(r"[{};]{3,}"),
)

_BOILERPLATE_PATTERNS = (
    re.compile(r"무단전재\s*(및)?\s*재배포\s*금지"),
    re.compile(r"저작권자\s*©"),
    re.compile(r"Copyright\s*\(c\)", re.IGNORECASE),
    re.compile(r"기자\s*=?\s*[\w.+-]+@[\w.-]+"),
    re.compile(r"^\s*(관련기사|추천기사|인기기사|ADVERTISEMENT|광고)\s*$", re.IGNORECASE),
)

_IMAGE_SELECTORS = (
    "meta[property='og:image']",
    "meta[property='og:image:url']",
    "meta[property='og:image:secure_url']",
    "meta[name='twitter:image']",
    "meta[name='twitter:image:src']",
    "meta[name='thumbnail']",
    "meta[itemprop='image']",
    "link[rel='image_src']",
)

_IMAGE_ATTR_ORDER = (
    "data-src", "data-original", "data-lazy-src", "data-lazy",
    "data-image", "data-thumb", "data-url", "src",
)


def _img_src_from_attrs(tag) -> str:
    """img/picture 태그에서 lazy-loading 속성을 우선 탐색해 src 반환."""
    for attr in _IMAGE_ATTR_ORDER:
        val = (tag.get(attr) or "").strip()
        if val:
            return val
    # srcset 의 첫 후보 URL.
    srcset = (tag.get("srcset") or tag.get("data-srcset") or "").strip()
    if srcset:
        first = srcset.split(",")[0].strip().split(" ")[0].strip()
        if first:
            return first
    return ""


def _strip_noise(soup) -> None:
    """Remove non-article nodes before text extraction."""
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for noise in soup.select(_NOISE_SELECTORS):
        noise.decompose()
    for tag in soup.select("[hidden], [aria-hidden='true']"):
        tag.decompose()
    # bs4 4.14+/py3.14 환경에서 일부 Tag 의 `.attrs` 가 dict 가 아닐 수 있어
    # `tag.get("style", "")` 가 AttributeError 를 던지는 사례가 관측됨 → getattr 로 방어.
    for tag in soup.find_all(style=True):
        attrs = getattr(tag, "attrs", None)
        if not isinstance(attrs, dict):
            continue
        raw_style = attrs.get("style", "")
        style = str(raw_style or "").replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            tag.decompose()


def _looks_like_code(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if any(pattern.search(stripped) for pattern in _CODE_LINE_PATTERNS):
        return True
    if len(stripped) >= 40:
        symbol_count = sum(stripped.count(ch) for ch in "{}[]();=<>|\\")
        if symbol_count / len(stripped) > 0.16 and not re.search(r"[가-힣]", stripped):
            return True
    return False


def _looks_like_boilerplate(line: str) -> bool:
    return any(pattern.search(line) for pattern in _BOILERPLATE_PATTERNS)


def _clean_article_text(raw_text: str) -> str:
    """Normalize article text and drop code/boilerplate fragments."""
    if not raw_text:
        return ""
    # \uc77c\ubd80 RSS/description \ubcf8\ubb38\uc740 \ud55c \ubc88 escape \ub41c HTML(\uc608: `&amp;nbsp;`, `&lt;p&gt;`)
    # \uc774 \ub4e4\uc5b4\uc640 BeautifulSoup get_text \ub9cc\uc73c\ub85c\ub294 `&nbsp;` \uac19\uc740 \uc5d4\ud2f0\ud2f0\uac00 \uadf8\ub300\ub85c \ub0a8\ub294\ub2e4.
    # \ub450 \ubc88\uae4c\uc9c0 unescape \ud55c \ub4a4 nbsp/zero-width \ubb38\uc790\ub97c \uacf5\ubc31\uc73c\ub85c \uce58\ud658\ud55c\ub2e4.
    text = _html.unescape(_html.unescape(raw_text))
    text = text.replace("\xa0", " ").replace("\u200b", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    lines: list[str] = []
    seen: set[str] = set()
    for line in re.split(r"\n+", text):
        cleaned = re.sub(r"\s{2,}", " ", line).strip(" \t-–—")
        if len(cleaned) < 2:
            continue
        if _looks_like_code(cleaned) or _looks_like_boilerplate(cleaned):
            continue
        # Keep only the first copy of repeated captions/share snippets.
        dedupe_key = cleaned[:120]
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        lines.append(cleaned)
    return re.sub(r"\s{2,}", " ", "\n".join(lines)).strip()


def _text_from_tag(tag) -> str:
    return _clean_article_text(tag.get_text(separator="\n", strip=True))


def _extract_image_url(soup, base_url: str) -> str:
    """Return the likely representative article image URL.

    우선순위: og:image / twitter:image / link[rel=image_src] 메타 →
    article/main 내부 img → picture > source[srcset] → 그 외 본문 img.
    각 후보에서 lazy-loading 속성(`data-src`, `data-lazy-src`, `srcset` 등)도 함께 검사.
    """
    for sel in _IMAGE_SELECTORS:
        tag = soup.select_one(sel)
        if not tag:
            continue
        val = (tag.get("content") or tag.get("href") or "").strip()
        # og:image 라도 언론사 로고/플레이스홀더면 건너뛰고 본문 이미지로 폴백.
        if val and not is_junk_image(val):
            return urljoin(base_url, val)

    img_selectors = (
        "article img", "main img", "div[itemprop='articleBody'] img",
        "article picture source", "main picture source", "picture source", "img",
    )
    for img in soup.select(", ".join(img_selectors)):
        src = _img_src_from_attrs(img)
        if not src or is_junk_image(src):
            continue
        return urljoin(base_url, src)
    return ""


def content_needs_refresh(content: str) -> bool:
    """Detect saved article bodies that are mostly code/UI noise and should be fetched again."""
    if not content or len(str(content).strip()) < _MIN_CONTENT_LEN:
        return True
    lines = [line.strip() for line in re.split(r"\n+", str(content)) if line.strip()]
    if not lines:
        return True
    noisy = sum(1 for line in lines if _looks_like_code(line) or _looks_like_boilerplate(line))
    if noisy >= 2 and noisy / len(lines) >= 0.25:
        return True
    lowered = str(content).lower()
    code_markers = ("<script", "</script", "function(", "window.", "document.", "datalayer", "googletag", "webpack")
    marker_hits = sum(1 for marker in code_markers if marker in lowered)
    if marker_hits >= 2:
        return True
    symbol_count = sum(str(content).count(ch) for ch in "{}[]();=<>|\\")
    return symbol_count / max(len(str(content)), 1) > 0.18 and not re.search(r"[가-힣]", str(content)[:500])


def fetch_article(url: str, *, session=None) -> dict[str, str]:
    """기사 URL → 정제된 본문과 대표 이미지 URL."""
    if not url or not url.startswith("http"):
        return {"content": "", "image_url": ""}
    sess = session or build_session()
    try:
        time.sleep(random.uniform(0.2, 0.5))
        # 같은 출처(origin)를 referer 로 — 브라우저가 사이트 내에서 클릭한 것처럼 보이게.
        # 네이버 기사(n.news.naver.com)처럼 referer 없으면 403 주는 사이트 대응.
        origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
        resp = sess.get(url, headers=default_headers(referer=origin), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding
    except requests.RequestException:
        return {"content": "", "image_url": ""}

    # HTML 파싱 단계는 외부 입력이라 bs4 내부 예외(AttributeError 등) 가능 → batch 전체를 망치지 않도록 흡수.
    try:
        soup = soup_of(resp.text)
        image_url = _extract_image_url(soup, url)
        _strip_noise(soup)

        candidates: list[str] = []
        for sel in _CONTENT_SELECTORS:
            tag = soup.select_one(sel)
            if tag:
                text = _text_from_tag(tag)
                if len(text) >= _MIN_CONTENT_LEN:
                    candidates.append(text)

        paragraphs = [_clean_article_text(p.get_text(separator="\n", strip=True)) for p in soup.select("p")]
        paragraphs = [p for p in paragraphs if len(p) > 30]
        if paragraphs:
            candidates.append("\n".join(paragraphs))

        # '링크가 적은 최대 텍스트 블록'도 **항상** 후보에 포함한다(특정 셀렉터에 안
        # 걸리거나 셀렉터가 본문 일부만 잡는 사이트에서 전체 본문을 확보하기 위함).
        # 본문 정제·코드/보일러플레이트 제거(_text_from_tag) + 링크 8개 초과 블록 제외로
        # 네비/광고가 아닌 실제 기사 본문을 노린다. 최종 본문은 후보 중 가장 긴 것.
        best_block = ""
        for block in soup.find_all(["div", "article", "section"]):
            try:
                if len(block.find_all("a")) > _FALLBACK_MAX_LINKS:
                    continue
                text = _text_from_tag(block)
            except Exception:  # noqa: BLE001 — 개별 블록 파싱 실패는 건너뛴다.
                continue
            if len(text) > len(best_block):
                best_block = text
        if best_block:
            candidates.append(best_block)

        content = max(candidates, key=len) if candidates else ""
        return {"content": content, "image_url": image_url}
    except Exception:  # noqa: BLE001 — 단일 페이지 파싱 실패가 전체 수집을 막지 않도록.
        logger.debug("기사 파싱 실패: %s", url, exc_info=True)
        return {"content": "", "image_url": ""}


def fetch_content(url: str, *, session=None) -> str:
    """기사 URL → 정제된 전체 본문 텍스트. 실패 시 빈 문자열."""
    return fetch_article(url, session=session)["content"]


def _llm_keywords(content: str) -> str:
    from sola.client import chat
    from sola.prompts import SYSTEM_KEYWORD_EXTRACT

    return chat(
        messages=[
            {"role": "system", "content": SYSTEM_KEYWORD_EXTRACT},
            {"role": "user", "content": content[:4000]},
        ],
        temperature=0.1,
        max_tokens=120,
    ).replace("\n", " ").strip()


def _llm_summary(content: str) -> str:
    from sola.client import chat
    from sola.prompts import SYSTEM_SUMMARY_SHORT

    return chat(
        messages=[
            {"role": "system", "content": SYSTEM_SUMMARY_SHORT},
            {"role": "user", "content": content[:4000]},
        ],
        temperature=0.2,
        max_tokens=240,
    ).strip()


def enrich_one(article: dict, *, with_llm: bool = True) -> dict:
    """단일 기사 enrich. 부수효과로 article dict 갱신, 동일 dict 반환."""
    from datetime import datetime, timezone

    link = article.get("link", "")
    content = _clean_article_text(article.get("content") or "")
    image_url = str(article.get("image_url") or "")
    # 리스트에서 가져온 이미지가 언론사 로고/플레이스홀더면 버린다 → fetch 의 og:image 가
    # 채우도록 유도(네이버 검색결과 로고만 가져오던 문제 등). fetch 결과 이미지는
    # _extract_image_url 가 이미 junk 를 걸러 반환하므로 그대로 우선한다.
    if is_junk_image(image_url):
        image_url = ""
    if link and (content_needs_refresh(content) or not image_url):
        fetched = fetch_article(link)
        content = fetched.get("content") or content
        image_url = fetched.get("image_url") or image_url
    article["content"] = content
    article["image_url"] = image_url

    # 빈도 기반 키워드(LLM 무관) — 데이터 표/매칭에서 쓰는 keywords 채움. 이미 있으면 유지.
    if content and not str(article.get("keywords") or "").strip():
        from scraping.extract import extract_keywords
        article["keywords"] = extract_keywords(content, top_n=6)

    if with_llm and content:
        from sola.client import LLMNotConfigured

        cache_key_base = cache.make_key("enrich", content)
        kw_key = cache_key_base + "-kw"
        sum_key = cache_key_base + "-sum"

        cached_kw = cache.get(kw_key)
        if cached_kw is None:
            try:
                cached_kw = _llm_keywords(content)
                cache.put(kw_key, cached_kw)
            except LLMNotConfigured:
                cached_kw = ""
            except Exception:  # noqa: BLE001
                cached_kw = ""
        if cached_kw:
            article["keywords_llm"] = cached_kw

        cached_sum = cache.get(sum_key)
        if cached_sum is None:
            try:
                cached_sum = _llm_summary(content)
                cache.put(sum_key, cached_sum)
            except LLMNotConfigured:
                cached_sum = ""
            except Exception:  # noqa: BLE001
                cached_sum = ""
        if cached_sum:
            article["summary_llm"] = cached_sum

    article["enriched_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return article


def enrich_articles(
    articles: list[dict],
    *,
    with_llm: bool = True,
    progress_cb: Callable[[int, int, dict], None] | None = None,
) -> list[dict]:
    """순차 enrich. Streamlit progress bar 와 호환되도록 콜백 제공."""
    total = len(articles)
    for i, art in enumerate(articles, start=1):
        enrich_one(art, with_llm=with_llm)
        if progress_cb:
            try:
                progress_cb(i, total, art)
            except Exception:  # noqa: BLE001
                pass
    return articles


def enrich_parallel(
    articles: list[dict],
    *,
    with_llm: bool = False,
    max_workers: int = 6,
    progress_cb: Callable[[int, int, dict | None], None] | None = None,
) -> list[dict]:
    """여러 기사의 본문/대표이미지/키워드를 **병렬**로 채운다(ThreadPoolExecutor).

    수집(`run_daily.collect_batch`) 직후 호출 — 검색 결과는 content 가 비어 있으므로
    각 기사 링크에서 본문·og:image 를 가져와 채운다. 입력 리스트를 in-place 갱신하고
    동일 리스트 반환(순서 유지). 개별 기사 실패는 격리해 배치를 막지 않는다.

    with_llm=False 가 기본(본문·이미지·빈도 키워드만, 빠름). LLM 요약/키워드가 필요하면
    True(느림) — collect 경로는 속도를 위해 False 로 호출한다.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total = len(articles)
    if total == 0:
        return articles

    def _work(art: dict) -> None:
        try:
            enrich_one(art, with_llm=with_llm)
        except Exception:  # noqa: BLE001 — 단일 기사 enrich 실패가 배치를 막지 않게.
            logger.debug("기사 enrich 실패: %s", art.get("link"), exc_info=True)

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_work, art) for art in articles]
        for _ in as_completed(futures):
            done += 1
            if progress_cb:
                try:
                    progress_cb(done, total, None)
                except Exception:  # noqa: BLE001
                    pass
    return articles
