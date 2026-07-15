"""api.routers.insights — 공정×기술 히트맵."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_heatmap_shape_empty():
    body = client.get("/api/insights/heatmap").json()
    # Step 7: 열은 하드코딩 7종이 아니라 taxonomy(안정 ID·alias)를 따른다.
    from store import taxonomy
    assert body["cols"] == [c["name"] for c in taxonomy.heatmap_columns()]
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


def test_process_map_returns_processes_for_keyword():
    """트렌드 키워드 → 그 키워드를 언급한 뉴스로 score_cells → 상위 공정 카드."""
    from store import news_db

    _seed_and_pick_weld_process()
    news_db.save_articles([
        {"title": "용접 협동 로봇 라인 확대", "link": "p1", "source": "naver",
         "keywords": "용접, 협동 로봇", "content": "조선 용접 협동로봇 비전 검사", "date": "2026-06-15"},
        {"title": "회계 무관 기사", "link": "p2", "source": "naver",
         "keywords": "회계", "content": "회계 결산", "date": "2026-06-15"},
    ], source="naver")

    rows = client.get("/api/insights/process-map", params={"keyword": "용접", "days": 30}).json()
    assert isinstance(rows, list) and len(rows) >= 1
    r0 = rows[0]
    assert "용접" in r0["lv3"] or r0["matched_news"] >= 1
    assert 0 <= r0["fit"] <= 1
    assert r0["tag"] in ("PoC 후보", "관찰 대상")
    # 매칭 안 되는 키워드 → 빈 목록
    assert client.get("/api/insights/process-map", params={"keyword": "존재안함zzz"}).json() == []


def test_heatmap_lights_up_with_matched_news():
    """다단어 공정명이어도 토큰 매칭으로 셀이 켜진다(과거엔 substring 미스로 전부 0).

    특정 공정이 top-N 행에 든다는 보장은 없으므로(87개 정의·의미매칭상 동점 다수,
    순서 의존 flaky 원인), '히트맵에 ≥1 인 셀이 하나라도 있다'로 회귀를 가드한다 —
    과거 버그(공정명 substring 미스)면 모든 셀이 0 이었다."""
    from store import news_db

    _lv3, task = _seed_and_pick_weld_process()
    news_db.save_articles([
        {"title": f"{task}에 협동 로봇·비전 검사 확대", "link": "w1", "source": "naver",
         "keywords": f"{task}, 협동 로봇, 비전", "content": f"{task} 협동 로봇 비전", "date": "2026-06-15"},
    ], source="naver")
    body = client.get("/api/insights/heatmap", params={"rows": 20}).json()
    assert any(v >= 1 for row in body["data"] for v in row)  # 최소 한 셀은 점등(전부 0 이면 회귀)
