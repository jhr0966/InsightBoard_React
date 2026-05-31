"""범용 RSS 2.0 / Atom 피드 fetcher — 커스텀 출처용.

`store/sources.py::custom_sources()` 가 등록한 (name, url) 쌍을 받아
표준 RSS XML 을 파싱하여 article dict 리스트를 반환한다.

HTTP 진입점은 `scraping.http.build_session()` 단일 — CLAUDE.md §4.
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
import re
from html import unescape
from xml.etree import ElementTree as ET

import requests

from scraping.http import REQUEST_TIMEOUT, build_session, default_headers


def _to_iso(rfc822: str) -> str:
    """RFC822 / ISO 8601 둘 다 시도. 실패 시 빈 문자열."""
    if not rfc822:
        return ""
    try:
        return parsedate_to_datetime(rfc822).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        pass
    # ISO 8601 fallback
    try:
        from datetime import datetime
        return datetime.fromisoformat(rfc822.replace("Z", "+00:00")).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return ""


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()


def _image_from_description(description: str) -> str:
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description or "",
                  flags=re.IGNORECASE)
    return unescape(m.group(1)) if m else ""


def _parse_rss_items(root: ET.Element) -> list[ET.Element]:
    """RSS 2.0 (channel/item) 또는 Atom (feed/entry) 모두 인식."""
    items = root.findall(".//item")
    if items:
        return items
    # Atom namespace 가 있어도 local-name 매칭이 동작하는 hack: tag 끝 'entry'
    entries = [el for el in root.iter() if el.tag.endswith("}entry") or el.tag == "entry"]
    return entries


def _entry_text(el: ET.Element, *local_names: str) -> str:
    """RSS/Atom 무관하게 자식 element 의 텍스트를 첫 매칭으로 반환."""
    for name in local_names:
        # 직접 자식 우선
        for child in list(el):
            tag = child.tag.split("}")[-1]
            if tag == name:
                if name == "link" and not (child.text or "").strip():
                    # Atom 의 <link href="..."/>
                    href = child.attrib.get("href", "")
                    if href:
                        return href.strip()
                return (child.text or "").strip()
    return ""


def fetch(url: str, source_name: str, max_results: int = 10) -> list[dict]:
    """RSS / Atom 피드를 받아 article dict 리스트로 변환.

    Args:
        url: 피드 URL (http/https).
        source_name: 저장될 `source` 필드 (예: "조선해양 e뉴스").
        max_results: 최대 항목 수.

    Returns:
        list[dict] — title/link/published_at/source/summary 등 필수 필드를 채움.
        실패 시 RuntimeError 전파(상위 collect_batch 가 errors 로 캡처).
    """
    if not url or not url.startswith(("http://", "https://")):
        raise RuntimeError(f"잘못된 RSS URL: {url!r}")

    session = build_session()
    try:
        resp = session.get(url, headers=default_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"RSS 요청 실패({source_name}): {e}") from e

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        raise RuntimeError(f"RSS 파싱 실패({source_name}): {e}") from e

    items = _parse_rss_items(root)
    articles: list[dict] = []
    seen_links: set[str] = set()
    for item in items[: max_results * 2]:
        if len(articles) >= max_results:
            break
        title = _entry_text(item, "title")
        link = _entry_text(item, "link")
        if not title or not link or link in seen_links:
            continue
        seen_links.add(link)
        pub_raw = _entry_text(item, "pubDate", "published", "updated")
        description = _entry_text(item, "description", "summary", "content")
        articles.append({
            "title": title,
            "press": source_name,
            "date": pub_raw,
            "published_at": _to_iso(pub_raw),
            "link": link,
            "summary": _strip_tags(description),
            "image_url": _image_from_description(description),
            "keywords": "",
            "source": source_name,
            "query": "",
        })
    return articles
