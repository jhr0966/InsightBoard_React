"""화면 템플릿의 {{TOKEN}} placeholder 가 모듈에서 모두 소비되는지 정적 검증 (백로그 4.3).

screens/*_main.html 과 ui/*_v2.py 는 `.replace("{{TOKEN}}", ...)` 문자열 치환으로
연결된다. placeholder 가 리네임됐는데 한쪽만 바뀌면 **silent 빈/리터럴 렌더**가 난다.
렌더 없이(정적) 모든 토큰이 모듈 소스에 참조되는지 교차검증해 드리프트를 차단.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from config import ASSETS_DIR

_MODULE = {
    "board": "ui/board_v2.py",
    "data_management": "ui/data_management_v2.py",
    "insights": "ui/insights_v2.py",
    "archive": "ui/archive_v2.py",
}

_TOKEN_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")


@pytest.mark.parametrize("screen", sorted(_MODULE))
def test_all_template_placeholders_consumed(screen):
    tpl = (ASSETS_DIR / "v2" / "screens" / f"{screen}_main.html").read_text(encoding="utf-8")
    src = Path(_MODULE[screen]).read_text(encoding="utf-8")
    tokens = set(_TOKEN_RE.findall(tpl))
    assert tokens, f"{screen}: 템플릿 placeholder 0개 — 정규식/템플릿 확인"
    missing = sorted(t for t in tokens if t not in src)
    assert not missing, f"{screen}_main.html 의 미소비 placeholder(렌더 시 그대로 노출): {missing}"
