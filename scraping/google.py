"""구글 뉴스 RSS 검색.

공식 API가 없어 RSS(`news.google.com/rss/search?q=...`)를 사용한다.
응답은 RFC822 날짜·`source` 태그를 가진 표준 RSS 2.0 XML.
"""
from __future__ import annotations

import base64
from email.utils import parsedate_to_datetime
import json
import re
from html import unescape
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import requests

from scraping.extract import is_junk_image, soup_of
from scraping.http import REQUEST_TIMEOUT, build_session, default_headers


_RSS_URL = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

# 구글 뉴스 RSS 의 media 네임스페이스(일부 항목에 대표 이미지 포함).
_MRSS = "{http://search.yahoo.com/mrss/}"
# 링크 해석용 타임아웃(리디렉트 추적·batchexecute — 본 RSS 타임아웃보다 짧게).
# 8s 는 데이터센터에서 batchexecute 응답이 느릴 때 서명 왕복이 잘려 실패를 키웠다 → 12s.
_RESOLVE_TIMEOUT = 12
# batchexecute(신 포맷 토큰 해석) 재시도 횟수 — 구글이 봇 의심으로 간헐 빈 응답/동의 페이지를
# 돌려주는 걸 1회 더 시도해 흡수. 실패 토큰만 재시도하므로 정상 경로엔 부담이 없다.
_BATCH_RETRIES = 1


def _apply_consent_cookies(session) -> None:
    """구글 동의(consent) 인터스티셜 우회 쿠키를 세션에 심는다.

    데이터센터 IP(Render 등)로 news.google.com 에 접근하면 구글이 쿠키 동의 페이지를
    돌려주는 경우가 있는데, 그러면 batchexecute 서명(`data-n-a-sg`) 추출이 실패해
    **원문 링크를 못 풀고 → 본문·사진이 통째로 비는** 핵심 원인이 된다. 브라우저가
    '동의 완료' 후 갖는 `CONSENT`/`SOCS` 쿠키를 미리 심어 실제 콘텐츠를 받게 한다.
    (pygooglenews·newspaper 등이 쓰는 표준 우회. 값 자체보다 '동의됨' 신호가 핵심.)
    """
    try:
        session.cookies.set("CONSENT", "YES+cb", domain=".google.com")
        session.cookies.set("SOCS", "CAISNQgQEitib3E", domain=".google.com")
    except Exception:  # noqa: BLE001 — 쿠키 주입 실패는 무시(정상 경로로 진행).
        pass


def _media_image(item) -> str:
    """RSS 항목의 media:content/thumbnail 대표 이미지(있으면). 로고류는 제외."""
    for name in ("content", "thumbnail"):
        tag = item.find(_MRSS + name)
        if tag is not None:
            url = (tag.attrib.get("url") or "").strip()
            if url.startswith("http") and not is_junk_image(url):
                return url
    return ""


