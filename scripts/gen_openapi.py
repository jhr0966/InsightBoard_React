"""FastAPI OpenAPI 스키마 → web/openapi.json 덤프.

React 타입 자동생성(openapi-typescript)의 입력. 계약이 바뀌면 다시 돌려
`web/src/api/schema.ts` 를 재생성한다(`cd web && npm run gen:types`).

사용:
    python scripts/gen_openapi.py            # web/openapi.json 갱신
    python scripts/gen_openapi.py --check    # 최신인지 검사(CI용, 변경 있으면 비0)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))  # repo 루트(스크립트 직접 실행 시 import 보장)

from api.main import app  # noqa: E402

OUT = _ROOT / "web" / "openapi.json"


def main() -> int:
    schema = app.openapi()
    text = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("openapi.json 이 최신이 아닙니다 — `python scripts/gen_openapi.py` 실행", file=sys.stderr)
            return 1
        print("openapi.json 최신 ✓")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(schema['paths'])} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
