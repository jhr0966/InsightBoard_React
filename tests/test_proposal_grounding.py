"""제안서 근거 연결 (Step 8) + 수직 흐름 검증.

수직 흐름(개편 계획 §16): 작업 선택 → 저장된 links 에서 관련 기사 → 연결 이유
→ 근거 있는 제안서 생성 → 제안서에서 근거 다시 확인(보관 meta).
LLM 미설정 환경에선 propose 가 '입력 컨텍스트 미리보기'를 반환하므로,
프롬프트에 실제로 근거가 들어갔는지까지 문자열로 검증할 수 있다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from sola.propose import select_evidence

client = TestClient(app)
_NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _iso(**delta) -> str:
    return (_NOW - timedelta(**delta)).isoformat()


def _links() -> pd.DataFrame:
    """저장 links 형태의 매칭 df (rank·이유 포함)."""
    rows = []
    for i in range(6):
        rows.append({"dept": "도장부", "lv3": "도장검사", "task": "도장 검사", "sub_task": "",
                     "news_title": f"막두께 기사{i}", "link": f"https://x.com/p{i}",
                     "article_id": f"aidp{i}", "score": 10.0 - i, "rank": i + 1,
                     "score_components": {"title_match": 5.0}, "matched_terms": ["막두께", "검사"],
                     "matched_fields": ["title"], "matching_version": 2})
    rows.append({"dept": "조립부", "lv3": "소조립", "task": "용접", "sub_task": "",
                 "news_title": "용접 기사", "link": "https://x.com/w", "article_id": "aidw",
                 "score": 8.0, "rank": 1, "score_components": {}, "matched_terms": ["용접"],
                 "matched_fields": ["title"], "matching_version": 2})
    # 임계값 미달 꼬리 (도장 top 10.0 의 25% 미만)
    rows.append({"dept": "도장부", "lv3": "도장검사", "task": "도장 검사", "sub_task": "",
                 "news_title": "잡음 기사", "link": "https://x.com/noise", "article_id": "aidn",
                 "score": 1.0, "rank": 7, "score_components": {}, "matched_terms": ["측정"],
                 "matched_fields": ["summary"], "matching_version": 2})
    return pd.DataFrame(rows)


def _news_meta() -> pd.DataFrame:
    rows = [{"link": f"https://x.com/p{i}", "press": f"언론{i % 3}", "source": "naver",
             "published_at_norm": _iso(days=i), "sort_at": _iso(days=i),
             "summary": f"막두께 요약 {i}", "content": f"막두께 본문 {i} " * 10}
            for i in range(6)]
    return pd.DataFrame(rows)


_TASK = {"org_meta": {"dept": "도장부", "lv3": "도장검사", "task": "도장 검사",
                      "process_id": "P-001"}}


def test_evidence_filtered_to_selected_task():
    """선택 작업과 매칭된 기사만 근거가 된다 — 다른 작업(용접) 기사 배제."""
    ev = select_evidence(_TASK, _links(), _news_meta())
    links = {e["link"] for e in ev}
    assert "https://x.com/w" not in links          # 다른 작업 기사 배제
    assert "https://x.com/noise" not in links      # 임계값(0.25×top) 미달 컷
    assert all("막두께" in e["matched_terms"] for e in ev)
    assert all(e["reason"] for e in ev)            # 결정적 이유 문장 포함


def test_evidence_source_diversity_and_freshness():
    """같은 출처 최대 2건(다양성) + 7일 내 기사 가점."""
    ev = select_evidence(_TASK, _links(), _news_meta(), max_items=6)
    per = {}
    for e in ev:
        per[e["press"]] = per.get(e["press"], 0) + 1
    assert max(per.values()) <= 2


def test_no_matched_links_returns_empty_not_random():
    """links 에 없는 작업 → 근거 없음 (최근 뉴스로 위장 금지 — 일반론 방지)."""
    other = {"org_meta": {"dept": "설계부", "lv3": "생산설계", "task": "도면 작성"}}
    assert select_evidence(other, _links(), _news_meta()) == []


def test_vertical_flow_end_to_end(monkeypatch):
    """수직 흐름: 작업 → links → 이유 → 근거 주입 제안서 → 보관 meta 재확인."""
    from roadmap import query as roadmap_query
    from store import links_db, news_db

    # ① 데이터 준비 — 뉴스 저장 + 작업정의(roadmap) 주입
    news_db.save_articles([
        {"title": "AI 도막 두께 측정 자동화", "link": "https://x.com/flow1", "source": "naver",
         "published_at": _iso(hours=3), "keywords": "막두께, 측정",
         "content": "도장 검사 자동화 본문 " * 10},
        {"title": "아이돌 콘서트", "link": "https://x.com/flow2", "source": "naver",
         "published_at": _iso(hours=1), "keywords": "콘서트"},
    ], source="naver")
    roadmap = pd.DataFrame([{
        "dept": "도장부", "lv1": "", "lv2": "", "lv3": "도장검사", "task": "도장 검사",
        "sub_task": "막두께 측정", "task_def": "건조 도막 두께를 측정하고 외관을 검사"}])
    monkeypatch.setattr(roadmap_query, "load_latest", lambda: roadmap)

    # ② 제안서 생성 API — LLM 미설정 강제(환경에 실키가 있어도 hermetic) →
    #    propose 가 '입력 컨텍스트 미리보기'를 반환해 주입 내용을 검증 가능.
    from sola.client import LLMNotConfigured

    with patch("sola.propose.chat", side_effect=LLMNotConfigured("test")):
        res = client.post("/api/proposals/generate", json={
            "task": {"org_meta": {"dept": "도장부", "lv3": "도장검사",
                                  "task": "도장 검사", "process_id": "P-FLOW"}}})
    assert res.status_code == 200
    body = res.json()
    # 근거: 매칭 기사만 — 무관 기사(콘서트) 배제
    ev_links = [e["link"] for e in body["evidence"]]
    assert "https://x.com/flow1" in ev_links and "https://x.com/flow2" not in ev_links
    assert body["evidence"][0]["reason"]                       # 연결 이유
    assert body["matching_version"] >= 2 and body["prompt_version"] >= 2
    # 프롬프트(미리보기)에 근거 기사·매칭 용어가 실제 주입됨
    assert "[근거 1]" in body["proposal"] and "AI 도막 두께 측정 자동화" in body["proposal"]
    assert "매칭:" in body["proposal"]
    # links 저장소에도 관계가 남아 있다 (기사 → 작업 역조회)
    rows = links_db.links_for_article(links_db.article_id("https://x.com/flow1"), days=30)
    assert rows and rows[0]["task"] == "도장 검사"

    # ③ 보관 — 근거 관계(meta)가 저장되고 다시 읽힌다
    created = client.post("/api/bookmarks", json={
        "type": "proposal", "title": "도장 검사 자동화 제안", "content": body["proposal"],
        "meta": {"task_id": "P-FLOW", "article_ids": [e["article_id"] for e in body["evidence"]],
                 "matching_version": body["matching_version"],
                 "prompt_version": body["prompt_version"]}})
    assert created.status_code == 201
    got = client.get("/api/bookmarks", params={"type": "proposal"}).json()
    saved = next(b for b in got if b["title"] == "도장 검사 자동화 제안")
    assert saved["meta"]["task_id"] == "P-FLOW"
    assert saved["meta"]["article_ids"]                        # 근거 복원 가능


def test_bookmark_meta_backward_compatible():
    """meta 없는 과거 북마크도 안전 (빈 dict)."""
    res = client.post("/api/bookmarks", json={"type": "proposal", "title": "구형", "content": "x"})
    assert res.status_code == 201 and res.json()["meta"] == {}
