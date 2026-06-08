"""뉴스 수집 개편 — 카테고리 카드 브라우저 + 기사 모달 단위 테스트.

대분류(키워드/포탈) 분류, 출처칩, 사진 카드(이미지 스킴 방어·모달 앵커), 카드
필터(카테고리·채널·검색), 기사 모달(본문 전체·원본 링크) 동작을 검증한다.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ui import data_management_v2 as dm


def _news_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"title": "네이버 용접 기사", "source": "naver", "press": "조선일보", "link": "https://a",
         "summary": "용접 자동화 요약", "content": "용접 본문", "image_url": "https://img/a.jpg",
         "collected_at": "2026-06-05T10:00:00Z", "keywords": ""},
        {"title": "구글 도장 기사", "source": "google", "press": "Google", "link": "https://b",
         "summary": "", "content": "도장 본문", "image_url": "",
         "collected_at": "2026-06-04T10:00:00Z", "keywords": ""},
        {"title": "AI Times 비전 기사", "source": "tech", "press": "AI Times", "link": "https://c",
         "summary": "비전 요약", "content": "문단1\n문단2", "image_url": "https://img/c.jpg",
         "collected_at": "2026-06-03T10:00:00Z", "keywords": ""},
        {"title": "커스텀 RSS 기사", "source": "조선해양e뉴스", "press": "", "link": "https://d",
         "summary": "", "content": "", "image_url": "",
         "collected_at": "2026-06-02T10:00:00Z", "keywords": ""},
    ])


# ── 대분류 / 채널 분류 ──────────────────────────────────────

def test_category_of():
    assert dm._news_category_of("naver") == "keyword"
    assert dm._news_category_of("google") == "keyword"
    assert dm._news_category_of("tech") == "portal"
    assert dm._news_category_of("조선해양e뉴스") == "portal"
    assert dm._news_category_of("") == "portal"


def test_channel_of():
    assert dm._news_channel_of("naver") == "네이버"
    assert dm._news_channel_of("google") == "구글"
    assert dm._news_channel_of("tech", "AI Times") == "AI Times"
    assert dm._news_channel_of("tech", "오토메이션월드") == "오토메이션월드"
    assert dm._news_channel_of("조선해양e뉴스", "") == "조선해양e뉴스"
    assert dm._news_channel_of("", "") == "기타"


# ── browse records + channels ──────────────────────────────

def test_browse_records_annotates_and_sorts():
    dm._sc_browse_records.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        recs = dm._sc_browse_records()
    assert recs[0]["title"] == "네이버 용접 기사"          # 최신순
    cats = {r["title"]: r["_cat"] for r in recs}
    assert cats["네이버 용접 기사"] == "keyword"
    assert cats["AI Times 비전 기사"] == "portal"
    chans = {r["title"]: r["_chan"] for r in recs}
    assert chans["네이버 용접 기사"] == "네이버"
    assert chans["AI Times 비전 기사"] == "AI Times"
    assert chans["커스텀 RSS 기사"] == "조선해양e뉴스"


def test_channels_per_category():
    dm._sc_browse_records.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        kw = dm._sc_channels("keyword")
        pt = dm._sc_channels("portal")
    assert kw == ["네이버", "구글"]
    assert set(pt) == {"AI Times", "조선해양e뉴스"}


# ── 카드 HTML (이미지·앵커·escape) ─────────────────────────

def test_card_html_image_and_anchor():
    row = {"title": "<b>위험</b> 제목", "source": "naver", "press": "", "link": "https://x?a=1&b=2",
           "summary": "요약 본문", "image_url": "https://img/x.jpg",
           "collected_at": "2026-06-05T10:00:00Z"}
    html = dm._sc_news_card_html(row)
    assert "<img src=" in html and "https://img/x.jpg" in html  # 실제 사진
    assert "news=" in html                                       # 기사 모달 앵커
    assert "&lt;b&gt;위험&lt;/b&gt;" in html                     # 제목 XSS escape
    assert "sc-card" in html and "네이버" in html


def test_card_html_non_http_image_falls_back():
    row = {"title": "t", "source": "naver", "link": "https://x",
           "image_url": "javascript:alert(1)"}
    html = dm._sc_news_card_html(row)
    assert "<img" not in html             # 비 http 스킴 → 이미지 미삽입(XSS 방어)
    assert "sc-card-img-ph" in html       # 그라데이션 플레이스홀더


# ── 카드 필터 (카테고리·채널·검색) ─────────────────────────

def test_cards_html_filters_category_and_channel():
    dm._sc_browse_records.clear(); dm._sc_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        kw_all = dm._sc_cards_html("keyword", dm._SC_ALL_CHANNEL, "")
    assert "네이버 용접 기사" in kw_all and "구글 도장 기사" in kw_all
    assert "AI Times 비전 기사" not in kw_all     # 포탈 카테고리 제외
    dm._sc_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        kw_naver = dm._sc_cards_html("keyword", "네이버", "")
    assert "네이버 용접 기사" in kw_naver and "구글 도장 기사" not in kw_naver


def test_cards_html_search_query():
    dm._sc_browse_records.clear(); dm._sc_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        html = dm._sc_cards_html("keyword", dm._SC_ALL_CHANNEL, "도장")
    assert "구글 도장 기사" in html and "네이버 용접 기사" not in html


def test_cards_html_empty_state():
    dm._sc_browse_records.clear(); dm._sc_cards_html.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()):
        html = dm._sc_cards_html("portal", dm._SC_ALL_CHANNEL, "")
    assert "sc-empty" in html


# ── 기사 모달 ──────────────────────────────────────────────

def test_find_record_by_link():
    dm._sc_browse_records.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        r = dm._find_news_record_by_link("https://c")
        miss = dm._find_news_record_by_link("https://nope")
    assert r is not None and r["title"] == "AI Times 비전 기사"
    assert miss is None


def test_modal_body_renders_content_link_and_escapes():
    import streamlit as st
    row = {"title": "모달 <제목>", "source": "tech", "press": "AI Times", "link": "https://c",
           "summary": "한줄 요약", "content": "문단1\n문단2", "image_url": "https://img/c.jpg",
           "collected_at": "2026-06-03T10:00:00Z"}
    captured: list[str] = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)), \
         patch("streamlit.button", return_value=False):
        dm._news_modal_body(row)
    html = captured[0]
    assert "모달 &lt;제목&gt;" in html                   # 제목 escape
    assert "문단1" in html and "문단2" in html            # 본문 단락 전체
    assert "한줄 요약" in html                            # 요약 블록
    assert "원본 기사 열기" in html and "https://c" in html  # 원본 링크
    assert 'src="https://img/c.jpg"' in html             # 모달 상단 사진


def test_modal_opens_from_news_query():
    """카드 클릭(?news=link) → 세션 플래그 + 기사 모달 렌더 + 파라미터 소비."""
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona
    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    dm._sc_browse_records.clear(); dm._sc_cards_html.clear()

    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["app_area"] = "🗞 뉴스 수집"
    at.query_params["news"] = "https://c"
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()), \
         patch.object(dm._news_db, "load_all_today", return_value=_news_df()):
        at.run()
    assert not at.exception
    assert "_sc_open_news" in at.session_state                    # 플래그 세팅
    assert at.session_state["_sc_open_news"] == "https://c"
    assert "news" not in at.query_params                          # 파라미터 1회 소비
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "sc-modal" in combined                                # 모달 본문 렌더
    assert "AI Times 비전 기사" in combined                       # 해당 link 의 기사
