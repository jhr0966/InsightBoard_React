"""뉴스 수집 개편 — 카테고리 카드 브라우저 + 기사 모달 단위 테스트.

대분류(키워드/포탈) 분류, 출처칩, 사진 카드(이미지 스킴 방어·모달 앵커), 카드
필터(카테고리·채널·검색), 기사 모달(본문 전체·원본 링크) 동작을 검증한다.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    assert dm._news_channel_of("naver") == "네이버 뉴스"
    assert dm._news_channel_of("google") == "구글 뉴스"
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
    assert chans["네이버 용접 기사"] == "네이버 뉴스"
    assert chans["AI Times 비전 기사"] == "AI Times"
    assert chans["커스텀 RSS 기사"] == "조선해양e뉴스"


def test_channels_per_category():
    dm._sc_browse_records.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        kw = dm._sc_channels("keyword")
        pt = dm._sc_channels("portal")
    assert kw == ["네이버 뉴스", "구글 뉴스"]
    assert set(pt) == {"AI Times", "조선해양e뉴스"}


# ── 카드 시각 HTML (이미지·escape, 앵커 없음) ─────────────────

def test_card_visual_html_image_and_escape():
    row = {"title": "<b>위험</b> 제목", "source": "naver", "press": "", "link": "https://x",
           "summary": "요약 본문", "image_url": "https://img/x.jpg",
           "collected_at": "2026-06-05T10:00:00Z"}
    html = dm._sc_card_visual_html(row)
    assert "<img src=" in html and "https://img/x.jpg" in html  # 실제 사진
    assert "&lt;b&gt;위험&lt;/b&gt;" in html                     # 제목 XSS escape
    assert "sc-card" in html and "네이버" in html
    # 카드 자체엔 앵커가 없다 — 클릭은 오버레이 버튼이 처리(문서 reload 없음)
    assert "<a " not in html and "news=" not in html


def test_card_visual_non_http_image_falls_back():
    row = {"title": "t", "source": "naver", "link": "https://x",
           "image_url": "javascript:alert(1)"}
    html = dm._sc_card_visual_html(row)
    assert "<img" not in html             # 비 http 스킴 → 이미지 미삽입(XSS 방어)
    assert "sc-card-img-ph" in html       # 그라데이션 플레이스홀더


# ── 레코드 필터 (카테고리·채널·검색) ───────────────────────

def test_filtered_records_category_and_channel():
    dm._sc_browse_records.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        kw_all = dm._sc_filtered_records("keyword", dm._SC_ALL_CHANNEL, "")
        kw_naver = dm._sc_filtered_records("keyword", "네이버 뉴스", "")
        portal = dm._sc_filtered_records("portal", dm._SC_ALL_CHANNEL, "")
    titles_all = {r["title"] for r in kw_all}
    assert {"네이버 용접 기사", "구글 도장 기사"} <= titles_all
    assert "AI Times 비전 기사" not in titles_all          # 포탈 제외
    assert {r["title"] for r in kw_naver} == {"네이버 용접 기사"}
    assert "AI Times 비전 기사" in {r["title"] for r in portal}


def test_filtered_records_search_query():
    dm._sc_browse_records.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        recs = dm._sc_filtered_records("keyword", dm._SC_ALL_CHANNEL, "도장")
    titles = {r["title"] for r in recs}
    assert "구글 도장 기사" in titles and "네이버 용접 기사" not in titles


def test_empty_state_html_and_no_records():
    dm._sc_browse_records.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=pd.DataFrame()):
        recs = dm._sc_filtered_records("portal", dm._SC_ALL_CHANNEL, "")
    assert recs == []
    assert "sc-empty" in dm._sc_empty_html("")


# ── 기사 모달 ──────────────────────────────────────────────

def test_find_record_by_link():
    dm._sc_browse_records.clear()
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()):
        r = dm._find_news_record_by_link("https://c")
        miss = dm._find_news_record_by_link("https://nope")
    assert r is not None and r["title"] == "AI Times 비전 기사"
    assert miss is None


def _modal_action_cols():
    """모달 하단 액션 행(st.columns) 대역 — 닫기 버튼은 미클릭 상태."""
    c1, c2 = MagicMock(), MagicMock()
    c2.button.return_value = False
    return c1, c2


def test_modal_body_renders_content_link_and_escapes():
    row = {"title": "모달 <제목>", "source": "tech", "press": "AI Times", "link": "https://c",
           "summary": "한줄 요약", "content": "문단1\n문단2", "image_url": "https://img/c.jpg",
           "collected_at": "2026-06-03T10:00:00Z"}
    captured: list[str] = []
    c1, c2 = _modal_action_cols()
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)), \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.columns", return_value=(c1, c2)):
        dm._news_modal_body(row)
    html = "\n".join(captured)
    assert "모달 &lt;제목&gt;" in html                   # 제목 escape
    assert "문단1" in html and "문단2" in html            # 본문 단락 전체
    assert "한줄 요약" not in html                        # content 있으면 요약 중복 노출 안 함
    assert "원본 기사 열기" in html and "https://c" in html  # 원본 링크
    assert 'src="https://img/c.jpg"' in html             # 모달 상단 사진


def test_modal_action_row_places_link_beside_close_button():
    """원본 기사 열기 링크와 ✕ 닫기 버튼이 같은 라인(2컬럼 행)에 병렬 배치돼야 한다."""
    row = {"title": "T", "source": "tech", "press": "", "link": "https://c",
           "summary": "", "content": "본문", "image_url": ""}
    captured: list[str] = []
    c1, c2 = _modal_action_cols()
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)), \
         patch("streamlit.button", return_value=False) as top_btn, \
         patch("streamlit.columns", return_value=(c1, c2)) as cols:
        dm._news_modal_body(row)
    cols.assert_called_once()                             # 액션 행 = 2컬럼
    assert "sc-modal-link--row" in "\n".join(captured)    # 링크가 행 전용 스타일로 1열에
    c2.button.assert_called_once()                        # 닫기 버튼이 2열에
    top_btn.assert_not_called()                           # 전폭 닫기 버튼은 미사용


def test_modal_body_falls_back_to_summary_when_no_content():
    """본문 미수집(content 없음)이면 요약을 본문 자리에 노출."""
    row = {"title": "T", "source": "naver", "press": "", "link": "https://x",
           "summary": "검색 요약 문장", "content": "", "image_url": ""}
    captured: list[str] = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)), \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.columns", return_value=_modal_action_cols()):
        dm._news_modal_body(row)
    assert "검색 요약 문장" in captured[0]


def test_modal_opens_from_news_query():
    """카드 클릭(?news=link) → 세션 플래그 + 기사 모달 렌더 + 파라미터 소비."""
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona
    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    dm._sc_browse_records.clear()

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


def _seed_app():
    from streamlit.testing.v1 import AppTest
    from persona import store as ps
    from persona.schema import Persona
    ps.reset(); ps.clear_onboarding_dismiss()
    ps.save(Persona(name="홍길동", dept="도장1팀", team="자동화1팀"))
    dm._sc_browse_records.clear()
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["app_area"] = "🗞 뉴스 수집"
    return at


def test_card_click_opens_modal_without_reload():
    """카드 오버레이 버튼(소켓 rerun) 클릭 → reload 없이 _sc_open_news 세팅 → 모달."""
    at = _seed_app()
    at.session_state["sc_news_cat"] = "keyword"
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()), \
         patch.object(dm._news_db, "load_all_today", return_value=_news_df()):
        at.run()
        assert not at.exception
        btns = [b for b in at.button if b.key == "sc_open_0"]
        assert btns, "카드 오버레이 버튼(sc_open_0)이 없음"
        btns[0].click().run()
    assert not at.exception
    assert "_sc_open_news" in at.session_state and at.session_state["_sc_open_news"]
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "sc-modal" in combined                                # 클릭 한 번에 모달


def test_table_view_renders_dataframe_with_body():
    """📋 데이터 표 모드 — 수집한 모든 뉴스가 st.dataframe 으로 렌더(본문 컬럼 포함)."""
    at = _seed_app()
    at.session_state["sc_browse_mode"] = "table"
    with patch.object(dm._news_db, "load_news_for_days", return_value=_news_df()), \
         patch.object(dm._news_db, "load_all_today", return_value=_news_df()):
        at.run()
    assert not at.exception
    assert len(at.dataframe) >= 1                                 # 데이터 표 존재
    cols = list(at.dataframe[0].value.columns)
    assert "본문" in cols and "제목" in cols and "사진" in cols    # 본문 포함
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "sc-empty" not in combined                            # 데이터 있으니 빈 상태 아님


def test_table_row_selection_opens_modal():
    """데이터 표 행 선택 → 해당 기사 모달 플래그(_sc_open_news) 세팅(reload 없는 소켓 rerun)."""
    import streamlit as st
    from types import SimpleNamespace
    st.session_state.clear()
    recs = [
        {"link": "https://a", "title": "A", "_cat": "keyword", "_chan": "네이버", "content": "본문A"},
        {"link": "https://b", "title": "B", "_cat": "portal", "_chan": "AI Times", "content": "본문B"},
    ]
    event = SimpleNamespace(selection=SimpleNamespace(rows=[1]))   # 두 번째 행 선택
    with patch.object(dm, "_sc_browse_records", return_value=recs), \
         patch("streamlit.dataframe", return_value=event), \
         patch("streamlit.caption"), patch("streamlit.rerun"):
        dm._render_news_table("")
    assert st.session_state.get("_sc_open_news") == "https://b"   # 선택 행 모달
    assert st.session_state.get("_sc_table_sel") == "https://b"

    # 같은 선택이 남아도(닫은 직후) 재오픈하지 않는다(가드)
    st.session_state.pop("_sc_open_news", None)
    with patch.object(dm, "_sc_browse_records", return_value=recs), \
         patch("streamlit.dataframe", return_value=event), \
         patch("streamlit.caption"), patch("streamlit.rerun"):
        dm._render_news_table("")
    assert "_sc_open_news" not in st.session_state               # 재오픈 안 함
    st.session_state.clear()


# ── 본문 폴백(제목 에코 방어) + 이미지 https 승격 ──────────────


def test_news_body_src_skips_title_echo_summary():
    """summary 가 '제목(+언론사)' 반복뿐이면 건너뛰고 content 로 폴백해야 한다."""
    row = {"title": "[단독] AI 글라스 커닝 적발",
           "summary": "[단독] AI 글라스 커닝 적발 스포츠경향",
           "content": "전기기사 시험에서 부정행위가 적발됐다."}
    body = dm._news_body_src(row, ("summary_llm", "summary", "content"))
    assert body == "전기기사 시험에서 부정행위가 적발됐다."
    # 실제 요약(제목과 다른 텍스트)은 그대로 사용
    row2 = {"title": "T제목입니다 충분히 김", "summary": "현장 적용이 확대되고 있다는 분석이다."}
    assert "확대" in dm._news_body_src(row2, ("summary", "content"))


def test_card_excerpt_uses_content_when_summary_echoes_title():
    """summary 가 제목 에코, content 도 '제목\\n본문'(레거시) — 발췌엔 본문만 남아야 한다."""
    row = {"title": "[단독] AI 글라스 커닝 적발", "source": "google", "press": "스포츠경향",
           "summary": "[단독] AI 글라스 커닝 적발 스포츠경향",
           "content": "[단독] AI 글라스 커닝 적발\n전기기사 시험에서 부정행위가 적발됐다.",
           "image_url": "", "collected_at": "2026-06-09T10:00:00Z"}
    html = dm._sc_card_visual_html(row)
    assert "부정행위가 적발됐다" in html          # 본문 자리에 content 본문
    assert html.count("AI 글라스 커닝 적발") == 1  # 제목은 h 영역 한 번만(발췌 미반복)


def test_https_img_upgrades_plain_http():
    assert dm._https_img("http://cdn.x.kr/a.jpg") == "https://cdn.x.kr/a.jpg"
    assert dm._https_img("https://cdn.x.kr/a.jpg") == "https://cdn.x.kr/a.jpg"
    assert dm._https_img("") == ""


def test_modal_body_skips_title_line_and_echo_summary():
    """모달: 레거시 content 의 제목 첫 줄은 걸러지고, 제목뿐인 content 면 요약으로 폴백."""
    title = "[단독] AI 글라스 커닝 적발 보도"
    row = {"title": title, "source": "google", "press": "", "link": "https://x",
           "summary": "실제 요약 문장이 따로 있다.",
           "content": f"{title}\n본문 첫 문단이다.", "image_url": ""}
    captured: list[str] = []
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)), \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.columns", return_value=_modal_action_cols()):
        dm._news_modal_body(row)
    body_html = captured[0]
    assert "본문 첫 문단이다" in body_html
    assert body_html.count("AI 글라스 커닝 적발 보도") == 1   # h2 한 번만

    # content 가 제목 한 줄뿐이면 → 요약 폴백
    row2 = dict(row, content=title)
    captured.clear()
    with patch("streamlit.html", side_effect=lambda s: captured.append(s)), \
         patch("streamlit.button", return_value=False), \
         patch("streamlit.columns", return_value=_modal_action_cols()):
        dm._news_modal_body(row2)
    assert "실제 요약 문장이 따로 있다" in captured[0]
