"""네이버 뉴스 검색 (키워드 → 기사 dict 리스트)."""
from __future__ import annotations

import random
import time
from urllib.parse import quote, urljoin

import requests

from scraping.extract import first_tag, first_text, is_junk_image, normalize_published_at, soup_of
from scraping.http import REQUEST_TIMEOUT, build_session, default_headers


_LIST_SELECTORS = [
    "div.fds-news-item-list-tab > div",
    "ul.list_news > li.bx",
    "div[class*='fds-news-item-list-tab'] > div",
    "div[class*='fds-news-item']",
    "ul.list_news_infinite_list > li",
    "ul[class*='list_news'] > li",
    "div.news_wrap",
    "div.news_area",
    "li.bx",
    "div.item_news",
]
_TITLE_SELECTORS = ["a.news_tit", "a[class*='news_tit']", "a[class*='title']", "a[class*='tit']"]

# 정크 링크 판정 — 검색결과에 섞인 '언론사 홈'·'Keep 저장' 링크는 기사가 아니다.
# 증상(실측): 제목이 "○○○새 창 열림", 링크가 도메인 루트(기사 경로 없음) 또는
# keep.naver.com → 본문 0자로 enrich 슬롯만 낭비하고 데이터도 오염된다.
_JUNK_TITLE_SUFFIX = "새 창 열림"
_JUNK_LABELS = ("네이버뉴스", "Keep에 바로가기")
_JUNK_HOSTS = ("keep.naver.com",)


def _is_junk_link(link: str) -> bool:
    """도메인 루트(기사 경로 없음) 또는 정크 호스트면 True — 언론사 홈·Keep."""
    from urllib.parse import urlparse

    try:
        p = urlparse(link)
    except ValueError:
        return True
    host = (p.netloc or "").lower()
    if any(h in host for h in _JUNK_HOSTS):
        return True
    # 기사라면 경로에 식별자가 있다. 루트('' 또는 '/')는 언론사 홈페이지.
    return len((p.path or "").strip("/")) < 2
_PRESS_SELECTORS = ["span[class*='press']", "a[class*='press']", "a.info.press", "span.info.press", "a.press"]
_DATE_SELECTORS = ["span[class*='time']", "span[class*='date']", "span.info", "i.time"]
_DESC_SELECTORS = [
    "div[class*='dsc']", "div[class*='desc']", "div[class*='summary']",
    "div.news_dsc", "div.dsc_wrap", "a.api_txt_lines",
]


def _image_from_item(item) -> str:
    """검색결과 항목의 기사 썸네일. 언론사 로고/플레이스홀더 img 는 건너뛴다.

    네이버 검색결과는 기사 썸네일과 함께 **언론사 로고** img 를 같이 둔다. 첫 img 를
    그대로 쓰면 로고만 가져오던 문제가 있어, junk(로고/아이콘) 가 아닌 첫 img 를 고른다.
    썸네일이 없어 모두 junk 면 빈 문자열 → enrich 가 본문 og:image 로 채운다.
    """
    for img in item.find_all("img"):
        src = (img.get("data-src") or img.get("data-lazysrc") or img.get("src") or "").strip()
        if not src or is_junk_image(src):
            continue
        return urljoin("https://search.naver.com", src)
    return ""


def _find_news_items(soup) -> list:
    first_single: list = []
    for sel in _LIST_SELECTORS:
        items = soup.select(sel)
        if len(items) >= 2:
            return items
        if not first_single and items:
            first_single = items
    return first_single


def search(keyword: str, max_results: int = 10) -> list[dict]:
    """키워드로 네이버 뉴스 최신순 검색."""
    if not keyword.strip():
        return []
    url = f"https://search.naver.com/search.naver?where=news&sm=tab_jum&query={quote(keyword)}&sort=1"
    session = build_session()
    try:
        session.get("https://www.naver.com", headers=default_headers(), timeout=8)
        time.sleep(random.uniform(0.3, 0.6))
        # 네이버 검색은 네이버 홈에서 넘어온 것처럼 보이도록 네이버 referer 명시.
        resp = session.get(url, headers=default_headers(referer="https://www.naver.com/"),
                           timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"네이버 검색 요청 실패: {e}") from e

    soup = soup_of(resp.text)
    items = _find_news_items(soup)
    articles: list[dict] = []
    seen_links: set[str] = set()

    for item in items[: max_results * 2]:
        if len(articles) >= max_results:
            break

        title_tag = first_tag(item, _TITLE_SELECTORS)
        if not title_tag:
            # 폴백 — 제목 셀렉터 미매칭 시 첫 유효 앵커. 단, '언론사 홈'·'Keep' 처럼
            # 정크 라벨("새 창 열림" 접미사·언론사명)은 제목으로 쓰지 않는다(오염 방지).
            for a in item.find_all("a", href=True):
                txt = a.get_text(strip=True)
                if (a.get("href", "").startswith("http") and len(txt) > 10
                        and not txt.endswith(_JUNK_TITLE_SUFFIX)
                        and txt not in _JUNK_LABELS):
                    title_tag = a
                    break
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href", "")
        for a in item.find_all("a", href=True):
            if a.get_text(strip=True) == "네이버뉴스" and "n.news.naver.com" in a.get("href", ""):
                link = a.get("href")
                break
        if not link or link in seen_links:
            continue
        # 언론사 홈·Keep 등 기사가 아닌 링크는 버린다(제목이 "○○○새 창 열림"·본문 0자).
        if _is_junk_link(link):
            continue
        seen_links.add(link)

        date_str = ""
        for sel in _DATE_SELECTORS:
            for tag in item.select(sel):
                txt = tag.get_text(strip=True)
                if any(x in txt for x in ["전", "분", "시간", "일", ".", ":"]) and len(txt) < 30:
                    date_str = txt
                    break
            if date_str:
                break

        articles.append({
            "title": title,
            "press": first_text(item, _PRESS_SELECTORS),
            "date": date_str,
            "published_at": normalize_published_at(date_str),
            "link": link,
            "summary": first_text(item, _DESC_SELECTORS),
            "image_url": _image_from_item(item),
            "keywords": "",
            "source": "naver",
            "query": keyword,
        })
    return articles
