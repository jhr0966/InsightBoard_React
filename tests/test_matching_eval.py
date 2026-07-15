"""매칭 품질 평가 하네스 (Step 4) — 실행·스키마·결정성 가드.

품질 수치 자체는 pytest 가 판정하지 않는다(그건 scripts/evaluate_matching.py
리포트의 몫). 여기서는 정답셋 스키마가 깨지지 않고, 평가가 결정적이며,
지표 계산이 토이 입력에서 정확한지만 가드한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

eval_mod = pytest.importorskip("scripts.evaluate_matching")

GOLD = Path(__file__).resolve().parents[1] / "data" / "evaluation" / "matching_gold.json"


def test_gold_schema_valid():
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    assert gold["version"] >= 1
    assert len(gold["tasks"]) >= 20 and len(gold["articles"]) >= 30
    task_keys = {f"{t['dept']}||{t['lv3']}||{t['task']}" for t in gold["tasks"]}
    links = {a["link"] for a in gold["articles"]}
    for lb in gold["labels"]:
        assert lb["relevance"] in ("strong", "weak")
        assert lb["task_key"] in task_keys, f"라벨의 task_key 불일치: {lb['task_key']}"
        assert lb["article"] in links, f"라벨의 article 불일치: {lb['article']}"
    # 무관(라벨 없는) 기사도 포함되어야 한다 — 무관 기사 혼입률 측정용.
    labeled_articles = {lb["article"] for lb in gold["labels"]}
    assert len(links - labeled_articles) >= 5


def test_evaluate_deterministic_and_schema():
    gold = eval_mod.load_gold()
    r1 = eval_mod.evaluate(gold)
    r2 = eval_mod.evaluate(gold)
    assert r1 == r2  # 결정성·멱등성
    for k in ("precision_at_3", "precision_at_5", "strict_precision_at_3",
              "irrelevant_in_top3_rate", "tasks_no_result_rate"):
        assert 0.0 <= r1[k] <= 1.0


def test_evaluate_metrics_on_toy_gold():
    """정답을 아는 토이 정답셋에서 지표가 정확히 계산된다."""
    toy = {
        "version": 1,
        "tasks": [{"dept": "D", "lv1": "", "lv2": "", "lv3": "L", "task": "용접 작업",
                   "sub_task": "FCAW", "task_def": "용접 로봇 자동화", "sws_no": "", "sws_name": "용접"}],
        "articles": [
            {"link": "s1", "title": "용접 로봇 자동화 FCAW", "summary": "용접 로봇", "keywords": "용접, 로봇", "source": "naver"},
            {"link": "n1", "title": "아이돌 콘서트", "summary": "콘서트", "keywords": "아이돌", "source": "naver"},
        ],
        "labels": [{"article": "s1", "task_key": "D||L||용접 작업", "relevance": "strong"}],
    }
    r = eval_mod.evaluate(toy, semantic_weight=0.0)
    # 매칭되는 기사는 s1 뿐 → top3=[s1]. P@K 분모는 항상 K(부풀림 금지) → 1/3.
    # 상한 대비 recall 은 1/1 = 100%.
    assert r["recall_at_3"] == 1.0
    assert r["precision_at_3"] == round(1 / 3, 3)
    assert r["strict_precision_at_3"] == round(1 / 3, 3)
    assert r["irrelevant_in_top3_rate"] == 0.0
    assert r["tasks_no_result_rate"] == 0.0


def test_baseline_report_recorded():
    """기준선 리포트가 커밋되어 있어야 한다 — 가중치 변경 PR 의 비교 기준."""
    base = GOLD.parent / "baseline_matching_v1.json"
    assert base.exists()
    rep = json.loads(base.read_text(encoding="utf-8"))
    assert "precision_at_3" in rep and rep["labeled_tasks"] >= 20
