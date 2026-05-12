"""구글 뉴스 RSS 검색.

공식 API가 없어 RSS(`news.google.com/rss/search?q=...`)를 사용한다.
응답은 RFC822 날짜·`source` 태그를 가진 표준 RSS 2.0 XML.
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from urllib.parse import quote
from xml.etree import ElementTree as ET

import requests

from scraping.http import REQUEST_TIMEOUT, build_session, default_headers


_RSS_URL = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def _to_iso(rfc822: str) -> str:
    if not rfc822:
        return ""
    try:
        return parsedate_to_datetime(rfc822).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return ""


def _split_title(raw: str) -> tuple[str, str]:
    """'기사 제목 - 언론사' 형식을 분리. 실패 시 (raw, '')."""
    if " - " not in raw:
        return raw, ""
    head, _, tail = raw.rpartition(" - ")
    return head.strip(), tail.strip()


def search(
    keyword: str,
    max_results: int = 10,
    *,
    hl: str = "ko",
    gl: str = "KR",
) -> list[dict]:
    """구글 뉴스 RSS 검색."""
    if not keyword.strip():
        return []
    url = _RSS_URL.format(
        q=quote(keyword),
        hl=hl,
        gl=gl,
        ceid=f"{gl}:{hl}",
    )

    session = build_session()
    try:
        resp = session.get(url, headers=default_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"구글 뉴스 RSS 요청 실패: {e}") from e

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        raise RuntimeError(f"구글 뉴스 RSS 파싱 실패: {e}") from e

    articles: list[dict] = []
    seen_links: set[str] = set()
    for item in root.findall(".//item")[:max_results * 2]:
        if len(articles) >= max_results:
            break
        title_raw = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title_raw or not link or link in seen_links:
            continue
        seen_links.add(link)

        title, press_from_title = _split_title(title_raw)
        source_el = item.find("source")
        press = (source_el.text.strip() if source_el is not None and source_el.text else press_from_title)

        pub_raw = (item.findtext("pubDate") or "").strip()
        published_at = _to_iso(pub_raw)
        description = (item.findtext("description") or "").strip()

        articles.append({
            "title": title,
            "press": press,
            "date": pub_raw,
            "published_at": published_at,
            "link": link,
            "summary": description,
            "keywords": "",
            "source": "google",
            "query": keyword,
        })
    return articles
