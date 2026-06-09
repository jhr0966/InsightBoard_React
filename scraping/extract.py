"""공통 추출 유틸: 날짜 정규화, 키워드 추출, HTML 셀렉터 시도."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup


def pick_parser() -> str:
    try:
        BeautifulSoup("<x/>", "lxml")
        return "lxml"
    except Exception:
        return "html.parser"


_HTML_PARSER = pick_parser()


def soup_of(markup: str) -> BeautifulSoup:
    return BeautifulSoup(markup, _HTML_PARSER)


def normalize_published_at(date_text: str, now_utc: datetime | None = None) -> str:
    """기사 날짜 텍스트 → UTC ISO8601. 실패 시 빈 문자열."""
    if not date_text:
        return ""
    now = now_utc or datetime.now(timezone.utc)
    text = date_text.strip()

    for unit, delta in (("분", "minutes"), ("시간", "hours"), ("일", "days")):
        m = re.search(rf"(\d+)\s*{unit}\s*전", text)
        if m:
            return (now - timedelta(**{delta: int(m.group(1))})).replace(microsecond=0).isoformat()

    cleaned = text.replace(".", "-").strip("- ")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
            return parsed.replace(microsecond=0).isoformat()
        except ValueError:
            continue
    return ""


_STOPWORDS = {
    "기자", "연합뉴스", "뉴스", "사진", "무단전재", "재배포", "금지", "특파원", "이", "그", "저",
    "것", "수", "등", "및", "하는", "있는", "위해", "대해", "관련", "이번", "가운데", "따르면",
    "대비", "했다", "결과", "통해", "위한", "비해", "경우", "때문에", "따라", "최근", "대한", "가장",
    "오늘", "내일", "어제", "올해", "작년", "지난", "이날", "당시", "현재", "지금",
    "보도", "기사", "취재", "발표", "전했다", "밝혔다", "말했다", "설명했다",
    "있다", "없다", "된다", "한다",
}


def extract_keywords(text: str, top_n: int = 5) -> str:
    if not text:
        return ""
    words = re.findall(r"[가-힣a-zA-Z0-9]+", text)
    filtered = [w for w in words if len(w) > 1 and w not in _STOPWORDS]
    if not filtered:
        return ""
    return ", ".join(w for w, _ in Counter(filtered).most_common(top_n))


# 대표 이미지로 부적합한(언론사 로고/엠블럼/아이콘/플레이스홀더/투명) URL 조각.
# 네이버 검색결과의 언론사 로고, 공용 placeholder 등을 본문 대표 이미지로 오인하는 것을 막는다.
_JUNK_IMAGE_FRAGMENTS = (
    "logo", "emblem", "favicon", "sprite", "spacer", "1x1", "transparent",
    "noimage", "no_image", "no-image", "blank.", "placeholder", "watermark",
    "avatar", "/ci/", "ci_", "default_profile", "btn_", "_btn.", "/sns",
)


def is_junk_image(url: str) -> bool:
    """대표 이미지로 부적합한(로고/아이콘/플레이스홀더/data URI) URL 인지 휴리스틱 판정.

    빈 문자열도 junk(True) 로 본다 — 호출부가 'junk면 버리고 og:image 로 교체' 하기 쉽게.
    """
    if not url:
        return True
    low = url.lower()
    if low.startswith("data:"):
        return True
    return any(frag in low for frag in _JUNK_IMAGE_FRAGMENTS)


def first_text(parent, selectors: list[str]) -> str:
    for sel in selectors:
        tag = parent.select_one(sel)
        if tag:
            return tag.get_text(strip=True)
    return ""


def first_tag(parent, selectors: list[str]):
    for sel in selectors:
        tag = parent.select_one(sel)
        if tag:
            return tag
    return None
