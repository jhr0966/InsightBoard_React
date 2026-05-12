"""부서별 인사이트 카드 — 1~2문장 자동 요약, 파일 캐시."""
from __future__ import annotations

import pandas as pd

from config import llm_model
from sola.client import LLMNotConfigured, chat
from sola.prompts import SYSTEM_INSIGHT
from store import cache


def _format_news(df: pd.DataFrame, max_items: int = 8) -> str:
    if df.empty:
        return "(관련 뉴스 없음)"
    lines: list[str] = []
    for i, (_, row) in enumerate(df.head(max_items).iterrows(), start=1):
        title = str(row.get("title", "")).replace("\n", " ").strip()
        press = str(row.get("press", "")).strip()
        lines.append(f"[{i}] {title} — {press}")
    return "\n".join(lines)


def insight_for_dept(dept: str, news_df: pd.DataFrame, *, force: bool = False) -> str:
    """동일 (부서·뉴스셋·모델)에 대해서는 캐시 반환."""
    titles = " | ".join(news_df.get("title", pd.Series(dtype=str)).head(8).astype(str).tolist())
    key = cache.make_key("insight", dept, titles, llm_model() or "")
    if not force:
        hit = cache.get(key)
        if hit is not None:
            return hit

    user = (
        f"[부서] {dept}\n\n"
        f"[관련 뉴스]\n{_format_news(news_df)}"
    )
    try:
        reply = chat(
            messages=[
                {"role": "system", "content": SYSTEM_INSIGHT},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=200,
        )
    except LLMNotConfigured as e:
        return f"⚠️ LLM 미설정: {e}"
    except Exception as e:  # noqa: BLE001
        return f"⚠️ 호출 실패: {e}"

    cache.put(key, reply)
    return reply
