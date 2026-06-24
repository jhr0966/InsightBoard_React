"""기사 본문 fetch + LLM 키워드/요약 enrich.

흐름:
  1. link → HTML fetch (scraping.http.build_session)
  2. CONTENT_SELECTORS 시도 → 본문 추출
  3. (LLM 설정 시) 본문 → 키워드 5~10개 + 2~3문장 요약
  4. store.cache 로 (본문 해시) 키 캐싱
"""
from __future__ import annotations

import html as _html
import json
import logging
import random
import re
import time
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import Comment

from scraping.extract import is_junk_image, soup_of
from scraping.http import (
    ENRICH_TIMEOUT,
    REQUEST_TIMEOUT,
    build_session,
    default_headers,
    fetch_impersonated,
)

# 본문 fetch 1건의 전체 시간 예산(초). 차단 시 3단계 폴백(기본→워밍업→TLS위장)이
# 누적되는데, 이미 예산을 넘겼으면 남은 (가장 비싼) 단계를 건너뛴다 — 한 기사가
# 배치 전체를 끌지 않게 하는 deadline. read 타임아웃(20s)보다 커서, 정상이지만
# 느린 사이트의 폴백 복구(워밍업→재요청, 위장)가 한 단계만에 잘리지 않게 한다.
_FETCH_BUDGET_S = 25.0
from store import cache

logger = logging.getLogger(__name__)


_CONTENT_SELECTORS = [
    # 한국 CMS(모우/모비 계열 — AI Times·오토메이션월드 등) 본문 컨테이너
    "div#article-view-content-div", "article#article-view-content-div",
    "div.article-view-content", "div.article_view_content",
    # thebell(구형 ASP) — 본문이 <p> 없이 <br> 구분 텍스트로 div#article_main 에 직접 들어있다.
    "div#article_main", "div.viewSection",
    # 네이버
    "div#dic_area", "div#articleBodyContents", "div.newsct_article",
    "div._article_body_contents",
    # itemprop / 일반 CMS
    "div[itemprop='articleBody']", "article[itemprop='articleBody']", "div.editor-p",
    "div#cnbc-front-articleContent-area-font", "div.ab_text",
    "div#aticle_txt", "div#article_txt", "div.text_area",
    "div.article_cont", "div.news_cnt_detail",
    "div#cont_newstext", "div.detail-body", "div.news_txt",
    "div.article_content", "div.v_article", "div.art_txt", "div.view_con",
    "div#articleBody", "article#articleBody", "div.article_body", "div.article-body",
    "div#news_body_id", "div.news_body", "div#content-body",
    "div.news_content", "div.txt_article", "div.atc_body", "div.article_view",
    # 포털(다음·네이버 등) 기사 본문 컨테이너 — section/div 무관 매칭.
    ".article_view", "section.article_view", "[data-translation]",
    "div#harmonyContainer", "div.news_view_body", "div#newsEndContents",
    "main article", "article", "main",
]

_NOISE_SELECTORS = (
    "script, style, noscript, template, svg, canvas, iframe, "
    "pre, code, samp, kbd, form, button, input, textarea, select, "
    "header, footer, nav, aside, figure, figcaption, "
    ".ad, .ads, .advertisement, .banner, .sponsor, .sponsored, "
    ".share, .sns, .social, .related, .recommend, .copyright, "
    ".reply, .comment, .comments, .byline, .tag, .tags, "
    # 포털(다음·네이버) 기사 리더 UI 잡음 — TTS/글자크기/번역/관련기사/언론사 이동/저작권.
    ".tts_area, [class*='tts'], [class*='relate'], [class*='copyright'], "
    "[class*='promotion'], .alex-action, .foot_view, .relate_news, "
    ".article_relation, .reporter_area, .copy_info, .txt_copyright, .link_news, "
    # thebell — 본문 컨테이너 안 광고 배너 + 헤더 옵션(책갈피/프린트/폰트/공유)·관련기사·태그.
    ".article_content_banner, .newsADBox, .linkNews, .linkBox, .optionIcon, .googleSearch"
)

_MIN_CONTENT_LEN = 80

# '최대 텍스트 블록' 후보를 만들 때 제외할 링크 과다 블록 기준(네비/목록 컷).
_FALLBACK_MAX_LINKS = 8

_CODE_LINE_PATTERNS = (
    re.compile(r"^\s*(var|let|const|function|return|if|else|for|while|import|export)\b"),
    re.compile(r"^\s*[.#]?[A-Za-z0-9_-]+\s*\{[^}]*\}\s*$"),
    re.compile(r"^\s*[{\[]\s*[\"'][A-Za-z0-9_-]+[\"']\s*:"),
    re.compile(r"\b(window|document|navigator|jQuery|dataLayer|googletag|webpack)\."),
    re.compile(r"[{};]{3,}"),
)