def _read_varint(data: bytes, i: int) -> tuple[int, int]:
    """protobuf varint 디코드 → (값, 다음 인덱스)."""
    val = 0
    shift = 0
    while i < len(data):
        b = data[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, i
        shift += 7
    return val, i


def _decode_google_url(google_url: str) -> str:
    """`news.google.com/rss/articles/<base64>` 토큰을 디코드해 원문 URL 추출.

    신 CBM 포맷(`\\x08\\x13\\x22<len><url>…`)은 원문 URL 이 **length-delimited** 필드라,
    길이만큼 정확히 잘라야 한다. 과거엔 정규식이 URL 뒤 protobuf 바이트(`\\x32…`)까지
    끌어와 **깨진 URL**(예: `…/ABCDEF/2\\x05ko-KR`)을 반환 → enrich fetch 가 실패해 구글
    뉴스 본문·사진이 통째로 비던 핵심 버그였다. 신 포맷은 길이로, 구 포맷은 엄격 문자셋
    정규식으로 추출. URL 이 없으면(불투명 토큰) 빈 문자열 → 상위가 batchexecute/리디렉트로 폴백.
    """
    m = re.search(r"/articles/([A-Za-z0-9_\-]+)", google_url or "")
    if not m:
        return ""
    token = m.group(1)
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except Exception:  # noqa: BLE001 — 잘못된 패딩/문자
        return ""

    url = ""
    # 신 CBM 포맷: 0x08 0x13 0x22 <varint len> <url bytes> … (field 4 = 원문 URL)
    if raw[:3] == b"\x08\x13\x22":
        length, idx = _read_varint(raw, 3)
        if 0 < length <= len(raw) - idx:
            url = raw[idx:idx + length].decode("utf-8", "ignore")
    # 폴백(구 포맷): 평문에 박힌 http URL — 엄격 URL 문자셋(제어문자에서 끊겨 garbage 방지).
    if not url.startswith("http"):
        text = raw.decode("latin-1", "ignore")
        m2 = re.search(r"https?://[A-Za-z0-9._~:/?#@!$&'()*+,;=%\-\[\]]+", text)
        url = m2.group(0) if m2 else ""

    # 제어문자/비ASCII 가 섞였으면(잔여 garbage) 신뢰하지 않는다 → 상위가 다른 경로로 폴백.
    if not url.startswith("http") or re.search(r"[\x00-\x20\x7f-\xff]", url):
        return ""
    host = urlparse(url).netloc
    return url if (host and "google.com" not in host) else ""


def _parse_batchexecute(text: str) -> str:
    """구글 batchexecute 응답 텍스트에서 원문 URL 추출.

    응답은 `)]}'` 가드 + `\\n\\n` 구분 JSON. `["wrb.fr","Fbv4je","<inner-json>"...]`
    행의 inner JSON(`["garturlres","<URL>",...]`) 두 번째 원소가 원문 URL.
    """
    try:
        parts = text.split("\n\n")
        if len(parts) < 2:
            return ""
        rows = json.loads(parts[1])
        for row in rows:
            if isinstance(row, list) and len(row) >= 3 and row[0] == "wrb.fr" and row[2]:
                inner = json.loads(row[2])
                if (isinstance(inner, list) and len(inner) >= 2
                        and isinstance(inner[1], str) and inner[1].startswith("http")):
                    return inner[1]
    except Exception:  # noqa: BLE001 — 포맷 변경/파싱 실패는 빈 문자열로.
        pass
    return ""


def _batchexecute_decode(session, token: str, *, retries: int = _BATCH_RETRIES) -> str:
    """구글 뉴스 **신 포맷(불투명 토큰)** → 원문 URL. 구글 내부 batchexecute API 사용.

    1) `/rss/articles/<token>` 페이지에서 signature(`data-n-a-sg`)·timestamp
       (`data-n-a-ts`) 추출 → 2) batchexecute 로 POST → 응답에서 원문 URL 파싱.
    어떤 단계든 실패하면 빈 문자열(상위 폴백/안전망이 처리). 구글이 포맷을 바꾸면
    깨질 수 있는(fragile) 경로라 예외를 모두 흡수한다. 간헐적 봇 의심 응답(빈 서명/
    동의 페이지)은 `retries` 회 더 시도해 흡수한다(실패 토큰만 재시도 — 정상 경로 무부담).
    """
    if not token:
        return ""
    for attempt in range(retries + 1):
        url = _batchexecute_decode_once(session, token)
        if url:
            return url
    return ""


def _batchexecute_decode_once(session, token: str) -> str:
    """batchexecute 1회 시도(재시도는 `_batchexecute_decode` 가 관리)."""
    try:
        art = session.get(f"https://news.google.com/rss/articles/{token}",
                          headers=default_headers(), timeout=_RESOLVE_TIMEOUT)
        sg = re.search(r'data-n-a-sg="([^"]+)"', art.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', art.text)
        if not (sg and ts):
            return ""
        inner = (
            '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
            'null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
            f'"{token}",{ts.group(1)},"{sg.group(1)}"]'
        )
        freq = json.dumps([[["Fbv4je", inner, None, "generic"]]])
        resp = session.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers={**default_headers(),
                     "content-type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data={"f.req": freq},
            timeout=_RESOLVE_TIMEOUT,
        )
        return _parse_batchexecute(resp.text)
    except Exception:  # noqa: BLE001
        return ""


def _resolve_link_method(session, url: str) -> tuple[str, str]:
    """구글 뉴스 리디렉트 URL → (원문 URL, 복원방법). 실패 시 (원본, "unresolved").

    복원방법 라벨(수집 로그 통계용): "decoded"(base64) · "batch"(batchexecute) ·
    "redirect"(리디렉트 추적) · "unresolved"(전부 실패 — 본문·사진 못 가져옴).
    구글 링크가 아니면 ("passthrough") — 이미 원문(예: description 직링크)이라는 뜻.
    """
    if not url or "news.google.com" not in url:
        return url, "passthrough"
    decoded = _decode_google_url(url)
    if decoded:
        return decoded, "decoded"
    m = re.search(r"/articles/([A-Za-z0-9_\-]+)", url)
    if m:
        be = _batchexecute_decode(session, m.group(1))
        if be:
            return be, "batch"
    try:
        r = session.get(url, headers=default_headers(), timeout=_RESOLVE_TIMEOUT, allow_redirects=True)
        final = str(getattr(r, "url", "") or "")
        host = urlparse(final).netloc
        if final.startswith("http") and host and "google.com" not in host:
            return final, "redirect"
    except requests.RequestException:
        pass
    return url, "unresolved"


def _resolve_link(session, url: str) -> str:
    """구글 뉴스 리디렉트 URL → 원문 URL(best-effort). 실패 시 원본 그대로."""
    return _resolve_link_method(session, url)[0]


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


def _image_from_description(description: str) -> str:
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description or "", flags=re.IGNORECASE)
    return unescape(match.group(1)) if match else ""


def _extract_original_link(description: str) -> str:
    """RSS description 안의 **비-구글 원문 링크**(있으면). 일부 구글 뉴스 항목은
    description 의 `<a href>` 가 퍼블리셔 직링크라, 리디렉트 추적 없이 원문을 얻는다.
    (참고: jhr0966/News scraper.py 의 _extract_original_link 와 동일 전략.)
    """
    if not description:
        return ""
    try:
        soup = soup_of(description)
    except Exception:  # noqa: BLE001
        return ""
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if href.startswith("http") and "news.google.com" not in href:
            return href
    return ""


def _summary_echoes_title(summary: str, title: str, press: str) -> bool:
    """RSS description 이 '제목(+언론사)' 반복뿐인지 판정.

    구글 뉴스 RSS 의 description 은 `<a>제목</a>(·언론사)` 형태라 태그를 벗기면 제목이
    그대로 남는다 → 카드/모달이 본문 폴백으로 쓰면 제목이 두 번 보인다. 제목 외
    정보가 사실상 없으면 빈 summary 로 두는 편이 낫다(UI 가 content 로 폴백).
    """
    s = " ".join((summary or "").split())
    t = " ".join((title or "").split())
    if not s or not t:
        return False
    p = " ".join((press or "").split())
    return t in s and len(s) <= len(t) + len(p) + 16


def search(
    keyword: str,
    max_results: int = 10,
    *,
    hl: str = "ko",
    gl: str = "KR",
    stats_out: dict | None = None,
) -> list[dict]:
    """구글 뉴스 RSS 검색.

    stats_out(선택): 넘기면 원문 링크 **복원 방법별 카운트**를 채운다 —
    {direct, decoded, batch, redirect, unresolved}. unresolved 가 곧 '본문·사진을
    못 가져오는' 기사 수(구글 인터스티셜 링크가 안 풀린 것)라 수집 로그에서 실패율을
    바로 볼 수 있다.
    """
    if not keyword.strip():
        return []
    url = _RSS_URL.format(
        q=quote(keyword),
        hl=hl,
        gl=gl,
        ceid=f"{gl}:{hl}",
    )

    session = build_session()
    _apply_consent_cookies(session)  # 동의 인터스티셜 우회 — batchexecute 성공률↑.
    try:
        resp = session.get(url, headers=default_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"구글 뉴스 RSS 요청 실패: {e}") from e

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        raise RuntimeError(f"구글 뉴스 RSS 파싱 실패: {e}") from e

    # 1) RSS 파싱(링크 해석 전) — 중복 제거 + max_results 컷.
    parsed: list[dict] = []
    seen_links: set[str] = set()
    for item in root.findall(".//item")[:max_results * 2]:
        if len(parsed) >= max_results:
            break
        title_raw = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title_raw or not link or link in seen_links:
            continue
        seen_links.add(link)
        title, press_from_title = _split_title(title_raw)
        source_el = item.find("source")
        press = (source_el.text.strip() if source_el is not None and source_el.text else press_from_title)
        description = (item.findtext("description") or "").strip()
        parsed.append({
            "title": title,
            "press": press,
            "date": (item.findtext("pubDate") or "").strip(),
            "raw_link": link,
            "description": description,
            "image_url": _media_image(item) or _image_from_description(description),
        })

    # 2) 원문 링크 복원 — **병렬**. 신 포맷은 batchexecute(2요청)라 순차면 매우 느리다.
    #    우선순위: description 직링크 → base64/batchexecute/리디렉트(_resolve_link).
    import threading as _threading
    _stats = {"direct": 0, "decoded": 0, "batch": 0, "redirect": 0, "unresolved": 0}
    _stats_lock = _threading.Lock()

    def _resolve_one(p: dict) -> None:
        direct = _extract_original_link(p["description"])
        if direct:
            p["link"] = direct
            method = "direct"
        else:
            p["link"], method = _resolve_link_method(session, p["raw_link"])
        with _stats_lock:
            # passthrough(구글 링크 아님)는 direct 로 합산 — 이미 원문이라는 뜻.
            _stats["direct" if method == "passthrough" else method] += 1

    if parsed:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(6, len(parsed))) as ex:
            list(ex.map(_resolve_one, parsed))

    if stats_out is not None:
        for k, v in _stats.items():
            stats_out[k] = stats_out.get(k, 0) + v

    # 3) 기사 dict 빌드.
    out: list[dict] = []
    for p in parsed:
        # 태그 제거 + HTML 엔티티(&nbsp; 등) 해제 + 공백 정리(폴백 노출 시 깨짐 방지).
        summary = " ".join(unescape(re.sub(r"<[^>]+>", " ", p["description"])).split())
        if _summary_echoes_title(summary, p["title"], p["press"]):
            summary = ""  # 제목 반복뿐 → 비워서 UI 가 본문(content)으로 폴백하게.
        out.append({
            "title": p["title"],
            "press": p["press"],
            "date": p["date"],
            "published_at": _to_iso(p["date"]),
            "link": p["link"],
            "summary": summary,
            "image_url": p["image_url"],
            "keywords": "",
            "source": "google",
            "query": keyword,
        })
    return out
