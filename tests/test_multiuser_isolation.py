"""멀티유저 격리 (Step 10) — X-User-Id 경량 식별 + 사용자별 데이터 분리.

⚠ X-User-Id 는 인증이 아니다 — 신뢰 프록시 주입 전제(api/deps.py·I-17).
여기서는 두 사용자(A/B)의 persona·bookmarks·threads·feedback(dismiss)이
서로 보이지 않음을 가드한다.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
A = {"X-User-Id": "userA"}
B = {"X-User-Id": "userB"}


def test_persona_isolated_per_user():
    client.put("/api/persona", json={"name": "A", "dept": "도장부"}, headers=A)
    client.put("/api/persona", json={"name": "B", "dept": "조립부"}, headers=B)
    assert client.get("/api/persona", headers=A).json()["dept"] == "도장부"
    assert client.get("/api/persona", headers=B).json()["dept"] == "조립부"
    # 헤더 없음 = 기본 사용자('local') — A/B 어느 쪽도 아님
    assert client.get("/api/persona").json()["dept"] == ""
    # reset 도 본인 것만
    client.post("/api/persona/reset", headers=A)
    assert client.get("/api/persona", headers=A).json()["dept"] == ""
    assert client.get("/api/persona", headers=B).json()["dept"] == "조립부"


def test_legacy_profile_migrates_to_default_user():
    """과거 단일 profile.json → 기본 사용자 프로필로 자동 이관(원본 보존)."""
    import json

    import config

    legacy = config.DATA_ROOT / "persona" / "profile.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"name": "레거시", "dept": "가공부"}, ensure_ascii=False),
                      encoding="utf-8")
    from persona import store as persona_store

    p = persona_store.load()          # 기본 사용자
    assert p.dept == "가공부"
    assert legacy.exists()            # 원본 보존
    assert persona_store.load("userA").dept == ""  # 다른 사용자에겐 이관 안 됨


def test_bookmarks_isolated_per_user():
    client.post("/api/bookmarks", json={"type": "news", "title": "A의 기사"}, headers=A)
    client.post("/api/bookmarks", json={"type": "news", "title": "B의 기사"}, headers=B)
    a_titles = [b["title"] for b in client.get("/api/bookmarks", headers=A).json()]
    b_titles = [b["title"] for b in client.get("/api/bookmarks", headers=B).json()]
    assert "A의 기사" in a_titles and "B의 기사" not in a_titles
    assert "B의 기사" in b_titles and "A의 기사" not in b_titles


def test_threads_isolated_per_user():
    client.post("/api/threads", json={"title": "A 스레드"}, headers=A)
    client.post("/api/threads", json={"title": "B 스레드"}, headers=B)
    a_titles = [t["title"] for t in client.get("/api/threads", headers=A).json()]
    b_titles = [t["title"] for t in client.get("/api/threads", headers=B).json()]
    assert "A 스레드" in a_titles and "B 스레드" not in a_titles
    assert "B 스레드" in b_titles and "A 스레드" not in b_titles


def test_feedback_dismiss_isolated():
    """A 의 '관련 없음'이 B 의 제외 목록에 섞이지 않는다."""
    from store import feedback

    client.post("/api/feedback/events", headers=A, json={"events": [
        {"action_type": "dismiss", "article_id": "art-1", "ranking_version": 1}]})
    assert feedback.dismissed_article_ids(user="userA") == {"art-1"}
    assert feedback.dismissed_article_ids(user="userB") == set()


def test_header_sanitized_against_traversal():
    """이상 문자·경로 조작 헤더는 슬러그로 정제(파일명 안전)."""
    evil = {"X-User-Id": "../../etc/passwd"}
    res = client.put("/api/persona", json={"name": "x", "dept": "y"}, headers=evil)
    assert res.status_code == 200
    import config

    profiles = config.DATA_ROOT / "persona" / "profiles"
    names = {p.name for p in profiles.glob("*.json")}
    assert all(".." not in n and "/" not in n for n in names)
