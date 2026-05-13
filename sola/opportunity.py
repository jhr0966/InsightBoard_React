"""자동화 기회 매트릭스 — 부서×공정(Lv3) 셀별 점수.

룰 기반(score_matches 누적) + 선택적 LLM 한 줄 코멘트.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from sola.client import LLMNotConfigured, chat
from sola.prompts import SYSTEM_OPPORTUNITY
from store import cache
from store.match import score_matches


_EMPTY_COLS = (
    "dept", "lv3", "cell_score", "avg_score",
    "matched_news", "matched_tasks", "sample_tasks", "sample_news",
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

    sample_tasks: list[str] = []
    sample_news: list[str] = []
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

    agg["sample_tasks"] = sample_tasks
    agg["sample_news"] = sample_news
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


def prefill_commentaries(
    cells_df: pd.DataFrame,
    *,
    max_cells: int = 20,
    progress_cb: Callable[[int, int, tuple[str, str, str]], None] | None = None,
) -> dict[tuple[str, str], str]:
    """상위 max_cells 개 셀에 대해 LLM 코멘트를 미리 채워 캐시에 적재.

    Args:
        cells_df: `score_cells()` 결과 (cell_score 내림차순 가정).
        max_cells: cron/UI 1회당 LLM 호출 상한.
        progress_cb: `(done, total, (dept, lv3, comment))` 콜백.

    Returns:
        `{(dept, lv3): comment}` — 빈 코멘트는 제외. LLM 미설정 시 빈 dict.
    """
    if cells_df.empty or max_cells <= 0:
        return {}

    from sola.client import is_configured

    if not is_configured():
        # 미설정 환경에서는 호출 자체가 무의미 (llm_commentary 가 빈 문자열 반환).
        return {}

    head = cells_df.head(max_cells)
    total = len(head)
    out: dict[tuple[str, str], str] = {}
    for i, (_, row) in enumerate(head.iterrows(), start=1):
        dept = str(row["dept"])
        lv3 = str(row["lv3"])
        comment = llm_commentary(
            dept, lv3,
            str(row.get("sample_news", "")),
            str(row.get("sample_tasks", "")),
        )
        if comment:
            out[(dept, lv3)] = comment
        if progress_cb is not None:
            try:
                progress_cb(i, total, (dept, lv3, comment))
            except Exception:  # noqa: BLE001
                pass
    return out
