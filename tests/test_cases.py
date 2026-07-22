"""사례 라이브러리 (Step 12) 회귀 테스트 — 저장소·추출·API·제안서 주입."""
from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from sola import case_extract
from store import cases_db

client = TestClient(app)


def _case(aid="aid1", status="pending_review"):
    return {
        "case_id": cases_db.case_id_for_article(aid),
        "title": "비전 AI 용접 검사 자동화", "industry": "조선",
        "target_work": "용접부 외관검사", "problem": "수작업 검사 병목",
        "solution": "딥러닝 비전으로 결함 자동 판정",
        "technology_ids": ["TECH-CV-001"],
        "implementation": "파일럿",
        "quantified_effects": [{"metric": "검사 시간", "value": "-60%",
                                "evidence_text": "검사 시간을 60% 단축했다"}],
        "shipyard_implications": "도장 검사에도 적용 가능",
        "confidence": 0.9, "review_status": status,
    }


def _sources(aid="aid1"):
    return [{"article_id": aid, "link": f"https://x/{aid}", "title": "기사",
             "evidence_text": "검사 시간을 60% 단축했다", "evidence_type": "source_fact"}]


def test_upsert_idempotent_and_status_preserved():
    cid = cases_db.upsert_case(_case(), _sources())
    cases_db.set_status(cid, "approved")
    # 재추출(같은 case_id)이 검토 상태를 되돌리지 않는다
    cases_db.upsert_case(_case(), _sources())
    got = cases_db.get(cid)
    assert got["review_status"] == "approved"
    assert got["technology_ids"] == ["TECH-CV-001"]
    assert got["sources"][0]["evidence_type"] == "source_fact"


def test_list_filters_and_summary():
    cases_db.upsert_case(_case("a1"), _sources("a1"))
    cases_db.upsert_case(_case("a2"), _sources("a2"))
    cases_db.set_status(cases_db.case_id_for_article("a2"), "approved")
    assert len(cases_db.list_cases(status="approved")) == 1
    assert len(cases_db.list_cases(technology_id="TECH-CV-001")) == 2
    s = cases_db.summary()
    assert s["total"] == 2 and s["by_status"]["approved"] == 1


def test_extract_one_parses_llm_json():
    """LLM JSON 응답 → 저장 형식 변환 (기술 taxonomy ID 수렴 포함)."""
    reply = json.dumps({
        "is_case": True, "title": "AGV 물류 자동화", "industry": "물류",
        "target_work": "자재 운반", "problem": "운반 인력 부족",
        "solution": "AGV 도입", "technologies": ["AGV"],
        "implementation": "전면 도입",
        "quantified_effects": [{"metric": "운반 시간", "value": "-30%",
                                "evidence_text": "운반 시간이 30% 줄었다"}],
        "shipyard_implications": "블록 운반에 적용 가능", "confidence": 0.8,
    }, ensure_ascii=False)
    art = {"article_id": "aidX", "link": "https://x/agv", "title": "AGV 도입 사례",
           "press": "테스트", "content": "본문 " * 100}
    with patch.object(case_extract, "chat", return_value=reply):
        out = case_extract.extract_one(art)
    assert out is not None
    assert "TECH-RB-002" in out["case"]["technology_ids"]      # AGV → 자율이동로봇 ID
    assert out["sources"][0]["evidence_type"] == "source_fact"  # 수치 원문 구절 존재
    # 사례 아님 판정
    with patch.object(case_extract, "chat", return_value='{"is_case": false}'):
        assert case_extract.extract_one(art) is None


