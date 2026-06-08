"""E2E 전체 사용 시나리오 시뮬레이션 — 시스템이 한 줄기로 유효하게 동작하는지 검증.

조선소 사용자(도장1팀·자동화1팀 홍길동)의 하루 워크플로를 **연결된 한 흐름**으로
시뮬레이션한다. 단위 테스트(782개)가 각 부품을 덮지만, 이 파일은 부품들이 **이어붙어**
실제 데이터가 수집→저장→매칭→기회→화면→LLM→보관함으로 흐르는지(조립 유효성)를 본다.

시나리오 맵:
  S1 수집     — 4개 출처(네트워크 mock) → news_db 영속화
  S2 로드맵   — 작업정의 → SQLite 동기화 → load_latest 재구성
  S3 매칭/기회 — 수집 뉴스 ↔ 작업 토큰 매칭 → 자동화 기회 셀 집계
  S4 네비게이션 — app.py 통해 5개 화면 전부 예외 없이 렌더(LLM graceful fallback)
  S5 카테고리  — 뉴스 수집 대분류 탭(키워드/포탈) + 출처칩으로 카드 좁힘(개편)
  S6 SOLA LLM — 요약·보드 브리핑(LLM mock) 프롬프트 조립·응답 처리
  S7 보관함   — 제안 북마크 → 보관함 렌더 → 채택 → 카운트 반영

외부 의존(네트워크·LLM)만 mock. 데이터 파이프라인·매칭·UI 조립은 실제 코드로 실행한다.
conftest 의 `_isolated_data_dirs` 로 tmp 격리되므로 각 테스트가 필요한 시드를 직접 만든다.
"""
from __future__ import annotations

import contextlib
import importlib
import json

import pandas as pd
import pytest
from unittest.mock import patch

from roadmap.schema import ALL_COLUMNS


# ── 시드 헬퍼 ──────────────────────────────────────────────

def _seed_persona() -> None:
    """도장1팀 홍길동 페르소나 저장 + 온보딩 모달 비활성(화면 직행)."""
    from persona import store as ps
    from persona.schema import Persona
    ps.save(Persona(
        name="홍길동", team="자동화1팀", dept="도장1팀",
        interest_tasks=["용접 자동화", "도장 검사"], interest_lv3=["용접 비드 검사"],
    ))
    ps.dismiss_onboarding()


def _row(**kw) -> dict:
    base = {c: "" for c in ALL_COLUMNS}
    base.update(kw)
    return base


def _tjson(pid: str, name: str, objectives: list[str]) -> str:
    return json.dumps(
        {"process_id": pid, "process_name": name, "objectives": objectives},
        ensure_ascii=False,
    )


def _seed_roadmap():
    """작업 정의 3건 → SQLite 동기화. task/objectives 에 매칭 토큰(용접·도장·절단) 포함."""
    from roadmap import sqlite_sync
    rows = [
        _row(team="자동화1팀", dept="도장1팀", division="용접", process="외판용접",
             task="용접 비드 품질 검사", sub_task="비드 형상 분석", process_id="WELD-001",
             task_def="용접 비드 품질을 비전으로 검사",
             task_def_json=_tjson("WELD-001", "용접 비드 검사", ["용접 결함 검출", "비드 형상 측정"])),
        _row(team="자동화1팀", dept="도장1팀", division="도장", process="외판도장",
             task="도장 표면 결함 검사", sub_task="핀홀 검출", process_id="PAINT-001",
             task_def="도장 표면 핀홀·결함을 머신비전으로 검출",
             task_def_json=_tjson("PAINT-001", "도장 결함 비전 검사", ["핀홀 검출", "막두께 측정"])),
        _row(team="가공팀", dept="가공팀", division="절단", process="강재절단",
             task="강재 절단 자동화", sub_task="플라즈마 절단", process_id="CUT-001",
             task_def="강재 절단 공정 자동화",
             task_def_json=_tjson("CUT-001", "강재 절단", ["절단 정밀도 향상"])),
    ]
    return sqlite_sync.sync_dataframe(pd.DataFrame(rows))


def _fake_naver(keyword: str, max_results: int = 10) -> list[dict]:
    pool = {
        "용접 자동화": [{"title": "용접 비드 품질 모니터링 기술 공개", "link": "https://n/w1",
                       "press": "AI Times", "source": "naver", "date": "2026-06-05",
                       "summary": "실시간 용접 비드 형상 분석"}],
        "도장 검사": [{"title": "머신비전 도장 결함 검출 솔루션", "link": "https://n/p1",
                     "press": "조선일보", "source": "naver", "date": "2026-06-05",
                     "summary": "도장 핀홀 비전 검출"}],
    }
    return pool.get(keyword, [{"title": f"{keyword} 일반 기사", "link": f"https://n/{keyword}",
                               "press": "Yonhap", "source": "naver", "date": "2026-06-05",
                               "summary": ""}])[:max_results]


