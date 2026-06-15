"""web/openapi.json 이 현재 FastAPI 계약과 일치하는지 — 드리프트 가드.

실패 시: `python scripts/gen_openapi.py && (cd web && npm run gen:types)` 로
스냅샷·React 타입을 재생성한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from api.main import app

_SNAPSHOT = Path(__file__).resolve().parent.parent / "web" / "openapi.json"


def test_openapi_snapshot_is_current():
    assert _SNAPSHOT.exists(), "web/openapi.json 없음 — python scripts/gen_openapi.py 실행"
    committed = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    current = json.loads(json.dumps(app.openapi()))  # 직렬화 정규화 후 비교
    assert committed == current, (
        "OpenAPI 계약이 web/openapi.json 과 다릅니다 — "
        "`python scripts/gen_openapi.py && cd web && npm run gen:types` 재생성 필요."
    )
