"""FastAPI 진입점 — `uvicorn api.main:app`.

Phase 1 백엔드 셸. 라우터를 등록하고 CORS(React dev 서버)·헬스체크를 제공한다.
도메인 엔드포인트는 `api/routers/*` 로 점진 추가(taskdefs 가 첫 레퍼런스).
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import taskdefs

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
    """헬스체크 — 배포 readiness 프로브용."""
    return {"status": "ok", "phase": "1"}


app.include_router(taskdefs.router)
