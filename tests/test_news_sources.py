"""ui.news_sources — 소스 표기 단일화(라벨·분류·그라데이션) + 집계 표 사이트 분해."""
from __future__ import annotations

import pytest

from ui import news_sources as ns


@pytest.fixture
def isolated_sources(tmp_path, monkeypatch):
    """store/sources 의 config.json 을 임시 디렉토리로 격리."""
    cfg_dir = tmp_path / "sources"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    from store import sources as src_store
    monkeypatch.setattr(src_store, "_config_path",
                        lambda: cfg_dir / "config.json")
    yield src_store


def test_source_label_keyword_and_portal():
    assert ns.source_label("naver") == "네이버 뉴스"
    assert ns.source_label("google") == "구글 뉴스"
    assert ns.source_label("tech", "AI Times") == "AI Times"
    assert ns.source_label("tech", "오토메이션월드") == "오토메이션월드"
    assert ns.source_label("tech") == "뉴스 포탈"          # legacy(무 press) 폴백
    assert ns.source_label("조선해양e뉴스") == "조선해양e뉴스"  # 커스텀 등록명 그대로
    assert ns.source_label("") == "기타"


def test_category_of():
    assert ns.category_of("naver") == "keyword"
    assert ns.category_of("google") == "keyword"
    assert ns.category_of("tech") == "portal"
    assert ns.category_of("조선해양e뉴스") == "portal"


def test_gradient_resolves_via_label_and_legacy_alias():
    # 신 라벨·내부 ID·legacy 표시명이 같은 색으로 수렴
    naver = ns.SOURCE_GRADIENTS["네이버 뉴스"]
    assert ns.source_gradient("naver") == naver
    assert ns.source_gradient("네이버 기술") == naver
    google = ns.SOURCE_GRADIENTS["구글 뉴스"]
    assert ns.source_gradient("google") == google
    assert ns.source_gradient("Google RSS") == google
    assert ns.source_gradient("tech", "AI Times") == ns.SOURCE_GRADIENTS["AI Times"]
    assert ns.source_gradient("모르는 출처") == ns.DEFAULT_GRADIENT


def test_collect_source_rows_splits_tech_sites():
    """saved 의 sites(사이트별 건수)가 있으면 tech 묶음을 AI Times/오토메이션월드로 분해."""
    from ui import data_management_v2 as dm

    saved = [
        {"source": "naver", "keywords": ["용접"], "count": 3, "path": "p"},
        {"source": "tech", "keywords": [], "count": 5, "path": "t",
         "sites": {"AI Times": 3, "오토메이션월드": 2}},
    ]
    errors = [{"source": "tech", "keyword": "오토메이션월드", "error": "403"}]
    rows = dm._collect_source_rows(saved, errors)
    assert rows == [
        {"source": "네이버 뉴스", "count": 3, "ok": True},
        {"source": "AI Times", "count": 3, "ok": True},
        {"source": "오토메이션월드", "count": 2, "ok": False},  # 사이트 단위 부분 오류
    ]


def test_collect_source_rows_legacy_tech_without_sites():
    """sites 없는 legacy 로그 — tech 1행을 '뉴스 포탈' 라벨로."""
    from ui import data_management_v2 as dm

    rows = dm._collect_source_rows(
        [{"source": "tech", "keywords": [], "count": 2, "path": "t"}], [])
    assert rows == [{"source": "뉴스 포탈", "count": 2, "ok": True}]


def test_run_daily_tech_entry_records_sites(monkeypatch):
    """collect_batch 가 tech saved 엔트리에 press 기준 사이트별 건수를 기록한다."""
    from scraping import run_daily

    arts = [
        {"title": "a", "press": "AI Times", "link": "https://a", "source": "tech"},
        {"title": "b", "press": "AI Times", "link": "https://b", "source": "tech"},
        {"title": "c", "press": "오토메이션월드", "link": "https://c", "source": "tech"},
    ]
    monkeypatch.setattr(run_daily.tech_sites, "search_all",
                        lambda max_results_per_site=10, on_error=None: list(arts))
    monkeypatch.setattr(run_daily, "save_articles",
                        lambda articles, source: f"/tmp/{source}.parquet")
    rep = run_daily.collect_batch([], sources=("tech",), do_enrich=False)
    assert rep.saved[0]["sites"] == {"AI Times": 2, "오토메이션월드": 1}


def test_sources_legacy_disabled_names_migrate(isolated_sources):
    """과거 표시명(네이버 기술/Google RSS)으로 저장된 disabled 설정이 현 이름으로 환산·토글된다."""
    import json
    s = isolated_sources
    s._save_raw({"disabled": ["네이버 기술", "Google RSS"]})
    assert s.disabled_set() == frozenset({"네이버 뉴스", "구글 뉴스"})
    # legacy 항목이 있어도 토글이 정상 동작(공존 무력화 방지)
    assert s.toggle_disabled("네이버 뉴스") is True   # 비활성 → 활성
    assert "네이버 뉴스" not in s.disabled_set()
    raw = json.loads(s._config_path().read_text(encoding="utf-8"))
    assert "네이버 기술" not in (raw.get("disabled") or [])
