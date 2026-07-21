"""도메인 특화 기술 뉴스 사이트 (AI Times, 추가 가능).

각 사이트 메인 페이지에서 기사 링크 후보를 찾아 article dict 리스트로 반환.
구체적 셀렉터를 강제하지 않고, 휴리스틱(제목 길이 + 도메인 일치 + 네비게이션 블록리스트)으로 추출.

⚠ 오토메이션월드는 2026-07 사이트 폐쇄(도메인 DNS 소멸 확인)로 제거했다.
새 사이트 추가는 TECH_SITES/TECH_RSS 에 한 줄씩.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests

from scraping import rss
from scraping.extract import soup_of
from scraping.http import REQUEST_TIMEOUT, build_session, default_headers


TECH_SITES: dict[str, str] = {
    "AI Times": "https://www.aitimes.com",
}

# 모우/모비 계열 CMS(AI Times 등)의 표준 전체기사 RSS 피드.
# homepage <a> 휴리스틱은 사이트마다 마크업이 달라 취약(통째로 0건이 되기도)
# → RSS 를 1순위로 쓰고, 실패/빈손일 때만 homepage 스크래핑으로 폴백.
TECH_RSS: dict[str, str] = {
    "AI Times": "https://www.aitimes.com/rss/allArticle.xml",
}


_NAV_BLOCKLIST = (
    "javascript:", "mailto:", "tel:",
    "/login", "/logout", "/signup", "/join", "/member/",
    "/privacy", "/terms", "/policy", "/sitemap", "/rss",
    "/tag/", "/tags/", "/category/", "/categories/", "/cat/",
    "/search?", "/search.",
    # 개별 기사가 아닌 '연재/섹션/목록' 페이지(모우·모비 계열 CMS) — 기사 모음이라
    # 본문이 없고 대표 og:image 가 사이트 기본 배너라 카드 이미지가 일괄로 같아진다.
    "articlelist", "/list.html", "sc_serial_code", "sc_section_code",
    "serial_code", "section_code", "view_type=", "/serial",
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
    """단일 기술 사이트 → 최근 기사 리스트. RSS 우선, homepage 스크래핑 폴백.

    RSS 가 기사를 주면 그대로 쓰고(`source`/`press`/`query` 만 tech 규격으로 보정),
    RSS 실패(요청·파싱 오류)나 0건이면 기존 homepage 휴리스틱(`_search_site_html`)로
    폴백한다. 둘 다 실패하면 RuntimeError 전파(상위 search_all 의 on_error 가 캡처).
    """
    rss_url = TECH_RSS.get(site_name) or urljoin(site_url.rstrip("/") + "/", "rss/allArticle.xml")
    try:
        items = rss.fetch(rss_url, site_name, max_results=max_results)
    except RuntimeError:
        items = []
    if items:
        for it in items:
            it["press"] = site_name
            it["source"] = "tech"
            it["query"] = site_name
            if not str(it.get("date") or "").strip():
                it["date"] = "최신 동향"
        return items
    return _search_site_html(site_name, site_url, max_results)


def _search_site_html(site_name: str, site_url: str, max_results: int = 10) -> list[dict]:
    """폴백 — 사이트 메인 페이지 <a> 휴리스틱으로 기사 링크 추출."""
    session = build_session()
    site_host = urlparse(site_url).netloc
    try:
        time.sleep(random.uniform(0.4, 0.9))
        resp = session.get(site_url, headers=default_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
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


def search_all(
    max_results_per_site: int = 10,
    *,
    on_error: Callable[[str, str], None] | None = None,
    on_site: Callable[[str, int], None] | None = None,
) -> list[dict]:
    """등록된 모든 기술 사이트에서 수집. 사이트별 실패는 격리하고 계속.

    `on_error(site_name, message)` 콜백이 주어지면 사이트별 실패를 통보한다
    (collect_batch 가 이를 report.errors 로 받아 '수집 헬스' 에 노출). 콜백이 없으면
    기존처럼 조용히 건너뛴다(후방 호환).

    `on_site(site_name, count)` 콜백은 사이트 1곳을 마칠 때마다 호출 — 수집 진행
    모달이 사이트별로 개별 표시하게 한다(과거엔 tech 묶음 1줄만 떠서 특정 사이트가
    시도조차 안 되는 것처럼 보였다). 실패한 사이트도 0건으로 통보해 '시도했음'이
    보이게 한다.
    """
    bag: list[dict] = []
    for name, url in TECH_SITES.items():
        try:
            found = search_site(name, url, max_results=max_results_per_site)
            bag.extend(found)
            if on_site:
                on_site(name, len(found))
        except RuntimeError as e:
            if on_error:
                on_error(name, str(e))
            if on_site:
                on_site(name, 0)  # 실패해도 '시도했음'을 진행표시에 남긴다
            continue
    return bag
