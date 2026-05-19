"""뉴스 요약 — 일자별/키워드별 article dict 리스트를 LLM 으로 요약."""
from __future__ import annotations

import pandas as pd

from sola.client import LLMNotConfigured, chat
from sola.preview import format_messages_preview
from sola.prompts import SYSTEM_SUMMARIZE


def _format_articles(df: pd.DataFrame, *, max_items: int = 20) -> str:
    if df.empty:
        return "(뉴스 없음)"
    cols = [c for c in ("title", "press", "summary", "link") if c in df.columns]
    lines: list[str] = []
    for i, (_, row) in enumerate(df.head(max_items).iterrows(), start=1):
        title = str(row.get("title", "")).replace("\n", " ").strip()
        press = str(row.get("press", "")).strip()
        summary = str(row.get("summary", "")).replace("\n", " ").strip()[:200]
        lines.append(f"[{i}] {title} — {press}\n    요지: {summary}")
    return "\n".join(lines)


def summarize_news(df: pd.DataFrame, *, max_items: int = 20) -> str:
    """뉴스 DataFrame 을 마크다운 요약으로. LLM 미설정 시 입력 컨텍스트 미리보기 반환."""
    user = (
        "다음은 오늘 수집된 조선소·제조기술 관련 뉴스 목록입니다.\n"
        "내용을 분석해 요약을 작성하세요.\n\n"
        f"{_format_articles(df, max_items=max_items)}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_SUMMARIZE},
        {"role": "user", "content": user},
    ]
    try:
        return chat(messages=messages, temperature=0.2)
    except LLMNotConfigured as e:
        return format_messages_preview(
            messages,
            header=f"⚠️ LLM 미설정 ({e}) — 뉴스 요약 시 전달될 입력 컨텍스트",
        )
