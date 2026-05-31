"""Data management health dashboard for the workflow shell.

Phase 4 UX: show whether news, roadmap, enrich, and LLM prerequisites are
ready before users enter the detailed collection/upload tabs.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from roadmap.query import load_latest as load_roadmap
from sola.client import is_configured as llm_ready
from store.news_db import load_all_today
from ui.components import render_html, metric_card, metric_grid, status_card
from ui.styles import section_label


def content_ready_count(news: pd.DataFrame) -> int:
    """Return rows with enough article body text for summary/matching work."""
    if news.empty or "content" not in news.columns:
        return 0
    return int((news["content"].astype(str).str.len() >= 50).sum())


def _source_count(news: pd.DataFrame) -> int:
    if news.empty or "source" not in news.columns:
        return 0
    return int(news["source"].nunique())


def _dept_count(roadmap: pd.DataFrame) -> int:
    if roadmap.empty or "dept" not in roadmap.columns:
        return 0
    return int(roadmap["dept"].nunique())


def enrich_percent(news: pd.DataFrame) -> int:
    """Return integer enrich completion percent for today's de-duplicated news."""
    if news.empty:
        return 0
    return round(content_ready_count(news) / len(news) * 100)


def data_quality_items(
    news: pd.DataFrame,
    roadmap: pd.DataFrame,
    *,
    llm_configured: bool,
) -> list[dict[str, str]]:
    """Build data quality status items in the order users should resolve them."""
    enriched = content_ready_count(news)
    items: list[dict[str, str]] = []

    if news.empty:
        items.append({
            "title": "뉴스 DB 준비 필요",
            "body": "뉴스 수집·Enrich 탭에서 키워드와 소스를 선택해 오늘 분석할 기사를 저장하세요.",
            "status": "warn",
            "icon": "📰",
        })
    else:
        items.append({
            "title": "뉴스 DB 준비됨",
            "body": f"오늘 기사 {len(news):,}건이 저장되어 있습니다. 소스 {_source_count(news):,}개를 기준으로 트렌드를 볼 수 있습니다.",
            "status": "ok",
            "icon": "📰",
        })

    if news.empty:
        items.append({
            "title": "본문 Enrich 대기",
            "body": "먼저 뉴스를 수집해야 본문 확보와 LLM 요약을 진행할 수 있습니다.",
            "status": "warn",
            "icon": "✨",
        })
    elif enriched == len(news):
        items.append({
            "title": "본문 Enrich 완료",
            "body": f"{enriched:,}/{len(news):,}건의 본문이 확보되어 요약·키워드·매칭 품질이 안정적입니다.",
            "status": "ok",
            "icon": "✨",
        })
    else:
        items.append({
            "title": "본문 Enrich 추가 필요",
            "body": f"{enriched:,}/{len(news):,}건만 본문이 확보되어 있습니다. 미처리 기사를 Enrich하세요.",
            "status": "warn",
            "icon": "✨",
        })

    if roadmap.empty:
        items.append({
            "title": "작업 정의 DB 준비 필요",
            "body": "작업 정의 데이터 업로드 탭에서 Master_Table 엑셀을 저장해야 뉴스가 부서·공정 작업과 연결됩니다.",
            "status": "warn",
            "icon": "🗂",
        })
    else:
        items.append({
            "title": "작업 정의 DB 준비됨",
            "body": f"작업 {len(roadmap):,}건과 부서 {_dept_count(roadmap):,}개가 저장되어 인사이트 분석 매칭에 사용할 수 있습니다.",
            "status": "ok",
            "icon": "🗂",
        })

    if llm_configured:
        items.append({
            "title": "LLM 연결 준비됨",
            "body": "SOLA 한 줄 해석, 부서 인사이트, 제안서 초안 생성에 LLM을 사용할 수 있습니다.",
            "status": "ok",
            "icon": "🤖",
        })
    else:
        items.append({
            "title": "LLM 설정 확인 필요",
            "body": "LLM_API_KEY/LLM_BASE_URL/LLM_MODEL을 설정하면 Enrich 요약과 SOLA 분석이 활성화됩니다.",
            "status": "warn",
            "icon": "🤖",
        })

    return items


def data_health_html(news: pd.DataFrame, roadmap: pd.DataFrame, *, llm_configured: bool) -> str:
    """Render the data readiness dashboard as escaped component HTML."""
    enriched = content_ready_count(news)
    enrich_pct = enrich_percent(news)
    metrics = metric_grid([
        metric_card("오늘 뉴스", f"{len(news):,}건", caption=f"소스 {_source_count(news):,}개", icon="📰", tone="info"),
        metric_card("본문 확보율", f"{enrich_pct}%", caption=f"{enriched:,}/{len(news):,}건", icon="✨", tone="ok" if enrich_pct == 100 and len(news) else "warn"),
        metric_card("정의된 작업", f"{len(roadmap):,}건", caption=f"부서 {_dept_count(roadmap):,}개", icon="🗂", tone="teal" if len(roadmap) else "warn"),
        metric_card("LLM", "Ready" if llm_configured else "Check", caption="SOLA 분석 엔진", icon="🤖", tone="ok" if llm_configured else "warn"),
    ])
    cards = "".join(
        status_card(item["title"], item["body"], status=item["status"], icon=item["icon"])
        for item in data_quality_items(news, roadmap, llm_configured=llm_configured)
    )
    return metrics + '<div class="data-quality-grid">' + cards + "</div>"


def build_data_context(news: pd.DataFrame, roadmap: pd.DataFrame, *, llm_configured: bool) -> str:
    """Compact text context for future chat/diagnostics usage."""
    return "\n".join([
        "화면: 데이터 관리 준비 상태",
        f"오늘 뉴스: {len(news):,}건 / 본문 확보: {content_ready_count(news):,}건 ({enrich_percent(news)}%)",
        f"정의된 작업: {len(roadmap):,}건 / 부서: {_dept_count(roadmap):,}개",
        f"LLM 설정: {'준비됨' if llm_configured else '확인 필요'}",
    ])


def render() -> None:
    """Render the Phase 4 data readiness overview above detailed data tabs."""
    news = load_all_today()
    roadmap = load_roadmap()
    section_label("데이터 준비 상태")
    render_html(
        data_health_html(news, roadmap, llm_configured=llm_ready()),
        unsafe_allow_html=True,
    )
