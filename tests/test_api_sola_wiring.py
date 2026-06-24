"""SOLA 미연결 기능 wiring — 제안서 다듬기(refine) + 스레드 자동 제목."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ── 제안서 다듬기 (/api/proposals/refine) ────────────────────────────
def test_refine_delegates_to_sola_refine():
    with patch("sola.refine.refine_proposal", return_value="# 다듬은 제안서\n개선됨") as m:
        r = client.post("/api/proposals/refine",
                        json={"proposal": "# 원본", "instruction": "리스크 강화"})
    assert r.status_code == 200
    assert r.json()["proposal"].startswith("# 다듬은 제안서")
    # current_md + instruction 이 전달됐는지
    args, kwargs = m.call_args
    assert args[0] == "# 원본" and args[1] == "리스크 강화"


def test_refine_requires_nonempty_fields():
    r = client.post("/api/proposals/refine", json={"proposal": "", "instruction": "x"})
    assert r.status_code == 422  # min_length=1


def test_refine_llm_error_returns_502():
    with patch("sola.refine.refine_proposal", side_effect=RuntimeError("Host blocked")):
        r = client.post("/api/proposals/refine",
                        json={"proposal": "# 원본", "instruction": "더 짧게"})
    assert r.status_code == 502


# ── 스레드 자동 제목 (/api/threads) ──────────────────────────────────
def test_create_thread_auto_titles_from_first_message():
    with patch("sola.thread_title.generate", return_value="용접 자동화 검토") as m:
        r = client.post("/api/threads", json={"first_message": "용접 공정 자동화 어떻게 할까?"})
    assert r.status_code == 200
    assert r.json()["title"] == "용접 자동화 검토"
    m.assert_called_once()


# ── 출처별 헬스 (/api/sources/health) ────────────────────────────────
def test_sources_health_reports_status_per_source():
    from store import news_db
    news_db.save_articles([
        {"title": "n1", "source": "naver", "press": "전자신문", "keywords": "",
         "content": "x", "date": "2026-06-15", "collected_at": "2026-06-15T09:00:00Z",
         "link": "https://e.com/1"},
        {"title": "t1", "source": "tech", "press": "AI Times", "keywords": "",
         "content": "x", "date": "2026-06-15", "collected_at": "2026-06-15T09:00:00Z",
         "link": "https://e.com/2"},
    ], source="naver")
    rows = client.get("/api/sources/health", params={"days": 30}).json()
    by = {r["name"]: r for r in rows}
    assert by["네이버 뉴스"]["count_7d"] == 1 and by["네이버 뉴스"]["status"] == "정상"
    assert by["AI Times"]["count_7d"] == 1
    # 수집 없는 출처는 무수집
    assert by["오토메이션월드"]["status"] == "무수집"


def test_create_thread_explicit_title_skips_llm():
    with patch("sola.thread_title.generate") as m:
        r = client.post("/api/threads", json={"title": "내 제목", "first_message": "무시됨"})
    assert r.json()["title"] == "내 제목"
    m.assert_not_called()
