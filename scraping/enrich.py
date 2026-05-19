"""기사 본문 fetch + LLM 키워드/요약 enrich.

흐름:
  1. link → HTML fetch (scraping.http.build_session)
  2. CONTENT_SELECTORS 시도 → 본문 추출
  3. (LLM 설정 시) 본문 → 키워드 5~10개 + 2~3문장 요약
  4. store.cache 로 (본문 해시) 키 캐싱
"""
from __future__ import annotations

import html as _html
import random
import re
import time
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import Comment

from scraping.extract import soup_of
from scraping.http import REQUEST_TIMEOUT, build_session, default_headers
from store import cache


_CONTENT_SELECTORS = [
    "div#dic_area", "div#articleBodyContents", "div.newsct_article",
    "div._article_body_contents", "div[itemprop='articleBody']",
    "article[itemprop='articleBody']", "div.editor-p",
    "div#article_txt", "div.article_cont", "div.news_cnt_detail",
    "div#cont_newstext", "div.detail-body", "div.news_txt",
    "div.article_content", "div.view_con", "div#articleBody",
    "article#articleBody", "div.article_body", "div.article-body",
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
    for tag in soup.find_all(style=True):
        style = str(tag.get("style", "")).replace(" ", "").lower()
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
        if val:
            return urljoin(base_url, val)

    bad_fragments = ("spacer", "blank", "logo", "icon", "ad_", "/ad/", "1x1", "transparent")
    img_selectors = (
        "article img", "main img", "div[itemprop='articleBody'] img",
        "article picture source", "main picture source", "picture source", "img",
    )
    for img in soup.select(", ".join(img_selectors)):
        src = _img_src_from_attrs(img)
        if not src:
            continue
        lower = src.lower()
        if any(bad in lower for bad in bad_fragments):
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
        resp = sess.get(url, headers=default_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding
    except requests.RequestException:
        return {"content": "", "image_url": ""}

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

    content = max(candidates, key=len) if candidates else ""
    return {"content": content, "image_url": image_url}


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
    if link and (content_needs_refresh(content) or not image_url):
        fetched = fetch_article(link)
        content = fetched.get("content") or content
        image_url = fetched.get("image_url") or image_url
    article["content"] = content
    article["image_url"] = image_url

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
