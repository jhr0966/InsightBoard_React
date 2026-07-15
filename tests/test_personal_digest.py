"""개인화 다이제스트 + 피드백 이벤트 (Step 9) 회귀 테스트."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from persona.schema import Persona
from store import feedback, rank

client = TestClient(app)
_NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _iso(**delta) -> str:
    return (_NOW - timedelta(**delta)).isoformat()


def _news() -> pd.DataFrame:
    return pd.DataFrame([
        {"article_id": "a1", "link": "https://x/1", "title": "용접 로봇 자동화 확산",
         "keywords": "용접, 로봇", "summary": "", "sort_at": _iso(hours=2), "content": "본문1"},
        {"article_id": "a2", "link": "https://x/2", "title": "도장 막두께 AI 측정",
         "keywords": "막두께", "summary": "", "sort_at": _iso(hours=1), "content": "본문2"},
        {"article_id": "a3", "link": "https://x/3", "title": "반도체 수출 증가",
         "keywords": "반도체", "summary": "", "sort_at": _iso(minutes=10), "content": "본문3"},
    ])


def _links() -> pd.DataFrame:
    return pd.DataFrame([
        {"article_id": "a1", "link": "https://x/1", "dept": "조립부", "lv3": "소조립",
         "task": "용접", "sub_task": "", "score": 9.0, "matched_terms": ["용접", "로봇"]},
        {"article_id": "a2", "link": "https://x/2", "dept": "도장부", "lv3": "도장검사",
         "task": "도장 검사", "sub_task": "", "score": 8.0, "matched_terms": ["막두께"]},
    ])


def _persona() -> Persona:
    return Persona(dept="도장부", interest_lv3=["도장검사"], interest_keywords=["막두께"])


def test_rank_prefers_persona_process_and_keyword():
    """관심 공정·키워드 기사가 최신 무관 기사(반도체)보다 위."""
    items = rank.rank_articles(_news(), _persona(), _links(), limit=3)
    assert items[0]["article_id"] == "a2"                     # 관심 공정+키워드
    ids = [i["article_id"] for i in items]
    assert ids.index("a1") < ids.index("a3") if "a3" in ids else True
    assert items[0]["ranking_version"] == rank.RANKING_VERSION


def test_why_sentence_composed_from_stored_reasons():
    """'왜 관련' 문장 — 저장된 매칭 용어+관심 신호의 규칙 조합(LLM 미사용)."""
    items = rank.rank_articles(_news(), _persona(), _links(), limit=3)
    why = items[0]["why"]
    assert "도장 검사" in why and "막두께" in why
    assert "관심" in why                                       # 관심 공정/키워드 표기


def test_dismissed_articles_excluded():
    items = rank.rank_articles(_news(), _persona(), _links(), limit=3,
                               exclude_article_ids={"a2"})
    assert all(i["article_id"] != "a2" for i in items)


def test_rank_deterministic():
    a = rank.rank_articles(_news(), _persona(), _links(), limit=3, now=_NOW)
    b = rank.rank_articles(_news(), _persona(), _links(), limit=3, now=_NOW)
    assert [i["article_id"] for i in a] == [i["article_id"] for i in b]
    assert [i["score"] for i in a] == [i["score"] for i in b]


def test_feedback_record_and_dismiss_lookup():
    n = feedback.record_events([
        {"action_type": "impression", "article_id": "a1", "ranking_version": 1},
        {"action_type": "dismiss", "article_id": "a1", "ranking_version": 1},
    ])
    assert n == 2
    assert feedback.dismissed_article_ids() == {"a1"}
    s = feedback.summary()
    assert s["by_action"]["dismiss"] == 1 and s["total"] == 2
    # 식별 필드 스탬프(I-7) — 멀티유저 전환 대비
    rows = feedback._repo().read_all()
    assert rows[0]["user_id"] and rows[0]["created_at"]


def test_feedback_api_validates_action():
    ok = client.post("/api/feedback/events", json={"events": [
        {"action_type": "open", "article_id": "a9", "ranking_version": 1}]})
    assert ok.status_code == 200 and ok.json()["saved"] == 1
    bad = client.post("/api/feedback/events", json={"events": [
        {"action_type": "hack", "article_id": "a9"}]})
    assert bad.status_code == 422


def test_digest_api_with_dismiss_flow(monkeypatch):
    """다이제스트 API — 랭킹 반환 + dismiss 후 재조회 시 제외 (개인화 루프)."""
    from roadmap import query as roadmap_query
    from store import news_db

    news_db.save_articles([
        {"title": "도장 막두께 AI 측정", "link": "https://x/d1", "source": "naver",
         "published_at": _iso(hours=1), "keywords": "막두께"},
        {"title": "용접 로봇 확산", "link": "https://x/d2", "source": "naver",
         "published_at": _iso(hours=2), "keywords": "용접"},
    ], source="naver")
    roadmap = pd.DataFrame([{"dept": "도장부", "lv1": "", "lv2": "", "lv3": "도장검사",
                             "task": "도장 검사", "sub_task": "", "task_def": "막두께 측정"}])
    monkeypatch.setattr(roadmap_query, "load_latest", lambda: roadmap)
    from persona import store as persona_store
    persona_store.save(_persona())

    first = client.get("/api/board/digest").json()
    assert first["ranking_version"] == rank.RANKING_VERSION and first["persona_set"]
    ids = [i["article_id"] for i in first["items"]]
    assert ids and first["items"][0]["why"]
    # 관련 없음 → 다음 다이제스트에서 제외
    client.post("/api/feedback/events", json={"events": [
        {"action_type": "dismiss", "article_id": ids[0], "ranking_version": 1}]})
    second = client.get("/api/board/digest").json()
    assert ids[0] not in [i["article_id"] for i in second["items"]]
