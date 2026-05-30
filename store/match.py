"""M1 룰 기반 뉴스↔작업 매칭. M2에서 SOLA(LLM) 로 대체된다.

뉴스 키워드와 작업(task/sub_task/task_def/sws_name) 의 토큰 중첩 점수.
"""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd


_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_NOISE = {"작업", "공정", "기술", "관련", "통해", "대한", "위한", "그리고", "또는"}


def _tokens(text: str) -> list[str]:
    return [w for w in _TOKEN_RE.findall((text or "").lower()) if w not in _NOISE]


def _row_text(row: pd.Series, cols: list[str]) -> str:
    return " ".join(str(row.get(c, "")) for c in cols)


def score_matches(
    news_df: pd.DataFrame,
    roadmap_df: pd.DataFrame,
    *,
    top_k: int = 5,
) -> pd.DataFrame:
    """각 작업(row)별로 가장 잘 맞는 뉴스 top_k와 점수를 반환.

    반환 컬럼: dept, lv1, lv2, lv3, task, sub_task, news_title, link, score
    """
    if news_df.empty or roadmap_df.empty:
        return pd.DataFrame(columns=[
            "dept", "lv1", "lv2", "lv3", "task", "sub_task",
            "news_title", "link", "score",
        ])

    news_cols = [c for c in ("title", "summary", "keywords") if c in news_df.columns]
    task_cols = [c for c in ("task", "sub_task", "task_def", "sws_name", "lv3") if c in roadmap_df.columns]
    has_task_def_json = "task_def_json" in roadmap_df.columns

    news_tokens = [Counter(_tokens(_row_text(row, news_cols))) for _, row in news_df.iterrows()]

    # task_def_json (신엑셀) 의 평탄 텍스트도 매칭에 합산 — 자동화 영역·품질
    # 리스크·objectives 같은 풍부한 신호가 추가되어 정확도↑. JSON 파싱 비용은
    # row 당 ~0.5ms 수준 (한 번만).
    from roadmap.task_def_json import flatten_for_match

    rows: list[dict] = []
    for _, task_row in roadmap_df.iterrows():
        task_text = _row_text(task_row, task_cols)
        if has_task_def_json:
            extra = flatten_for_match(task_row.get("task_def_json", ""))
            if extra:
                task_text = task_text + " " + extra
        tk_counter = Counter(_tokens(task_text))
        if not tk_counter:
            continue
        scored: list[tuple[float, int]] = []
        for idx, nc in enumerate(news_tokens):
            common = set(tk_counter) & set(nc)
            if not common:
                continue
            score = float(sum(min(tk_counter[w], nc[w]) for w in common))
            if score > 0:
                scored.append((score, idx))
        if not scored:
            continue
        scored.sort(reverse=True)
        for score, idx in scored[:top_k]:
            news_row = news_df.iloc[idx]
            rows.append({
                "dept": task_row.get("dept", ""),
                "lv1": task_row.get("lv1", ""),
                "lv2": task_row.get("lv2", ""),
                "lv3": task_row.get("lv3", ""),
                "task": task_row.get("task", ""),
                "sub_task": task_row.get("sub_task", ""),
                "news_title": news_row.get("title", ""),
                "link": news_row.get("link", ""),
                "score": score,
            })
    return pd.DataFrame(rows)
