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
