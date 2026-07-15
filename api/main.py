"""FastAPI 진입점 — `uvicorn api.main:app`.

Phase 1 백엔드 셸. 라우터를 등록하고 CORS(React dev 서버)·헬스체크를 제공한다.
도메인 엔드포인트는 `api/routers/*` 로 점진 추가(taskdefs 가 첫 레퍼런스).
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    assistant,
    board,
    bookmarks,
    cases,
    collect,
    feedback,
    insights,
    matches,
    news,
    opportunities,
    persona,
    prefs,
    proposals,
    sources,
    taskdefs,
    threads,
    trends,
)

app = FastAPI(
    title="InsightBoard API",
    version="0.1.0",
    summary="조선소 작업정의 × 외부 기술동향 매칭 — React 전환용 백엔드 계약",
)

# React dev 서버 / 배포 프론트 origin. 쉼표 구분 env 로 오버라이드.
_origins = os.getenv(
    "INSIGHTBOARD_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    """헬스체크 — 배포 readiness 프로브용. 의존성과 무관하게 항상 200(liveness)."""
    return {"status": "ok", "phase": "1"}


@app.get("/api/health/deps", tags=["meta"])
def health_deps() -> dict:
    """진단용 — 핵심 의존성(LLM·작업정의·뉴스) 상태를 표면화.

    `/api/health`(liveness)와 분리: 여기서 LLM 미설정/뉴스 0 이어도 200 을 반환하되
    `ready` 플래그로 운영 점검을 돕는다(배포 프로브가 이 결과로 흔들리지 않게).
    """
    llm = {"configured": False, "provider": None}
    try:
        from config import llm_provider
        from sola import client as _llm

        llm = {"configured": _llm.is_configured(), "provider": llm_provider()}
    except Exception as exc:  # noqa: BLE001 — 진단은 부분 실패해도 200
        llm = {"configured": False, "provider": None, "error": str(exc)}

    taskdefs_n = None
    try:
        from store import task_defs_db

        taskdefs_n = len(task_defs_db.list_all())
    except Exception as exc:  # noqa: BLE001
        taskdefs_n = f"error: {exc}"

    news_n = None
    try:
        from store import news_db

        news_n = int(len(news_db.load_news_for_days(7)))
    except Exception as exc:  # noqa: BLE001
        news_n = f"error: {exc}"

    return {
        "status": "ok",
        "ready": bool(isinstance(taskdefs_n, int) and taskdefs_n > 0),
        "llm": llm,
        "taskdefs": taskdefs_n,
        "news_7d": news_n,
    }


app.include_router(board.router)
app.include_router(taskdefs.router)
app.include_router(bookmarks.router)
app.include_router(news.router)
app.include_router(trends.router)
app.include_router(opportunities.router)
app.include_router(proposals.router)
app.include_router(collect.router)
app.include_router(threads.router)
app.include_router(assistant.router)
app.include_router(persona.router)
app.include_router(prefs.router)
app.include_router(sources.router)
app.include_router(matches.router)
app.include_router(insights.router)
app.include_router(feedback.router)
app.include_router(cases.router)
