"""자동화 과제 제안서 — 작업 1건 + 관련 뉴스로 마크다운 제안서 생성."""
from __future__ import annotations

import pandas as pd

from persona import context as persona_ctx
from persona.schema import Persona
from sola.client import chat
from sola.prompts import SYSTEM_PROPOSE


def _format_task(task: dict) -> str:
    keys = ("team", "dept", "lv1", "lv2", "lv3", "task", "sub_task", "task_def", "sws_no", "sws_name")
    return "\n".join(f"- {k}: {task.get(k, '')}" for k in keys if task.get(k))


def _format_news(news: pd.DataFrame, *, max_items: int = 10) -> str:
    if news.empty:
        return "(관련 뉴스 없음)"
    cols = [c for c in ("title", "press", "summary", "link") if c in news.columns]
    lines: list[str] = []
    for i, (_, row) in enumerate(news.head(max_items).iterrows(), start=1):
        title = str(row.get("title", "")).replace("\n", " ").strip()
        press = str(row.get("press", "")).strip()
        body = str(row.get("summary", "")).replace("\n", " ").strip()[:240]
        lines.append(f"[{i}] {title} — {press}\n    {body}")
    return "\n".join(lines)


def propose_for_task(
    task: dict,
    news_df: pd.DataFrame,
    *,
    max_news: int = 10,
    persona: Persona | None = None,
) -> str:
    user = (
        "## [작업]\n"
        f"{_format_task(task)}\n\n"
        "## [관련 뉴스]\n"
        f"{_format_news(news_df, max_items=max_news)}"
    )
    persona_block = persona_ctx.system_block(persona) if persona else ""
    return chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROPOSE + persona_block},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
