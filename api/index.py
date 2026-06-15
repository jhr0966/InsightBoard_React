"""Vercel Python 서버리스 진입점 (ASGI).

Vercel `@vercel/python` 런타임이 `app` (ASGI 앱)을 감지해 `/api/*` 요청을 위임한다.
로컬 개발은 `uvicorn api.main:app` 를 그대로 쓴다 — 이 파일은 Vercel 전용 shim.

주의(서버리스 제약):
- 파일시스템은 읽기전용 + `/tmp` 만 쓰기 가능 → `INSIGHTBOARD_DATA_ROOT=/tmp/data`
  (vercel.json 의 env)로 데이터 경로를 옮긴다. 단 `/tmp` 는 호출 간 휘발 →
  영구 저장은 Phase 2(Postgres)에서. 데모/읽기 위주로만 사용.
"""
from api.main import app

__all__ = ["app"]
