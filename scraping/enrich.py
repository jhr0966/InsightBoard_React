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
]

_NOISE_SELECTORS = (
    "script, style, .ad, .advertisement, figure, figcaption, "
    "header, footer, nav, .header, .footer"
)

_MIN_CONTENT_LEN = 80


def fetch_content(url: str, *, session=None) -> str:
    """기사 URL → 본문 텍스트. 실패 시 빈 문자열."""
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
    for noise in soup.select(_NOISE_SELECTORS):
        noise.decompose()

    for sel in _CONTENT_SELECTORS:
        tag = soup.select_one(sel)
        if tag:
            text = re.sub(r"\s{2,}", " ", tag.get_text(separator=" ", strip=True))
            if len(text) >= _MIN_CONTENT_LEN:
                return text

    paragraphs = [p.get_text(strip=True) for p in soup.select("p") if len(p.get_text(strip=True)) > 30]
    if paragraphs:
        text = " ".join(paragraphs)
        if len(text) >= _MIN_CONTENT_LEN:
            return text

    return ""


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
