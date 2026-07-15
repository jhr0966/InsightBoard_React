"""article_task_links 관계 저장소 (Step 6) 회귀 테스트.

계약: 저장본 소비 결과 = 라이브 계산 결과(동일 순서·점수), stale(새 기사·버전
변경) 시 자동 재빌드, 저장 실패에도 조회는 성공(write-through).
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from store import links_db, match

client = TestClient(app)


def _news(n: int = 4) -> pd.DataFrame:
    rows = [{"title": f"용접 로봇 자동화 {i}", "summary": "용접 자동화 사례",
             "keywords": "용접, 로봇", "link": f"https://x.com/{i}",
             "article_id": f"aid{i}"} for i in range(n)]
    rows.append({"title": "도장 막두께 측정 AI", "summary": "", "keywords": "막두께",
                 "link": "https://x.com/paint", "article_id": "aidp"})
    return pd.DataFrame(rows)


def _roadmap() -> pd.DataFrame:
    return pd.DataFrame([
        {"dept": "조립부", "lv1": "", "lv2": "", "lv3": "소조립", "task": "용접",
         "sub_task": "FCAW", "task_def": "용접 로봇"},
        {"dept": "도장부", "lv1": "", "lv2": "", "lv3": "도장검사", "task": "막두께 측정",
         "sub_task": "", "task_def": "도막 두께 측정"},
    ])


def test_stored_equals_live():
    """저장본 소비 결과가 라이브 score_matches(top_k 슬라이스)와 동일하다."""
    news, roadmap = _news(), _roadmap()
    live = match.score_matches(news, roadmap, top_k=5,
                               semantic_weight=match.DEFAULT_SEMANTIC_WEIGHT)
    got = links_db.slice_top_k(
        links_db.matches_for_window(news, roadmap, days=30), 5)  # 1회차: 계산+저장
    again = links_db.slice_top_k(
        links_db.matches_for_window(news, roadmap, days=30), 5)  # 2회차: 저장본
    for df in (got, again):
        assert list(df["link"]) == list(live["link"])
        assert [round(s, 4) for s in df["score"]] == [round(s, 4) for s in live["score"]]
    # 이유 데이터도 저장·복원된다
    assert again.iloc[0]["matched_terms"]
    assert isinstance(again.iloc[0]["score_components"], dict)


def test_second_call_skips_recompute():
    """같은 윈도우 재조회는 score_matches 를 다시 부르지 않는다 (재계산 제거)."""
    news, roadmap = _news(), _roadmap()
    links_db.matches_for_window(news, roadmap, days=30)
    with patch.object(links_db, "score_matches", side_effect=AssertionError("재계산 금지")):
        df = links_db.matches_for_window(news, roadmap, days=30)
    assert not df.empty


def test_new_article_invalidates_index():
    """윈도우에 새 기사가 들어오면 시그니처 불일치 → 재계산."""
    news, roadmap = _news(), _roadmap()
    links_db.matches_for_window(news, roadmap, days=30)
    news2 = pd.concat([news, pd.DataFrame([{
        "title": "신규 용접 기사", "summary": "", "keywords": "용접",
        "link": "https://x.com/new", "article_id": "aidnew"}])], ignore_index=True)
    df = links_db.matches_for_window(news2, roadmap, days=30)
    assert "https://x.com/new" in set(df["link"])


def test_matching_version_change_invalidates(monkeypatch):
    """MATCHING_VERSION 변경(알고리즘 교체) → stale → 재빌드 + 상태 노출."""
    news, roadmap = _news(), _roadmap()
    links_db.matches_for_window(news, roadmap, days=30)
    monkeypatch.setattr(links_db, "MATCHING_VERSION", 999)
    called = {"n": 0}
    real = match.score_matches

    def counting(*a, **k):
        called["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(links_db, "score_matches", counting)
    links_db.matches_for_window(news, roadmap, days=30)
    assert called["n"] == 1  # 버전 변경으로 재계산
    status = links_db.index_status()
    assert status and {s["window_days"] for s in status} >= {30}


def test_links_for_article_reverse_lookup():
    """기사 → 연결 작업 역조회 (개인화 '왜 관련' 원자료)."""
    news, roadmap = _news(), _roadmap()
    links_db.matches_for_window(news, roadmap, days=30)
    aid = links_db.article_id("https://x.com/paint")
    rows = links_db.links_for_article(aid, days=30)
    assert rows and rows[0]["task"] == "막두께 측정"
    assert rows[0]["matched_terms"]


def test_rebuild_and_status_api():
    """관리자 재빌드·상태 API — 데이터 없으면 built=False 로 안전."""
    res = client.post("/api/matches/rebuild-links")
    assert res.status_code == 200
    body = res.json()
    assert body["built"] is False  # 격리 환경: 뉴스·로드맵 없음
    assert client.get("/api/matches/links-status").status_code == 200


def test_cells_parity_stored_vs_live():
    """기회 매트릭스 집계가 저장본/라이브 어느 경로로도 동일하다."""
    from sola.opportunity import score_cells

    news, roadmap = _news(), _roadmap()
    live_cells = score_cells(news, roadmap)
    stored = links_db.matches_for_window(news, roadmap, days=30)
    stored_cells = score_cells(news, roadmap, matches=stored)
    assert list(live_cells["cell_score"]) == pytest.approx(list(stored_cells["cell_score"]))
    assert list(live_cells["dept"]) == list(stored_cells["dept"])