def _fake_google(keyword: str, max_results: int = 10, **_) -> list[dict]:
    return [{"title": f"{keyword} 구글 뉴스", "link": f"https://g/{keyword}",
             "press": "Google", "source": "google", "date": "2026-06-05",
             "summary": ""}][:max_results]


def _fake_tech(max_results_per_site: int = 10, **_) -> list[dict]:
    return [{"title": "강재 절단 자동화 라인 도입", "link": "https://aw/cut",
             "press": "AutomationWorld", "source": "AI Times", "date": "2026-06-05",
             "summary": "플라즈마 절단 자동화"}]


def _seed_news_via_collect(monkeypatch):
    """네트워크 mock 후 실제 collect_batch 실행 → news_db 영속화."""
    from scraping import run_daily
    monkeypatch.setattr(run_daily.naver_news, "search", _fake_naver)
    monkeypatch.setattr(run_daily.google_news, "search", _fake_google)
    monkeypatch.setattr(run_daily.tech_sites, "search_all", _fake_tech)
    return run_daily.collect_batch(
        ["용접 자동화", "도장 검사"], sources=("naver", "google", "tech"), max_results=5,
    )


def _clear_ui_caches() -> None:
    """st.cache_data 는 테스트 간 전역 유지 → UI 화면 캐시를 비워 stale 방지."""
    mods_fns = [
        ("ui.data_management_v2", ["_news_cards_html", "_news_source_options", "_dm_stats",
                                   "_ingest_jobs_html", "_hist_html", "_archive_stats_dm",
                                   "_sc_browse_records"]),
        ("ui.board_v2", ["_board_kpis", "_archive_stats"]),
        ("ui.archive_v2", ["_oa_data", "_archive_stats_oa"]),
        ("ui.insights_v2", ["_ia_stats", "_archive_stats_ia"]),
    ]
    for modname, fns in mods_fns:
        with contextlib.suppress(Exception):
            mod = importlib.import_module(modname)
            for fn in fns:
                obj = getattr(mod, fn, None)
                if obj is not None and hasattr(obj, "clear"):
                    with contextlib.suppress(Exception):
                        obj.clear()


# ── S1: 수집 → 저장 ────────────────────────────────────────

def test_e2e_s1_collect_persists_news(monkeypatch):
    _seed_persona()
    report = _seed_news_via_collect(monkeypatch)
    assert report.total_articles > 0
    assert report.errors == []
    assert report.total_files >= 1

    from store import news_db
    df = news_db.load_all_today()
    assert not df.empty
    assert df["title"].str.contains("용접").any()
    assert df["title"].str.contains("도장").any()
    # 출처가 여러 개 (필터 시나리오 전제)
    assert df["source"].nunique() >= 2


# ── S2: 로드맵 ingest → SQLite → load_latest ──────────────

def test_e2e_s2_roadmap_ingest_and_load():
    res = _seed_roadmap()
    assert res.created == 3

    from store import task_defs_db
    assert task_defs_db.count() == 3

    from roadmap.query import load_latest
    rdf = load_latest()
    assert not rdf.empty
    assert {"lv3", "task", "task_def_json", "dept"} <= set(rdf.columns)
    # 라운드트립으로 작업 토큰 보존 (lv3=task fallback 또는 task_def_json flatten)
    blob = " ".join(rdf["task"].astype(str)) + " ".join(rdf["task_def_json"].astype(str))
    assert "용접" in blob and "도장" in blob


# ── S3: 매칭 + 자동화 기회 ─────────────────────────────────

def test_e2e_s3_match_and_opportunity(monkeypatch):
    _seed_persona()
    _seed_roadmap()
    _clear_ui_caches()
    _seed_news_via_collect(monkeypatch)

    from store import news_db, match
    from roadmap.query import load_latest
    from sola import opportunity

    news = news_db.load_news_for_days(days=3)
    rdf = load_latest()
    assert not news.empty and not rdf.empty

    matches = match.score_matches(news, rdf, top_k=5)
    assert not matches.empty
    assert (matches["score"] > 0).all()
    # 매칭이 용접·도장 기사를 작업과 실제로 연결
    assert matches["news_title"].str.contains("용접", na=False).any()
    assert matches["news_title"].str.contains("도장", na=False).any()

    cells = opportunity.score_cells(news, rdf)
    assert not cells.empty
    assert cells["matched_news"].sum() > 0
    assert cells["matched_tasks"].sum() > 0


