"""채팅용 컨텍스트 조립 — 오늘 뉴스/로드맵 요약을 시스템 프롬프트에 주입."""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

import pandas as pd

if TYPE_CHECKING:
    from store.bookmarks import Bookmark


def build_context_block(
    news_df: pd.DataFrame,
    roadmap_df: pd.DataFrame,
    *,
    max_news: int = 12,
    proposal: str | None = None,
    adopted_proposals: "Iterable[Bookmark] | None" = None,
) -> str:
    """채팅 시스템 메시지 뒤에 붙일 컨텍스트 블록.

    배치 순서: 첨부 제안서 → 채택된 제안서(이전 사이클 결정) → 오늘 뉴스 → 로드맵.

    - `proposal` 이 주어지면 LLM 이 가장 먼저 참고하도록 최상단.
    - `adopted_proposals` 는 (제목, 메모) 만 노출 → 토큰 부담 최소화. 본문 X.
    """
    parts: list[str] = []

    if proposal:
        parts.append("[첨부 제안서]\n" + proposal.strip())

    if adopted_proposals:
        lines = []
        for b in adopted_proposals:
            head = f"- {b.title}"
            if b.decided_at:
                head += f" (채택: {b.decided_at[:10]})"
            lines.append(head)
            if b.decision_note:
                lines.append(f"    메모: {b.decision_note}")
        if lines:
            parts.append("[이전 사이클에서 채택된 제안서]\n" + "\n".join(lines))

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
