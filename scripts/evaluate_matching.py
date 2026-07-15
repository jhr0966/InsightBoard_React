"""매칭 품질 평가 — 정답셋 기반 리포트 (개편 로드맵 Step 4).

`store.match.score_matches` 의 품질을 정답셋(`data/evaluation/matching_gold.json`)
으로 측정한다. **가중치·알고리즘을 바꾸기 전에 이 기준선을 먼저 기록**하고,
변경 후 다시 돌려 개선/악화를 수치로 확인한다 (pytest 와 분리된 품질 평가 —
pytest 는 실행·스키마·결정성만 가드한다: tests/test_matching_eval.py).

Usage:
  python scripts/evaluate_matching.py                 # 사람이 읽는 리포트
  python scripts/evaluate_matching.py --json          # JSON 출력
  python scripts/evaluate_matching.py --save PATH     # JSON 을 파일로 저장

지표:
  precision_at_3 / precision_at_5   상위 K 중 관련(strong+weak) 비율 (라벨 있는 작업 평균)
  strict_precision_at_3             상위 3 중 strong 비율
  irrelevant_in_top3                상위 3 에 무관 기사가 낀 비율
  tasks_no_result                   결과가 아예 없는 작업 비율
  article_hit_bias                  특정 기사가 여러 작업 top3 에 반복 등장(상위 5)
  source_bias                       top3 등장 기사의 출처 분포
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 레포 루트

import pandas as pd

from store.match import DEFAULT_SEMANTIC_WEIGHT, score_matches

GOLD_PATH = Path(__file__).resolve().parents[1] / "data" / "evaluation" / "matching_gold.json"


def load_gold(path: Path = GOLD_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_key(row: dict) -> str:
    return f"{row.get('dept', '')}||{row.get('lv3', '')}||{row.get('task', '')}"


def evaluate(gold: dict, *, top_k: int = 5,
             semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT) -> dict:
    """정답셋 → 지표 dict (순수 함수·결정적)."""
    news_df = pd.DataFrame(gold["articles"])
    roadmap_df = pd.DataFrame(gold["tasks"])
    rel: dict[tuple[str, str], str] = {
        (lb["task_key"], lb["article"]): lb["relevance"] for lb in gold["labels"]
    }
    labeled_tasks = {lb["task_key"] for lb in gold["labels"]}

    matches = score_matches(news_df, roadmap_df, top_k=top_k,
                            semantic_weight=semantic_weight)
    by_task: dict[str, list[str]] = {}
    if not matches.empty:
        for _, m in matches.iterrows():
            tk = f"{m['dept']}||{m['lv3']}||{m['task']}"
            by_task.setdefault(tk, []).append(str(m["link"]))

    p3s, p5s, strict3s, irrel3 = [], [], [], 0
    no_result = 0
    hit_counter: Counter = Counter()
    src_counter: Counter = Counter()
    art_source = {a["link"]: a.get("source", "") for a in gold["articles"]}

    for tk in sorted(labeled_tasks):
        links = by_task.get(tk, [])
        if not links:
            no_result += 1
            p3s.append(0.0); p5s.append(0.0); strict3s.append(0.0)
            continue
        top3, top5 = links[:3], links[:5]
        rel3 = [rel.get((tk, ln), "none") for ln in top3]
        rel5 = [rel.get((tk, ln), "none") for ln in top5]
        p3s.append(sum(r != "none" for r in rel3) / len(top3))
        p5s.append(sum(r != "none" for r in rel5) / len(top5))
        strict3s.append(sum(r == "strong" for r in rel3) / len(top3))
        if any(r == "none" for r in rel3):
            irrel3 += 1
        for ln in top3:
            hit_counter[ln] += 1
            src_counter[art_source.get(ln, "?")] += 1

    n = len(labeled_tasks) or 1
    return {
        "gold_version": gold.get("version"),
        "semantic_weight": semantic_weight,
        "top_k": top_k,
        "labeled_tasks": len(labeled_tasks),
        "precision_at_3": round(sum(p3s) / n, 3),
        "precision_at_5": round(sum(p5s) / n, 3),
        "strict_precision_at_3": round(sum(strict3s) / n, 3),
        "irrelevant_in_top3_rate": round(irrel3 / n, 3),
        "tasks_no_result_rate": round(no_result / n, 3),
        "article_hit_bias_top5": hit_counter.most_common(5),
        "source_bias": dict(src_counter),
    }


def render(report: dict) -> str:
    lines = [
        "# 매칭 품질 리포트 (score_matches)",
        f"- 정답셋 v{report['gold_version']} · 라벨 작업 {report['labeled_tasks']}개"
        f" · semantic_weight={report['semantic_weight']} · top_k={report['top_k']}",
        f"- Precision@3: {report['precision_at_3']:.1%}   Precision@5: {report['precision_at_5']:.1%}",
        f"- Strict(강한 관련만)@3: {report['strict_precision_at_3']:.1%}",
        f"- 상위3에 무관 기사 낀 작업 비율: {report['irrelevant_in_top3_rate']:.1%}",
        f"- 결과 없는 작업 비율: {report['tasks_no_result_rate']:.1%}",
        "- 기사 반복 등장(편중) top5: "
        + ", ".join(f"{l.rsplit('/', 1)[-1]}×{c}" for l, c in report["article_hit_bias_top5"]),
        f"- 출처 분포(top3 등장): {report['source_bias']}",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    ap.add_argument("--save", metavar="PATH", help="JSON 리포트를 파일로 저장")
    ap.add_argument("--semantic-weight", type=float, default=DEFAULT_SEMANTIC_WEIGHT)
    args = ap.parse_args()

    report = evaluate(load_gold(), semantic_weight=args.semantic_weight)
    if args.save:
        Path(args.save).write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
