"""뉴스 대표 이미지 추출 개선 — 로고/플레이스홀더 제외 + og:image 우선 + 구글 링크 복원.

네이버는 언론사 로고만 가져오던 문제, 구글은 이미지 0건(리디렉트 URL 미복원),
og:image 가 로고면 본문 이미지로 폴백 — 결정적(네트워크 무관) 부분을 검증한다.
"""
from __future__ import annotations

import base64
from unittest.mock import patch
from xml.etree import ElementTree as ET

from scraping import enrich, google, naver
from scraping.extract import is_junk_image, soup_of


# ── is_junk_image ──────────────────────────────────────────

def test_is_junk_image():
    assert is_junk_image("https://x/press_logo.png")
    assert is_junk_image("https://x/favicon.ico")
    assert is_junk_image("data:image/gif;base64,AAAA")
    assert is_junk_image("")                                   # 빈 값도 junk
    assert not is_junk_image("https://x/2026/06/main_photo.jpg")


# ── naver: 로고 건너뛰고 기사 썸네일 ────────────────────────

def test_naver_image_skips_press_logo():
    item = soup_of(
        '<div class="bx">'
        '<img src="https://imgnews/press_logo.png">'          # 언론사 로고(먼저 등장)
        '<img data-src="https://imgnews/2026/thumb_main.jpg">'  # 실제 기사 썸네일
        '</div>'
    ).div
    assert naver._image_from_item(item) == "https://imgnews/2026/thumb_main.jpg"


def test_naver_image_empty_when_only_logo():
    item = soup_of('<div><img src="https://imgnews/logo_emblem.png"></div>').div
    assert naver._image_from_item(item) == ""   # 로고뿐 → 빈 값(enrich 가 og:image 로 채움)


# ── google: media 이미지 + 링크 복원 ───────────────────────

def test_google_media_image():
    item = ET.fromstring(
        '<item xmlns:media="http://search.yahoo.com/mrss/">'
        '<media:content url="https://img.example.com/main.jpg"/>'
        '</item>'
    )
    assert google._media_image(item) == "https://img.example.com/main.jpg"


def test_google_media_image_rejects_logo():
    item = ET.fromstring(
        '<item xmlns:media="http://search.yahoo.com/mrss/">'
        '<media:thumbnail url="https://img.example.com/site_logo.png"/>'
        '</item>'
    )
    assert google._media_image(item) == ""


def test_google_decode_url_extracts_embedded_original():
    original = "https://example.com/news/article/123"
    token = base64.urlsafe_b64encode(
        b"\x08\x13\x22" + original.encode() + b'"trailing'
    ).decode().rstrip("=")
    gurl = f"https://news.google.com/rss/articles/{token}?oc=5"
    assert google._decode_google_url(gurl) == original


def test_google_decode_url_opaque_returns_empty():
    opaque = base64.urlsafe_b64encode(b"\x08\x13\x22opaque-id-no-url").decode().rstrip("=")
    gurl = f"https://news.google.com/rss/articles/{opaque}"
    assert google._decode_google_url(gurl) == ""


def test_google_extract_original_link_from_description():
    desc = '<a href="https://pub.example.com/article/5">기사 제목</a>&nbsp;<font>언론사</font>'
    assert google._extract_original_link(desc) == "https://pub.example.com/article/5"
    # 구글 링크만 있으면 빈 문자열(→ 디코드/리디렉트로 폴백)
    assert google._extract_original_link('<a href="https://news.google.com/rss/articles/x">t</a>') == ""


def test_google_resolve_prefers_decode_no_request():
    """디코드로 풀리면 네트워크 요청 없이 원문 URL 을 돌려준다."""
    original = "https://pub.example.com/a/b"
    token = base64.urlsafe_b64encode(b"\x08\x13\x22" + original.encode() + b'"x').decode().rstrip("=")
    gurl = f"https://news.google.com/rss/articles/{token}"

    class _Boom:
        def get(self, *a, **k):
            raise AssertionError("디코드 성공 시 요청하면 안 됨")

    assert google._resolve_link(_Boom(), gurl) == original


# ── enrich: og:image 가 로고면 본문 이미지로 폴백 ─────────

def test_extract_image_skips_logo_og_uses_content_img():
    html = (
        '<html><head><meta property="og:image" content="https://x/press_logo.png"></head>'
        '<body><article><img src="https://x/2026/real_photo.jpg"><p>본문</p></article></body></html>'
    )
    img = enrich._extract_image_url(soup_of(html), "https://x/")
    assert img == "https://x/2026/real_photo.jpg"


def test_enrich_one_drops_logo_list_image_for_og():
    art = {"link": "https://x/a", "content": "", "image_url": "https://x/press_logo.png"}
    fetched = {"content": "충분히 긴 본문 내용입니다. " * 10, "image_url": "https://x/og_main.jpg"}
    with patch.object(enrich, "fetch_article", return_value=fetched):
        enrich.enrich_one(art, with_llm=False)
    assert art["image_url"] == "https://x/og_main.jpg"   # 로고 버리고 og:image 채택
