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


def _seed_and_pick_weld_process():
    """시드(작업정의) 적재 후 '용접' 포함 공정(lv3·task) 하나 반환."""
    from roadmap.seed import seed_if_empty
    from roadmap import query as rq

    seed_if_empty()
    rm = rq.load_latest()
    weld = rm[rm["lv3"].astype(str).str.contains("용접")].iloc[0]
    return str(weld["lv3"]), str(weld["task"])


def test_heatmap_cell_matches_news():
    """드릴다운은 공정→뉴스 매칭(score_matches) 기반 — 공정에 매칭된 뉴스 중
    해당 기술을 언급한 기사만 돌려준다(옛 공정명 substring 방식 아님)."""
    from store import news_db

    lv3, task = _seed_and_pick_weld_process()
    news_db.save_articles([
        {"title": f"{task} 공정에 협동 로봇 적용", "link": "h1", "source": "naver",
         "keywords": f"{task}, 협동 로봇", "content": f"{task} 라인에 협동 로봇 도입", "date": "2026-06-15"},
        {"title": "무관 기사", "link": "h2", "source": "naver", "keywords": "기타", "date": "2026-06-15"},
    ], source="naver")

    hit = client.get("/api/insights/heatmap-cell", params={"row": lv3, "col": "협동 로봇"}).json()
    links = [a["link"] for a in hit]
    assert "h1" in links          # 용접 공정에 매칭 + '협동 로봇' 언급
    assert "h2" not in links      # 무관 기사 — 매칭/언급 모두 안 됨
    # 존재하지 않는 공정 → 빈 결과
    assert client.get("/api/insights/heatmap-cell", params={"row": "없는공정zzz", "col": "AI"}).json() == []


def test_heatmap_lights_up_with_matched_news():
    """다단어 공정명이어도 토큰 매칭으로 셀이 켜진다(과거엔 substring 미스로 0)."""
    from store import news_db

    lv3, task = _seed_and_pick_weld_process()
    news_db.save_articles([
        {"title": f"{task}에 협동 로봇·비전 검사 확대", "link": "w1", "source": "naver",
         "keywords": f"{task}, 협동 로봇, 비전", "content": f"{task} 협동 로봇 비전", "date": "2026-06-15"},
    ], source="naver")
    body = client.get("/api/insights/heatmap", params={"rows": 10}).json()
    assert lv3 in body["rows"]
    r = body["rows"].index(lv3)
    cobot = body["cols"].index("협동 로봇")
    assert body["data"][r][cobot] >= 1
