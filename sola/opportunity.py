"""자동화 기회 매트릭스 — 부서×공정(Lv3) 셀별 점수.

룰 기반(score_matches 누적) + 선택적 LLM 한 줄 코멘트.
"""
from __future__ import annotations

import pandas as pd

from sola.client import LLMNotConfigured, chat
from sola.prompts import SYSTEM_OPPORTUNITY
from store import cache
from store.match import score_matches


_EMPTY_COLS = (
    "dept", "lv3", "cell_score", "avg_score",
    "matched_news", "matched_tasks", "sample_tasks", "sample_news",
    "sample_objectives",
)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=list(_EMPTY_COLS))


def score_cells(
    news_df: pd.DataFrame,
    roadmap_df: pd.DataFrame,
    *,
    cell_level: str = "lv3",
    top_k_per_task: int = 5,
) -> pd.DataFrame:
    """반환 컬럼:
      dept, lv3, cell_score, avg_score, matched_news, matched_tasks,
      sample_tasks, sample_news
    cell_score 내림차순.
    """
    if news_df.empty or roadmap_df.empty:
        return _empty()
    if cell_level not in roadmap_df.columns:
        return _empty()

    matches = score_matches(news_df, roadmap_df, top_k=top_k_per_task)
    if matches.empty:
        return _empty()

    agg = (
        matches.groupby(["dept", cell_level], dropna=False)
        .agg(
            cell_score=("score", "sum"),
            avg_score=("score", "mean"),
            matched_news=("link", "nunique"),
            matched_tasks=("task", "nunique"),
        )
        .reset_index()
    )

    # roadmap_df 에 task_def_json (신엑셀 정의서) 이 있으면 셀별로 첫 task 의
    # objective 한 줄을 함께 노출 → 보드 ④ 자동화 기회 카드의 tagline 강화.
    has_tdj = "task_def_json" in roadmap_df.columns
    if has_tdj:
        from roadmap.task_def_json import first_objective

    sample_tasks: list[str] = []
    sample_news: list[str] = []
    sample_objectives: list[str] = []
    for _, row in agg.iterrows():
        cell_matches = matches[
            (matches["dept"] == row["dept"]) & (matches[cell_level] == row[cell_level])
        ]
        tasks = list(dict.fromkeys(cell_matches["task"].astype(str).tolist()))[:3]
        news = (
            cell_matches.sort_values("score", ascending=False)
            .drop_duplicates("link")["news_title"].astype(str).tolist()[:3]
        )
        sample_tasks.append(" · ".join(tasks))
        sample_news.append(" · ".join(news))

        # objective — 첫 매칭 task 의 task_def_json 에서
        obj = ""
        if has_tdj and tasks:
            rm = roadmap_df[
                (roadmap_df["dept"] == row["dept"])
                & (roadmap_df[cell_level] == row[cell_level])
                & (roadmap_df.get("task", "") == tasks[0])
            ]
            if not rm.empty:
                obj = first_objective(rm.iloc[0].get("task_def_json", ""))
        sample_objectives.append(obj)

    agg["sample_tasks"] = sample_tasks
    agg["sample_news"] = sample_news
    agg["sample_objectives"] = sample_objectives
    return agg.sort_values("cell_score", ascending=False, ignore_index=True)


def llm_commentary(dept: str, lv3: str, sample_news: str, sample_tasks: str) -> str:
    """상위 셀 1개에 대한 한 줄 코멘트. 캐시.

    LLM 미설정 시 빈 문자열 반환.
    """
    key = cache.make_key("opportunity", dept, lv3, sample_news, sample_tasks)
    hit = cache.get(key)
    if hit is not None:
        return hit

    user = (
        f"[부서] {dept}\n"
        f"[공정(Lv3)] {lv3}\n"
        f"[관련 작업] {sample_tasks or '(없음)'}\n"
        f"[관련 뉴스] {sample_news or '(없음)'}"
    )
    try:
        reply = chat(
            messages=[
                {"role": "system", "content": SYSTEM_OPPORTUNITY},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=160,
        )
    except LLMNotConfigured:
        return ""
    except Exception:  # noqa: BLE001
        return ""

    cache.put(key, reply)
    return reply
