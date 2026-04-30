from __future__ import annotations

from typing import Any


def build_workspace_metrics(session_state: Any) -> dict[str, int]:
    naver_count = len(session_state.get("articles_naver", []))
    tech_count = len(session_state.get("articles_tech", []))
    proposal_count = len(session_state.get("proposal_results", []))
    return {
        "naver_articles": naver_count,
        "tech_articles": tech_count,
        "total_articles": naver_count + tech_count,
        "proposals": proposal_count,
    }
