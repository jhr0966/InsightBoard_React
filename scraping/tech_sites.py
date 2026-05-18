"""도메인 특화 기술 뉴스 사이트 (AI Times, 오토메이션월드, 추가 가능).

각 사이트 메인 페이지에서 기사 링크 후보를 찾아 article dict 리스트로 반환.
구체적 셀렉터를 강제하지 않고, 휴리스틱(제목 길이 + 도메인 일치 + 네비게이션 블록리스트)으로 추출.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

from scraping.extract import soup_of
from scraping.http import REQUEST_TIMEOUT, build_session, default_headers


TECH_SITES: dict[str, str] = {
    "AI Times": "https://www.aitimes.com",
    "오토메이션월드": "https://automation-world.co.kr",
}


_NAV_BLOCKLIST = (
    "javascript:", "mailto:", "tel:",
    "/login", "/logout", "/signup", "/join", "/member/",
    "/privacy", "/terms", "/policy", "/sitemap", "/rss",
    "/tag/", "/tags/", "/category/", "/categories/", "/cat/",
    "/search?", "/search.",
)

_MIN_TITLE_LEN = 15


def _root_domain(host: str) -> str:
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def _same_root_domain(candidate: str, target: str) -> bool:
    if not candidate:
        return True
    a = _root_domain(candidate)
    b = _root_domain(target)
    return a == b or a.endswith("." + b)


def _is_article_link(href: str, site_host: str) -> bool:
    if not href:
        return False
    lower = href.lower()
    if any(bad in lower for bad in _NAV_BLOCKLIST) or href.startswith("#"):
        return False
    try:
        parsed = urlparse(href)
    except ValueError:
        return False
    if not _same_root_domain(parsed.netloc, site_host):
        return False
    path = (parsed.path or "").rstrip("/")
    return len(path) >= 2


def _image_from_link(a, site_url: str) -> str:
    img = a.select_one("img")
    if not img:
        parent = a.parent
        img = parent.select_one("img") if parent else None
    if not img:
        return ""
    src = (img.get("data-src") or img.get("data-original") or img.get("src") or "").strip()
    return urljoin(site_url, src) if src else ""


def search_site(site_name: str, site_url: str, max_results: int = 10) -> list[dict]:
    """단일 사이트 메인 페이지 → 최근 기사 리스트."""
    session = build_session()
    site_host = urlparse(site_url).netloc
    try:
        time.sleep(random.uniform(0.4, 0.9))
        resp = session.get(site_url, headers=default_headers(), timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        raise RuntimeError(f"{site_name} 요청 실패: {e}") from e

    soup = soup_of(resp.text)
    articles: list[dict] = []
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    for a in soup.find_all("a", href=True):
        if len(articles) >= max_results:
            break
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if len(title) < _MIN_TITLE_LEN or title in seen_titles:
            continue
        full_link = urljoin(site_url, href)
        if full_link in seen_links or not _is_article_link(full_link, site_host):
            continue
        seen_links.add(full_link)
        seen_titles.add(title)

        articles.append({
            "title": title,
            "press": site_name,
            "date": "최신 동향",
            "published_at": now_iso,
            "link": full_link,
            "summary": "",
            "image_url": _image_from_link(a, site_url),
            "keywords": "",
            "source": "tech",
            "query": site_name,
        })
    return articles


def search_all(max_results_per_site: int = 10) -> list[dict]:
    """등록된 모든 기술 사이트에서 수집. 사이트별 실패는 무시하고 계속."""
    bag: list[dict] = []
    for name, url in TECH_SITES.items():
        try:
            bag.extend(search_site(name, url, max_results=max_results_per_site))
        except RuntimeError:
            continue
    return bag