_BOILERPLATE_PATTERNS = (
    re.compile(r"무단전재\s*(및)?\s*재배포\s*금지"),
    re.compile(r"무단\s*전재.*금지|재배포.*금지|AI\s*학습.*(이용)?\s*금지"),
    re.compile(r"저작권자\s*©"),
    re.compile(r"Copyright\s*[©(]", re.IGNORECASE),
    re.compile(r"기자\s*=?\s*[\w.+-]+@[\w.-]+"),
    re.compile(r"^\s*(관련기사|추천기사|인기기사|많이 본 뉴스|ADVERTISEMENT|광고)\s*$", re.IGNORECASE),
    # 포털 기사 리더 UI 텍스트(다음·네이버) — 음성/글자크기/번역 위젯, 언론사 이동 안내.
    re.compile(r"음성\s*재생\s*설정|글자\s*크기\s*설정|이 글자크기로 변경됩니다"),
    re.compile(r"매우\s*(작은|큰)\s*폰트|보통\s*폰트|파란원을 좌우로"),
    re.compile(r"Translated by|번역\s*beta|음성으로 제공", re.IGNORECASE),
    re.compile(r"해당\s*언론사로\s*이동|에서\s*직접\s*확인하세요"),
    re.compile(r"다음뉴스를?\s*만나보세요|가장\s*빠른\s*뉴스가 있고"),
    # 퍼블리셔(언론사 자체 페이지) 기사 wrapper 의 UI 버튼/위젯 텍스트 — 단독 라인만 제거.
    # 본문 셀렉터 미매칭 → 최대블록 폴백 시 폰트/공유/번역 버튼 라벨이 본문에 섞이는 문제.
    re.compile(r"^(번역(\s*beta)?|beta|닫기|공유(하기)?|스크랩|프린트|인쇄(하기)?)$", re.IGNORECASE),
    re.compile(r"^(매우\s*)?(작은|큰|보통)\s*폰트$|^(글꼴|글자)\s*(크게|작게|크기)$"),
    re.compile(r"^kaka\s*i$|^(카카오(톡|스토리)?|페이스북|페북|트위터|밴드|텔레그램|링크\s*복사|url\s*복사)$",
               re.IGNORECASE),
    # 기사 메타가 단독 라인으로 섞인 것 — 섹션명/입력·수정 일시/날짜만 있는 줄.
    re.compile(r"^(사회|정치|경제|국제|문화|생활|스포츠|연예|오피니언|IT|과학|산업|증권|부동산|기획|칼럼)$"),
    re.compile(r"^(입력|수정|업데이트|발행)\s*[:.]?\s*\d{4}"),
    re.compile(r"^\d{4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2}\.?\s*(\d{1,2}:\d{2}(:\d{2})?)?$"),
    # thebell — 무료 공개 안내 라인 + 헤더 옵션 버튼/구글 출처 추가 라벨.
    re.compile(r"무료로 공개된 기사입니다|구글 검색 선호 출처로 추가"),
    re.compile(r"^(책갈피|프린트|작게|크게)$"),
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
    # ND소프트/Froala 에디터 계열(slist 등) 본문 이미지 lazy 속성.
    "data-fr-src", "data-echo", "data-lazyload",
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
    # bs4 4.14+/py3.14 환경에서 일부 Tag 의 `.attrs` 가 dict 가 아닐 수 있어
    # `tag.get("style", "")` 가 AttributeError 를 던지는 사례가 관측됨 → getattr 로 방어.
    for tag in soup.find_all(style=True):
        attrs = getattr(tag, "attrs", None)
        if not isinstance(attrs, dict):
            continue
        raw_style = attrs.get("style", "")
        style = str(raw_style or "").replace(" ", "").lower()
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


def _strip_title_echo(content: str, title: str) -> str:
    """본문에 기사 제목이 그대로 한 줄로 반복되면 제거.

    본문 셀렉터 미매칭 사이트에서 최대블록 폴백이 제목 영역까지 포함한 wrapper 를
    잡으면, 모달에서 제목이 두 번(헤더 + 본문 첫 줄) 보인다 → 정규화 후 제목과
    동일한 라인만 걷어낸다(본문 문장 오삭제 방지 위해 8자 미만 제목은 건너뜀).
    """
    norm_title = re.sub(r"\s+", " ", (title or "")).strip()
    if not content or len(norm_title) < 8:
        return content
    kept = [line for line in content.splitlines()
            if re.sub(r"\s+", " ", line).strip() != norm_title]
    return "\n".join(kept)


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
        # og:image 라도 언론사 로고/플레이스홀더면 건너뛰고 본문 이미지로 폴백.
        if val and not is_junk_image(val):
            return urljoin(base_url, val)

    img_selectors = (
        "article img", "main img", "div[itemprop='articleBody'] img",
        # 본문 컨테이너로 추정되는 div 내부를 문서 전체보다 먼저 — 헤더/사이드 UI 아이콘
        # (thebell 구글 출처 아이콘 등)이 첫 img 로 잡히는 것을 방지.
        "div[id*='article'] img", "div[class*='article'] img", "div.viewSection img",
        "article picture source", "main picture source", "picture source", "img",
    )
    for img in soup.select(", ".join(img_selectors)):
        src = _img_src_from_attrs(img)
        if not src or is_junk_image(src):
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


# WAF/anti-bot 이 봇 의심 요청에 주로 돌려주는 상태코드 — 이때만 강화 재시도를 1회 수행.
_BLOCKED_STATUSES = (401, 403, 406, 412, 429)


def _full_browser_headers(referer: str | None = None) -> dict[str, str]:
    """WAF 가 검사하는 브라우저 시그널(sec-fetch-*)까지 채운 강화 헤더."""
    headers = default_headers(referer=referer)
    headers.update({
        "Sec-Fetch-Site": "cross-site" if referer else "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })
    return headers


def _get_article_response(sess, url: str):
    """기사 GET — WAF/anti-bot 차단 응답이면 홈 워밍업(쿠키) + 강화 헤더로 1회 재시도.

    thebell 등 구형 ASP/WAF 사이트는 세션 쿠키 없는 직접 진입·약식 헤더를 403 으로
    막아 본문·사진이 통째로 빈다 → ① 사이트 홈을 먼저 방문해 세션 쿠키를 받고
    ② sec-fetch 시그널 + 네이버 검색 referer(검색 클릭 유입 위장)로 다시 요청한다.
    """
    # 같은 출처(origin)를 referer 로 — 브라우저가 사이트 내에서 클릭한 것처럼 보이게.
    # 네이버 기사(n.news.naver.com)처럼 referer 없으면 403 주는 사이트 대응.
    start = time.monotonic()
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
    resp = sess.get(url, headers=default_headers(referer=origin), timeout=ENRICH_TIMEOUT)
    if resp.status_code not in _BLOCKED_STATUSES:
        return resp
    # 예산 초과면 폴백(워밍업+위장) 생략 — 차단 1건이 배치를 끌지 않게.
    if time.monotonic() - start > _FETCH_BUDGET_S:
        return resp
    try:
        sess.get(origin, headers=_full_browser_headers(), timeout=ENRICH_TIMEOUT)
    except requests.RequestException:
        pass  # 워밍업 실패는 무시 — 본 요청 재시도가 본질
    time.sleep(random.uniform(0.3, 0.7))
    resp = sess.get(url, headers=_full_browser_headers(referer="https://search.naver.com/"),
                    timeout=ENRICH_TIMEOUT)
    if resp.status_code not in _BLOCKED_STATUSES:
        return resp
    # 헤더로도 안 풀리면 TLS 지문(JA3) 검사 WAF — 실제 Chrome TLS 로 위장(curl_cffi,
    # 선택 의존성)해 최후 재시도. 가장 비싼 단계라 예산 초과면 건너뛴다.
    if time.monotonic() - start > _FETCH_BUDGET_S:
        return resp
    imp = fetch_impersonated(url, referer="https://search.naver.com/", timeout=ENRICH_TIMEOUT[1])
    if imp is not None and getattr(imp, "status_code", 599) < 400:
        return imp
    return resp


def _ldjson_article_body(soup) -> str:
    """schema.org NewsArticle ld+json 의 articleBody — SPA 라도 메타엔 전문이 있다."""
    for tag in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (ValueError, TypeError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, list):
                nodes.extend(n for n in graph if isinstance(n, dict))
                continue
            body = node.get("articleBody")
            if isinstance(body, str) and body.strip():
                return _clean_article_text(body)
    return ""


def _arc_fusion_body(html_text: str) -> str:
    """Arc Publishing(Fusion) SPA 본문 — `Fusion.globalContent` JSON 의 문단 복원.

    조선닷컴 등 Arc 계열은 본문 문단이 DOM 에 없고(JS 렌더) fusion-metadata 스크립트의
    content_elements(type=text/raw_html) 에만 있다. 마커가 없으면 빈 문자열.
    """
    m = re.search(r"Fusion\.globalContent\s*=\s*", html_text)
    if not m:
        return ""
    try:
        data, _ = json.JSONDecoder().raw_decode(html_text, m.end())
    except ValueError:
        return ""
    paras: list[str] = []
    for el in data.get("content_elements") or []:
        if isinstance(el, dict) and el.get("type") in ("text", "raw_html"):
            txt = re.sub(r"<[^>]+>", " ", str(el.get("content") or ""))
            if txt.strip():
                paras.append(txt)
    return _clean_article_text("\n".join(paras))


def _structured_body(soup, html_text: str) -> str:
    """구조화 데이터(ld+json → Arc Fusion)에서 본문 — 둘 중 더 긴 쪽."""
    candidates = (_ldjson_article_body(soup), _arc_fusion_body(html_text))
    return max(candidates, key=len)


def fetch_article(url: str, *, session=None) -> dict[str, str]:
    """기사 URL → 정제된 본문과 대표 이미지 URL."""
    if not url or not url.startswith("http"):
        return {"content": "", "image_url": ""}
    # 본문 fetch 는 best-effort — 재시도 1회·짧은 백오프로 느린 호스트 누적시간 억제.
    sess = session or build_session(total_retries=1, backoff_factor=0.3)
    try:
        time.sleep(random.uniform(0.2, 0.5))
        resp = _get_article_response(sess, url)
        if resp.status_code >= 400:
            # 워밍업·TLS 위장 폴백까지 거친 최종 응답이 여전히 차단 — 배포 로그에서
            # '어느 기사가 어떤 코드로 막혔는지' 보이도록 warning 으로 남긴다.
            logger.warning("기사 fetch 차단: %s (HTTP %s)", url, resp.status_code)
        resp.raise_for_status()
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            # curl_cffi 응답엔 apparent_encoding 이 없다 → getattr 폴백(utf-8).
            resp.encoding = getattr(resp, "apparent_encoding", None) or "utf-8"
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        logger.warning("기사 fetch 실패: %s (HTTP %s · %s)", url, status or "-",
                       type(e).__name__)
        return {"content": "", "image_url": ""}

    # HTML 파싱 단계는 외부 입력이라 bs4 내부 예외(AttributeError 등) 가능 → batch 전체를 망치지 않도록 흡수.
    try:
        soup = soup_of(resp.text)
        image_url = _extract_image_url(soup, url)
        # _strip_noise 가 script 를 지우기 전에 구조화 데이터(ld+json/Fusion) 본문 확보.
        structured = _structured_body(soup, resp.text)
        _strip_noise(soup)

        # 1) 본문 컨테이너 셀렉터를 **신뢰**한다. 매칭되는 셀렉터 중 가장 긴 텍스트를
        #    본문으로. 셀렉터는 기사 본문만 가리키므로 포털(다음·네이버)의 TTS·글자크기·
        #    번역 위젯·관련기사·제목 같은 chrome 이 섞이지 않는다(이게 핵심 — 과거엔
        #    '최대 텍스트 블록'을 무조건 취해 wrapper 의 chrome 까지 끌고 왔다).
        selector_texts: list[str] = []
        for sel in _CONTENT_SELECTORS:
            tag = soup.select_one(sel)
            if tag:
                text = _text_from_tag(tag)
                if len(text) >= _MIN_CONTENT_LEN:
                    selector_texts.append(text)
        best_dom = max(selector_texts, key=len) if selector_texts else ""
        # SPA(조선닷컴 등 Arc 계열): 본문 문단이 DOM 에 없어(JS 렌더) 셀렉터/폴백이
        # 빈손이 된다 → 구조화 데이터 본문이 DOM 보다 길면 그쪽을 신뢰.
        if len(structured) >= _MIN_CONTENT_LEN and len(structured) > len(best_dom):
            return {"content": structured, "image_url": image_url}
        if best_dom:
            return {"content": best_dom, "image_url": image_url}

        # 2) 본문 셀렉터가 하나도 없을 때만 폴백: 문단(<p>) 합치기 → 그래도 빈약하면
        #    링크 적은 '최대 텍스트 블록'. (비표준 마크업 사이트 대응.)
        candidates: list[str] = []
        paragraphs = [_clean_article_text(p.get_text(separator="\n", strip=True)) for p in soup.select("p")]
        paragraphs = [p for p in paragraphs if len(p) > 30]
        if paragraphs:
            candidates.append("\n".join(paragraphs))
        best_block = ""
        for block in soup.find_all(["div", "article", "section"]):
            try:
                if len(block.find_all("a")) > _FALLBACK_MAX_LINKS:
                    continue
                text = _text_from_tag(block)
            except Exception:  # noqa: BLE001 — 개별 블록 파싱 실패는 건너뛴다.
                continue
            if len(text) > len(best_block):
                best_block = text
        if best_block:
            candidates.append(best_block)

        content = max(candidates, key=len) if candidates else ""
        return {"content": content, "image_url": image_url}
    except Exception:  # noqa: BLE001 — 단일 페이지 파싱 실패가 전체 수집을 막지 않도록.
        logger.debug("기사 파싱 실패: %s", url, exc_info=True)
        return {"content": "", "image_url": ""}


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


def enrich_one(article: dict, *, with_llm: bool = True, session=None) -> dict:
    """단일 기사 enrich. 부수효과로 article dict 갱신, 동일 dict 반환.

    session: 재사용할 HTTP 세션(배치 enrich 가 같은 언론사 연결을 keep-alive 로
    재사용해 속도↑). None 이면 fetch_article 가 1회용 세션 생성.
    """
    from datetime import datetime, timezone

    link = article.get("link", "")
    content = _clean_article_text(article.get("content") or "")
    image_url = str(article.get("image_url") or "")
    # 리스트에서 가져온 이미지가 언론사 로고/플레이스홀더면 버린다 → fetch 의 og:image 가
    # 채우도록 유도(네이버 검색결과 로고만 가져오던 문제 등). fetch 결과 이미지는
    # _extract_image_url 가 이미 junk 를 걸러 반환하므로 그대로 우선한다.
    if is_junk_image(image_url):
        image_url = ""
    # 미해석 구글 뉴스 링크(news.google.com)는 인터스티셜 페이지라 fetch 하면 본문은
    # 비고 og:image 는 'Google News 로고'만 들어온다(카드 전부 같은 로고) → fetch 자체를
    # 건너뛴다. 원문이 풀린 링크(퍼블리셔 도메인)만 본문·og:image 를 가져온다.
    fetchable = bool(link) and "news.google.com" not in link
    if fetchable and (content_needs_refresh(content) or not image_url):
        fetched = fetch_article(link, session=session)
        content = fetched.get("content") or content
        image_url = fetched.get("image_url") or image_url
    # wrapper 폴백 추출 시 제목이 본문 첫 줄로 반복되는 것 제거(모달 제목 이중 노출 방지).
    content = _strip_title_echo(content, str(article.get("title") or ""))
    article["content"] = content
    article["image_url"] = image_url

    # 빈도 기반 키워드(LLM 무관) — 데이터 표/매칭에서 쓰는 keywords 채움. 이미 있으면 유지.
    if content and not str(article.get("keywords") or "").strip():
        from scraping.extract import extract_keywords
        article["keywords"] = extract_keywords(content, top_n=6)

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


def enrich_parallel(
    articles: list[dict],
    *,
    with_llm: bool = False,
    max_workers: int = 10,
    progress_cb: Callable[[int, int, dict | None], None] | None = None,
) -> list[dict]:
    """여러 기사의 본문/대표이미지/키워드를 **병렬**로 채운다(ThreadPoolExecutor).

    수집(`run_daily.collect_batch`) 직후 호출 — 검색 결과는 content 가 비어 있으므로
    각 기사 링크에서 본문·og:image 를 가져와 채운다. 입력 리스트를 in-place 갱신하고
    동일 리스트 반환(순서 유지). 개별 기사 실패는 격리해 배치를 막지 않는다.

    with_llm=False 가 기본(본문·이미지·빈도 키워드만, 빠름). LLM 요약/키워드가 필요하면
    True(느림) — collect 경로는 속도를 위해 False 로 호출한다.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total = len(articles)
    if total == 0:
        return articles

    # 배치 전체가 1개 세션을 공유 — 같은 언론사로의 연결을 keep-alive 로 재사용해
    # 매 기사 새 세션 생성·핸드셰이크 비용을 줄인다(requests.Session 은 GET 에 스레드
    # 안전). best-effort 라 재시도 1회.
    shared = build_session(total_retries=1, backoff_factor=0.3)

    def _work(art: dict) -> None:
        try:
            enrich_one(art, with_llm=with_llm, session=shared)
        except Exception:  # noqa: BLE001 — 단일 기사 enrich 실패가 배치를 막지 않게.
            logger.debug("기사 enrich 실패: %s", art.get("link"), exc_info=True)

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_work, art) for art in articles]
        for _ in as_completed(futures):
            done += 1
            if progress_cb:
                try:
                    progress_cb(done, total, None)
                except Exception:  # noqa: BLE001
                    pass
    return articles
