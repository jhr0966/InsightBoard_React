"""api.routers.news / trends / proposals — store·sola 위임."""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from store import news_db

client = TestClient(app)

# 오늘 날짜로 시드 — trends/volume 의 N일 윈도우 안에 항상 들도록(하드코딩 날짜는 시간이 지나면 윈도우 밖으로 썩는다).
_TODAY = date.today().isoformat()


def _seed():
    news_db.save_articles(
        [
            {"title": "조선소 용접 자동화", "link": "l1", "source": "naver",
             "keywords": "용접, 자동화", "date": _TODAY},
            {"title": "강재 절단 효율화", "link": "l2", "source": "google",
             "keywords": "절단, 자동화", "date": _TODAY},
        ],
        source="naver",
    )


def test_news_list_and_source_filter():
    _seed()
    alln = client.get("/api/news").json()
    assert len(alln) == 2
    # 카드·데이터표가 본문을 보여주도록 content 를 목록에 포함(길이 제한 절단).
    assert "title" in alln[0] and "content" in alln[0]
    naver = client.get("/api/news", params={"source": "naver"}).json()
    assert [r["link"] for r in naver] == ["l1"]


def test_news_list_truncates_content():
    """목록 content 는 _LIST_CONTENT_MAX 로 절단(payload 절감), 상세는 전체."""
    from api.routers.news import _LIST_CONTENT_MAX

    long_body = "가나다라마 " * 2000  # 충분히 길게
    news_db.save_articles(
        [{"title": "긴 본문", "link": "long1", "source": "naver", "date": _TODAY,
          "content": long_body}], source="naver")
    row = next(r for r in client.get("/api/news").json() if r["link"] == "long1")
    assert len(row["content"]) <= _LIST_CONTENT_MAX + 1  # 절단 + … 꼬리
    assert row["content"].endswith("…")
    detail = client.get("/api/news/detail", params={"link": "long1"}).json()
    assert len(detail["content"]) > _LIST_CONTENT_MAX  # 상세는 전체


def test_news_today():
    _seed()
    assert len(client.get("/api/news/today").json()) == 2


def test_news_empty_ok():
    assert client.get("/api/news").json() == []


def test_news_content_rate():
    """본문 확보율 — content ≥ 50자 비율(수집 설정 헬스 카드)."""
    news_db.save_articles([
        {"title": "긴 본문", "link": "cr1", "source": "naver", "date": "2026-06-15",
         "content": "이것은 충분히 긴 본문입니다. " * 5},
        {"title": "빈 본문", "link": "cr2", "source": "naver", "date": "2026-06-15", "content": ""},
    ], source="naver")
    r = client.get("/api/news/content-rate", params={"days": 30}).json()
    assert r["total"] == 2 and r["ready"] == 1 and r["pct"] == 50
    # 뉴스 없으면 0
    assert client.get("/api/news/content-rate").json()["total"] >= 0


def test_news_detail_returns_content():
    news_db.save_articles(
        [{"title": "본문 있는 기사", "link": "ld1", "source": "naver",
          "content": "이것은 기사 본문 전체입니다.", "keywords_llm": "용접, 로봇",
          "date": "2026-06-15"}],
        source="naver",
    )
    r = client.get("/api/news/detail", params={"link": "ld1"})
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "이것은 기사 본문 전체입니다."
    assert body["keywords_llm"] == "용접, 로봇"


def test_news_detail_404_when_missing():
    assert client.get("/api/news/detail", params={"link": "nope"}).status_code == 404


def test_keyword_delta_edge_cases():
    from store import trends
    assert trends.keyword_delta([]) == (0, False)
    assert trends.keyword_delta([0, 0, 0]) == (0, False)
    assert trends.keyword_delta([0, 0, 3]) == (100, True)  # 첫 등장(선행 0 트림)
    pct, is_new = trends.keyword_delta([2, 2, 2, 4, 4, 4])
    assert not is_new and pct == 100  # 2→4 = +100%


def test_keyword_series_endpoint_shape():
    _seed()
    d = client.get("/api/trends/keyword-series").json()
    assert d["mode"] in ("weekly", "daily")
    assert isinstance(d["labels"], list) and isinstance(d["series"], list)
    if d["series"]:
        s = d["series"][0]
        assert {"keyword", "counts", "total", "delta", "is_new"} <= set(s)
        assert len(s["counts"]) == len(d["labels"])


def test_trends_keywords_volume_sources():
    _seed()
    kw = client.get("/api/trends/keywords").json()
    kws = {r["keyword"]: r["count"] for r in kw}
    assert kws.get("자동화") == 2
    vol = client.get("/api/trends/volume", params={"days": 7}).json()
    assert sum(r["count"] for r in vol) == 2
    src = client.get("/api/trends/sources").json()
    assert {r["source"] for r in src} == {"naver", "google"}


def test_proposals_generate_delegates():
    _seed()
    with patch("api.routers.proposals.propose_for_task", return_value="## 제안서\n초안") as m:
        r = client.post("/api/proposals/generate", json={
            "task": {"process_id": "PNL-1", "org_meta": {"team": "T", "dept": "D"}},
        })
    assert r.status_code == 200
    assert r.json()["proposal"].startswith("## 제안서")
    assert r.json()["task_process_id"] == "PNL-1"
    assert m.called


def test_assistant_context_packages_persona_and_digest():
    _seed()
    r = client.get("/api/assistant/context", params={"screen": "insights", "days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["screen"] == "insights"
    assert body["news_count"] == 2
    assert "자동화" in body["context"]
