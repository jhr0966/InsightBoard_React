"""자동화 과제 제안서 — 작업 1건 + 관련 뉴스로 마크다운 제안서 생성."""
from __future__ import annotations

import json

import pandas as pd

from persona import context as persona_ctx
from persona.schema import Persona
from roadmap import task_def_json as tdj
from sola.client import LLMNotConfigured, chat
from sola.preview import format_messages_preview
from sola.prompts import SYSTEM_PROPOSE


def _format_task(task: dict) -> str:
    """작업 dict → 제안서 입력 텍스트.

    조직 계층 scalar(team/dept/...) + 구조화 작업정의(work_flow·품질리스크·자동화
    영역 등)를 함께 넣는다. 신엑셀(2026-05+) 작업은 `task` dict 자체가 구조화 JSON
    payload 이므로 `to_chat_context_lines` 로 핵심 신호를 풀어 LLM 이 공정 맥락에
    맞는 제안을 하도록 한다. (과거엔 이름·줄글정의만 전달해 일반론에 그쳤다.)
    """
    keys = ("team", "dept", "lv1", "lv2", "lv3", "task", "sub_task", "task_def", "sws_no", "sws_name")
    org_meta = task.get("org_meta") if isinstance(task.get("org_meta"), dict) else {}
    lines = [
        f"- {k}: {task.get(k) or org_meta.get(k, '')}"
        for k in keys
        if task.get(k) or org_meta.get(k)
    ]
    # 구조화 작업정의 신호 — task dict 가 곧 정의서 JSON payload.
    detail = tdj.to_chat_context_lines(tdj.parse(json.dumps(task, ensure_ascii=False)), indent="")
    if detail:
        lines.append("")
        lines.extend(detail)
    return "\n".join(lines)


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
    messages = [
        {"role": "system", "content": SYSTEM_PROPOSE + persona_block},
        {"role": "user", "content": user},
    ]
    try:
        return chat(messages=messages, temperature=0.3)
    except LLMNotConfigured as e:
        return format_messages_preview(
            messages,
            header=f"⚠️ LLM 미설정 ({e}) — 제안서 생성 시 전달될 입력 컨텍스트",
        )