def test_extract_batch_llm_unset_graceful(monkeypatch):
    """LLM 미설정 → 배치가 조용히 생략(수집·cron 을 깨지 않음)."""
    from datetime import datetime, timedelta, timezone

    from roadmap import query as roadmap_query
    from sola.client import LLMNotConfigured
    from store import news_db

    news_db.save_articles([{"title": "용접 로봇", "link": "https://x/w1", "source": "naver",
                            "published_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                            "content": "용접 자동화 본문 " * 50}], source="naver")
    monkeypatch.setattr(roadmap_query, "load_latest", lambda: pd.DataFrame([{
        "dept": "조립부", "lv1": "", "lv2": "", "lv3": "소조립", "task": "용접",
        "sub_task": "", "task_def": "용접 로봇"}]))
    with patch.object(case_extract, "chat", side_effect=LLMNotConfigured("no key")):
        res = case_extract.extract_batch(days=7, limit=5)
    assert res["extracted"] == 0 and "LLM" in res.get("reason", "")


def test_cases_api_list_status_extract():
    cases_db.upsert_case(_case("api1"), _sources("api1"))
    cid = cases_db.case_id_for_article("api1")
    assert client.get("/api/cases").status_code == 200
    assert client.get("/api/cases", params={"status": "이상한값"}).status_code == 422
    res = client.post(f"/api/cases/{cid}/status", json={"status": "approved"})
    assert res.status_code == 200 and res.json()["review_status"] == "approved"
    assert client.post("/api/cases/none/status", json={"status": "approved"}).status_code == 404
    assert client.get("/api/cases/summary").json()["total"] >= 1


def test_approved_case_injected_into_proposal(monkeypatch):
    """승인 사례만 제안서에 주입 — 미승인은 제외 (§14-3 핵심)."""
    from datetime import datetime, timedelta, timezone

    from roadmap import query as roadmap_query
    from sola.client import LLMNotConfigured
    from store import news_db

    now = datetime.now(timezone.utc)
    news_db.save_articles([{"title": "비전 AI 도막 검사", "link": "https://x/pv1", "source": "naver",
                            "published_at": (now - timedelta(hours=2)).isoformat(),
                            "keywords": "막두께, 검사", "content": "도장 검사 자동화 " * 30}],
                          source="naver")
    monkeypatch.setattr(roadmap_query, "load_latest", lambda: pd.DataFrame([{
        "dept": "도장부", "lv1": "", "lv2": "", "lv3": "도장검사", "task": "도장 검사",
        "sub_task": "", "task_def": "도막 두께 측정 검사"}]))
    # 근거 기사의 article_id 로 사례 저장
    from store.article_id import article_id
    aid = article_id("https://x/pv1")
    cases_db.upsert_case({**_case(aid), "title": "타사 도막 검사 자동화 사례"},
                         _sources(aid))
    cid = cases_db.case_id_for_article(aid)

    def _gen():
        with patch("sola.propose.chat", side_effect=LLMNotConfigured("t")):
            return client.post("/api/proposals/generate", json={
                "task": {"org_meta": {"dept": "도장부", "lv3": "도장검사",
                                      "task": "도장 검사"}}}).json()

    # 미승인 → 주입 안 됨
    body = _gen()
    assert body["cases"] == [] and "[사례 1]" not in body["proposal"]
    # 승인 → 주입됨(프롬프트 미리보기에 사례 블록)
    cases_db.set_status(cid, "approved")
    body = _gen()
    assert body["cases"] and body["cases"][0]["title"] == "타사 도막 검사 자동화 사례"
    assert "[승인 사례]" in body["proposal"] and "[사례 1]" in body["proposal"]


def test_handoff_case_ids_inject_specified_case(monkeypatch):
    """'이 사례로 제안서' 핸드오프 — case_ids 로 지정한 사례를 주입(승인된 것만)."""
    from roadmap import query as roadmap_query
    from sola.client import LLMNotConfigured
    from store import news_db

    # 근거 기사와 무관한(=자동 매칭 안 되는) 사례를 별도 기사로 저장.
    news_db.save_articles([{"title": "무관 기사", "link": "https://x/unrel", "source": "naver",
                            "keywords": "x", "content": "본문 " * 30}], source="naver")
    from store.article_id import article_id
    other = article_id("https://x/other-case-src")
    cases_db.upsert_case({**_case(other), "title": "핸드오프로 지정한 사례"}, _sources(other))
    cid = cases_db.case_id_for_article(other)
    monkeypatch.setattr(roadmap_query, "load_latest", lambda: pd.DataFrame([{
        "dept": "조립부", "lv1": "", "lv2": "", "lv3": "용접", "task": "용접 검사",
        "sub_task": "", "task_def": "용접부 외관 검사"}]))

    def _gen(case_ids):
        with patch("sola.propose.chat", side_effect=LLMNotConfigured("t")):
            return client.post("/api/proposals/generate", json={
                "task": {"org_meta": {"dept": "조립부", "lv3": "용접", "task": "용접 검사"}},
                "case_ids": case_ids}).json()

    # 미승인 지정 → 무시(§14-3)
    assert _gen([cid])["cases"] == []
    # 승인 후 지정 → 근거 기사와 매칭 안 돼도 주입됨
    cases_db.set_status(cid, "approved")
    titles = [c["title"] for c in _gen([cid])["cases"]]
    assert "핸드오프로 지정한 사례" in titles
