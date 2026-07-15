"""기술 taxonomy (Step 7) — 안정 ID·alias·오버라이드·links 태깅 회귀 테스트."""
from __future__ import annotations

import json

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from store import links_db, taxonomy

client = TestClient(app)


def test_seed_schema_and_stable_ids():
    items = taxonomy.load()
    ids = [t["technology_id"] for t in items]
    assert len(ids) == len(set(ids))                      # ID 고유
    assert all(i.startswith("TECH-") for i in ids)        # 안정 ID 형식
    assert taxonomy.TAXONOMY_VERSION >= 1
    names = {t["name"] for t in items}
    assert {"컴퓨터 비전", "로보틱스", "자율이동로봇", "생성형 AI"} <= names


def test_alias_resolution():
    """동의어가 같은 기술 ID 로 수렴 — 비전 AI·머신비전 → 컴퓨터 비전, AGV·AMR → 자율이동로봇."""
    assert "TECH-CV-001" in taxonomy.tag_text("조선소 비전 AI 용접 검사")
    assert "TECH-CV-001" in taxonomy.tag_text("머신비전 기반 외관검사")
    got = taxonomy.tag_text("AGV와 AMR 이 물류를 바꾼다")
    assert "TECH-RB-002" in got
    assert taxonomy.tag_text("아이돌 콘서트 소식") == []


def test_override_file_and_fallback(tmp_path, monkeypatch):
    """운영 오버라이드 파일 우선, 깨진 파일은 시드 폴백."""
    import config

    d = config.DATA_ROOT / "taxonomy"
    d.mkdir(parents=True, exist_ok=True)
    (d / "taxonomy.json").write_text(json.dumps([
        {"technology_id": "TECH-XX-001", "name": "테스트기술", "aliases": ["엑스"]},
    ], ensure_ascii=False), encoding="utf-8")
    assert [t["technology_id"] for t in taxonomy.load()] == ["TECH-XX-001"]
    assert taxonomy.tag_text("엑스 도입 사례") == ["TECH-XX-001"]
    (d / "taxonomy.json").write_text("{broken", encoding="utf-8")
    assert len(taxonomy.load()) == len(taxonomy._SEED)    # 폴백


def test_heatmap_cols_follow_taxonomy():
    """히트맵 열이 하드코딩이 아니라 taxonomy 를 따른다 (빈 데이터에서도 계약 유지)."""
    res = client.get("/api/insights/heatmap")
    assert res.status_code == 200
    body = res.json()
    assert body["cols"] == [c["name"] for c in taxonomy.heatmap_columns()]
    assert client.get("/api/insights/taxonomy").status_code == 200


def test_links_store_technology_ids():
    """links 저장 행에 기술 ID 가 태깅된다 (문자열이 아닌 ID — 계획 §10)."""
    news = pd.DataFrame([{
        "title": "AGV 물류 자동화", "summary": "자율물류 도입", "keywords": "AGV, 물류",
        "link": "https://x.com/agv", "article_id": "aid1"}])
    roadmap = pd.DataFrame([{
        "dept": "생산관리부", "lv1": "", "lv2": "", "lv3": "물류", "task": "블록 운반",
        "sub_task": "", "task_def": "AGV 자율물류 운반"}])
    links_db.matches_for_window(news, roadmap, days=30)           # 계산+저장
    stored = links_db.matches_for_window(news, roadmap, days=30)  # 저장본
    assert "TECH-RB-002" in stored.iloc[0]["technology_ids"]
    rows = links_db.links_for_article(links_db.article_id("https://x.com/agv"), days=30)
    assert rows and "TECH-RB-002" in rows[0]["technology_ids"]
