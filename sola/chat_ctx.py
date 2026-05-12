"""채팅용 컨텍스트 조립 — 오늘 뉴스/로드맵 요약을 시스템 프롬프트에 주입."""
from __future__ import annotations

import pandas as pd


def build_context_block(
    news_df: pd.DataFrame,
    roadmap_df: pd.DataFrame,
    *,
    max_news: int = 12,
    proposal: str | None = None,
) -> str:
    """채팅 시스템 메시지 뒤에 붙일 컨텍스트 블록.

    `proposal` 이 주어지면 가장 먼저 배치돼 LLM 이 우선 참고하도록 한다.
    """
    parts: list[str] = []

    if proposal:
        parts.append("[첨부 제안서]\n" + proposal.strip())

    if not news_df.empty:
        lines = []
        for i, (_, row) in enumerate(news_df.head(max_news).iterrows(), start=1):
            title = str(row.get("title", "")).replace("\n", " ").strip()
            press = str(row.get("press", "")).strip()
            lines.append(f"  [{i}] {title} — {press}")
        parts.append("[오늘 뉴스 헤드라인]\n" + "\n".join(lines))

    if not roadmap_df.empty:
        dept_counts = (
            roadmap_df.groupby("dept", dropna=False).size()
            .sort_values(ascending=False).head(8).to_dict()
        )
        lv3_counts = (
            roadmap_df.groupby("lv3", dropna=False).size()
            .sort_values(ascending=False).head(8).to_dict()
        )
        parts.append(
            "[로드맵 요약]\n"
            f"- 전체 작업 수: {len(roadmap_df):,}\n"
            f"- 부서 분포: {dept_counts}\n"
            f"- 공정(Lv3) 분포: {lv3_counts}"
        )

    if not parts:
        return ""
    return "\n\n--- 참고 컨텍스트 ---\n" + "\n\n".join(parts)
