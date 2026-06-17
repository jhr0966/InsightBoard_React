"""api.routers.insights — 공정×기술 히트맵."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_heatmap_shape_empty():
    body = client.get("/api/insights/heatmap").json()
    assert body["cols"] == ["비전", "협동 로봇", "예지보전", "디지털 트윈", "AGV", "AI", "외골격"]
    assert body["rows"] == []  # 로드맵/뉴스 없음
    assert body["data"] == []


def test_heatmap_cell_matches_news():
    from store import news_db
    news_db.save_articles([
        {"title": "패널 용접에 AI 비전 적용", "link": "h1", "source": "naver",
         "keywords": "용접, AI", "content": "패널 라인에 AI 비전 검사", "date": "2026-06-15"},
        {"title": "무관 기사", "link": "h2", "source": "naver", "keywords": "기타", "date": "2026-06-15"},
    ], source="naver")
    hit = client.get("/api/insights/heatmap-cell", params={"row": "패널", "col": "AI"}).json()
    assert [a["link"] for a in hit] == ["h1"]
    assert client.get("/api/insights/heatmap-cell", params={"row": "없는공정", "col": "AI"}).json() == []
