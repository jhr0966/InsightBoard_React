"""웹크롤링 파이프라인 자체검증 — 로컬 fixture 서버 + 실 scraping 모듈 스모크.

외부망이 막힌 환경(클라우드 샌드박스 등)에서도 scraping 모듈이 실제 HTTP 왕복으로
동작하는지 검증한다. 로컬 HTTP 서버에 RSS/사이트/기사/네이버 fixture 를 띄우고,
`scraping.http.build_session()` 을 통과하는 **실제 요청→파싱 경로**를 그대로 태운다.

Usage:
  python scripts/verify_scrape.py          # 로컬 fixture 검증 (외부망 불필요)
  python scripts/verify_scrape.py --live   # 실 외부 소스(네이버·구글·AI Times)까지 시도

검사 항목:
  1. rss.fetch        — RSS 2.0 피드 파싱 (title/link/published_at/summary/image)
  2. tech_sites       — 사이트 메인 휴리스틱 기사 추출 (제목 길이·도메인·블록리스트)
  3. enrich           — 기사 본문 셀렉터 추출 + og:image
  4. naver 셀렉터     — 검색결과 마크업 → 항목/제목/링크 (URL 하드코딩이라 오프라인 파싱)
  5. (--live) 실 소스 — naver.search / google.search / rss.fetch(AI Times)
"""
from __future__ import annotations

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 레포 루트 — scripts/ 직접 실행 지원

from scraping import enrich, naver, rss, tech_sites
from scraping.extract import first_tag, soup_of

# ---------------------------------------------------------------- fixtures

_ARTICLE_BODY = (
    "조선소 용접 자동화 라인에 협동로봇이 도입되면서 곡블록 용접 품질 편차가 줄었다. "
    "비전 센서가 갭을 실시간 측정해 위빙 폭을 보정하고, 작업자는 티칭과 검수에 집중한다. "
    "현장 적용 6개월 만에 재작업률이 두 자릿수에서 한 자릿수로 내려왔다는 평가다."
)

FIXTURES: dict[str, tuple[str, str]] = {
    "/feed.xml": ("application/rss+xml; charset=utf-8", """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>로컬 테스트 피드</title>
<item><title>조선소 용접 자동화 협동로봇 현장 적용 확대</title>
  <link>{base}/article/1</link>
  <pubDate>Mon, 08 Jun 2026 09:00:00 +0900</pubDate>
  <description>&lt;img src="{base}/img/1.jpg"/&gt;협동로봇 기반 용접 자동화 요약.</description></item>
<item><title>선체 블록 물류 AGV 도입 사례 분석</title>
  <link>{base}/article/2</link>
  <pubDate>Mon, 08 Jun 2026 08:00:00 +0900</pubDate>
  <description>AGV 물류 자동화 요약.</description></item>
<item><title>도장 공정 AI 비전 검사 기술 동향</title>
  <link>{base}/article/3</link>
  <pubDate>Sun, 07 Jun 2026 18:00:00 +0900</pubDate>
  <description>AI 비전 검사 요약.</description></item>
</channel></rss>"""),
    "/site/": ("text/html; charset=utf-8", """<!doctype html><html><body>
<nav><a href="/login">로그인</a><a href="/category/news">카테고리</a></nav>
<section>
  <a href="/article/1"><img src="/img/1.jpg"/>조선소 용접 자동화 협동로봇 현장 적용 확대</a>
  <a href="{base}/article/2">선체 블록 물류 AGV 도입 사례 심층 분석</a>
  <a href="/article/3">도장 공정 AI 비전 검사 기술 최신 동향</a>
  <a href="/article/4">짧은제목</a>
</section></body></html>"""),
    "/article/1": ("text/html; charset=utf-8", """<!doctype html><html><head>
<meta property="og:image" content="{base}/img/og1.jpg"/></head>
<body><header>사이트 헤더</header>
<article id="article-view-content-div"><p>""" + _ARTICLE_BODY + """</p></article>
<footer>저작권</footer></body></html>"""),
    "/naver.html": ("text/html; charset=utf-8", """<!doctype html><html><body>
<ul class="list_news">
  <li class="bx"><div class="news_area">
    <a class="news_tit" href="https://n.news.naver.com/article/001/0001">조선소 용접 자동화 협동로봇 현장 적용 확대</a>
    <a class="info press">테스트일보</a><span class="info">3시간 전</span>
    <div class="news_dsc">협동로봇 용접 자동화 기사 요약문.</div></div></li>
  <li class="bx"><div class="news_area">
    <a class="news_tit" href="https://n.news.naver.com/article/001/0002">선체 블록 물류 AGV 도입 사례 분석</a>
    <a class="info press">테스트경제</a><span class="info">5시간 전</span>
    <div class="news_dsc">AGV 물류 자동화 기사 요약문.</div></div></li>
</ul></body></html>"""),
}


