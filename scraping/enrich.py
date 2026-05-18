"""기사 본문 fetch + LLM 키워드/요약 enrich.

흐름:
  1. link → HTML fetch (scraping.http.build_session)
  2. CONTENT_SELECTORS 시도 → 본문 추출
  3. (LLM 설정 시) 본문 → 키워드 5~10개 + 2~3문장 요약
  4. store.cache 로 (본문 해시) 키 캐싱
"""
from __future__ import annotations

import random
import re
import time
from typing import Callable

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
    text = raw_text.replace("\xa0", " ").replace("\u200b", " ")
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


def fetch_content(url: str, *, session=None) -> str:
    """기사 URL → 정제된 전체 본문 텍스트. 실패 시 빈 문자열."""
    if not url or not url.startswith("http"):
        return ""
    sess = session or build_session()
    try:
        time.sleep(random.uniform(0.2, 0.5))
        resp = sess.get(url, headers=default_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding
    except requests.RequestException:
        return ""

    soup = soup_of(resp.text)
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

    if not candidates:
        return ""

    # Prefer the longest clean candidate so multi-paragraph article bodies are not truncated.
    return max(candidates, key=len)


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
    content = article.get("content") or ""
    if not content and link:
        content = fetch_content(link)
        article["content"] = content

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