# ── S4: app.py 통해 5개 화면 네비게이션 ────────────────────

_AREAS = [
    "📊 오늘의 보드", "🗞 뉴스 수집", "📋 작업 정의", "🔎 인사이트 분석",
    "🤖 SOLA 작업실", "📦 산출물 보관함",
]


def test_e2e_s4_navigate_all_screens(monkeypatch):
    _seed_persona()
    _seed_roadmap()
    _clear_ui_caches()
    _seed_news_via_collect(monkeypatch)

    from streamlit.testing.v1 import AppTest
    for area in _AREAS:
        at = AppTest.from_file("app.py", default_timeout=120)
        at.session_state["app_area"] = area
        at.run()
        assert not at.exception, f"{area} 렌더 예외: {at.exception}"
        assert at.get("html"), f"{area} 가 아무 html 도 렌더하지 않음"


# ── S5: 데이터 관리 출처 필터(신규 기능) 전체 앱에서 동작 ──

def test_e2e_s5_data_mgmt_category_browser(monkeypatch):
    _seed_persona()
    _clear_ui_caches()
    _seed_news_via_collect(monkeypatch)

    from store import news_db
    srcs = sorted(s for s in news_db.load_news_for_days(days=3)["source"].dropna().unique() if s)
    assert len(srcs) >= 2  # naver/google(키워드) + tech(포탈)

    from streamlit.testing.v1 import AppTest
    # 기본 카드뷰(키워드 카테고리) — 수집된 뉴스가 사진 카드로 노출
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["app_area"] = "🗞 뉴스 수집"
    at.run()
    assert not at.exception
    combined = "\n".join(h.proto.body for h in at.get("html"))
    assert "sc-card" in combined                       # 카드 브라우저 렌더
    assert "용접 비드 품질 모니터링" in combined        # naver(키워드) 카드 제목

    # 출처칩으로 '구글'만 좁히면 네이버 전용 카드는 사라진다(원클릭 카테고리 narrowing)
    at2 = AppTest.from_file("app.py", default_timeout=120)
    at2.session_state["app_area"] = "🗞 뉴스 수집"
    at2.session_state["sc_news_cat"] = "keyword"
    at2.session_state["sc_chan_keyword"] = "구글"
    at2.run()
    assert not at2.exception
    combined2 = "\n".join(h.proto.body for h in at2.get("html"))
    assert "구글 뉴스" in combined2                     # google 카드
    assert "용접 비드 품질 모니터링" not in combined2    # 네이버 전용 카드 제외


# ── S6: SOLA LLM 흐름 (mock) ───────────────────────────────

def test_e2e_s6_sola_llm_flows(monkeypatch):
    _seed_persona()
    _clear_ui_caches()
    _seed_news_via_collect(monkeypatch)

    from store import news_db
    news = news_db.load_news_for_days(days=3)
    assert not news.empty

    from sola import summarize
    with patch("sola.summarize.chat", return_value="• 용접·도장 자동화 동향 요약 3건"):
        out = summarize.summarize_news(news, max_items=5)
    assert "요약" in out                     # mock 응답이 반환됨(미리보기 폴백 아님)

    from sola import board_brief
    items = [{"title": t, "source": s}
             for t, s in zip(news["title"].head(3), news["source"].head(3))]
    with patch("sola.board_brief.chat", return_value="오늘의 브리핑: 자동화 기회 3건 두드러짐"):
        brief = board_brief.brief(items, "도장1팀 · 검사관", force=True)
    assert isinstance(brief, str) and "브리핑" in brief


# ── S7: 보관함 제안 채택 흐름 ──────────────────────────────

def test_e2e_s7_archive_proposal_flow():
    _seed_persona()
    _clear_ui_caches()

    from store import bookmarks
    from store.bookmarks import Bookmark
    bookmarks.add(Bookmark(id="prop-weld", type="proposal",
                           title="용접 비드 비전 검사 PoC 제안",
                           content="용접 비드 품질을 머신비전으로 자동 검사", tags=["용접", "비전"]))

    # 보관함 화면이 제안을 노출
    captured: list[str] = []
    import streamlit as st
    from ui import archive_v2
    st.query_params.clear(); st.session_state.clear()
    with patch("streamlit.rerun"), \
         patch("streamlit.html", side_effect=lambda s, **k: captured.append(s)):
        try:
            archive_v2.render()
        finally:
            st.query_params.clear(); st.session_state.clear()
    assert any("용접 비드 비전 검사 PoC" in c for c in captured)

    # 채택 → 카운트 반영
    assert bookmarks.set_status("prop-weld", "adopted") is True
    counts = bookmarks.summary_counts()
    assert counts["proposal_status"].get("adopted", 0) == 1