class _Handler(BaseHTTPRequestHandler):
    base_url = ""

    def do_GET(self):  # noqa: N802 — http.server 규약
        path = self.path if self.path in FIXTURES else self.path + "/"
        if path not in FIXTURES:
            self.send_response(404)
            self.end_headers()
            return
        ctype, body = FIXTURES[path]
        data = body.replace("{base}", self.base_url).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # 콘솔 소음 제거
        pass


def _start_server() -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    _Handler.base_url = base
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, base

# ---------------------------------------------------------------- checks


def check_rss(base: str) -> str:
    arts = rss.fetch(f"{base}/feed.xml", "로컬RSS", max_results=10)
    assert len(arts) == 3, f"3건 기대, {len(arts)}건"
    a = arts[0]
    assert a["title"].startswith("조선소 용접"), a["title"]
    assert a["link"] == f"{base}/article/1", a["link"]
    assert a["published_at"].startswith("2026-06-08"), a["published_at"]
    assert a["image_url"].endswith("/img/1.jpg"), a["image_url"]
    assert "협동로봇" in a["summary"] and "<" not in a["summary"], a["summary"]
    return f"{len(arts)}건 · 필드 정상"


def check_tech_sites(base: str) -> str:
    arts = tech_sites.search_site("로컬사이트", f"{base}/site/", max_results=10)
    links = {a["link"] for a in arts}
    assert len(arts) == 3, f"3건 기대(짧은 제목·nav 제외), {len(arts)}건: {links}"
    assert f"{base}/article/1" in links and f"{base}/article/2" in links, links
    assert not any("/login" in l or "/category/" in l for l in links), links
    art1 = next(a for a in arts if a["link"].endswith("/article/1"))
    assert art1["image_url"].endswith("/img/1.jpg"), art1["image_url"]
    return f"{len(arts)}건 · 블록리스트/제목 길이 필터 정상"


def check_enrich(base: str) -> str:
    out = enrich.fetch_article(f"{base}/article/1")
    assert "협동로봇" in out["content"] and len(out["content"]) >= 80, out["content"][:80]
    assert "사이트 헤더" not in out["content"], "본문에 헤더 chrome 혼입"
    assert out["image_url"].endswith("/img/og1.jpg"), out["image_url"]
    return f"본문 {len(out['content'])}자 · og:image 정상"


def check_naver_selectors(base: str) -> str:
    # naver.search() 는 URL 이 하드코딩이라 fixture 마크업을 받아 셀렉터 경로만 검증.
    from scraping.http import build_session
    resp = build_session().get(f"{base}/naver.html", timeout=5)
    soup = soup_of(resp.text)
    items = naver._find_news_items(soup)
    assert len(items) == 2, f"2건 기대, {len(items)}건"
    tag = first_tag(items[0], naver._TITLE_SELECTORS)
    assert tag and tag.get_text(strip=True).startswith("조선소 용접"), tag
    assert "n.news.naver.com" in tag.get("href", ""), tag.get("href")
    return f"{len(items)}건 · 제목/링크 셀렉터 정상"


def check_live() -> str:
    parts = []
    for name, fn in [
        ("naver", lambda: naver.search("조선소 자동화", max_results=3)),
        ("google", lambda: __import__("scraping.google", fromlist=["search"]).search("조선소", max_results=3)),
        ("aitimes-rss", lambda: rss.fetch("https://www.aitimes.com/rss/allArticle.xml", "AI Times", max_results=3)),
    ]:
        try:
            n = len(fn())
            parts.append(f"{name} {n}건")
        except Exception as e:  # noqa: BLE001 — 개별 소스 실패는 모아서 보고
            parts.append(f"{name} 실패({type(e).__name__})")
    msg = " / ".join(parts)
    if all("실패" in p for p in parts):
        raise RuntimeError(f"모든 외부 소스 실패 — 망 allowlist 차단 가능성: {msg}")
    return msg


def main(argv: list[str]) -> int:
    live = "--live" in argv
    srv, base = _start_server()
    checks = [
        ("rss.fetch", lambda: check_rss(base)),
        ("tech_sites", lambda: check_tech_sites(base)),
        ("enrich", lambda: check_enrich(base)),
        ("naver 셀렉터", lambda: check_naver_selectors(base)),
    ]
    if live:
        checks.append(("live 외부소스", check_live))

    fails = 0
    print(f"로컬 fixture 서버: {base}")
    for name, fn in checks:
        try:
            msg = fn()
            print(f"  ✅ {name:12s} {msg}")
        except Exception as e:  # noqa: BLE001 — 개별 실패를 모아 한 번에 보고
            fails += 1
            print(f"  ❌ {name:12s} {type(e).__name__}: {e}")
    srv.shutdown()
    if fails:
        print(f"\nFAIL: {fails}/{len(checks)}")
        return 1
    print(f"\nOK: {len(checks)}/{len(checks)} 크롤링 파이프라인 검증 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
