"""HTTP 단일 진입점. 다른 모듈은 직접 requests를 import 하지 않는다.

CLAUDE.md 절대규칙 §4 — 외부 호출은 모두 build_session()을 거친다.
"""
from __future__ import annotations

import random

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


REQUEST_TIMEOUT = 15

_UA_POOL = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
)


def default_headers(referer: str | None = None) -> dict[str, str]:
    """브라우저 위장 헤더. `referer` 는 호출처가 도메인에 맞게 지정한다.

    과거엔 모든 요청에 `Referer: https://search.naver.com/` 를 고정으로 실어, 구글
    뉴스·AI Times·오토메이션월드·커스텀 RSS 같은 **타 도메인 요청에 네이버 referer**
    가 붙어 anti-bot 403 을 유발할 수 있었다. 이제 기본은 referer 없음, 네이버 검색만
    명시적으로 네이버 referer 를 전달한다.
    """
    headers = {
        "User-Agent": random.choice(_UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def build_session() -> requests.Session:
    """429/5xx 지수 백오프 + 풀 사이즈 고정."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
