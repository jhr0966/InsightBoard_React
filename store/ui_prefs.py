"""UI 표시 설정(테마·글자 크기) 영구화 — `data/ui_prefs.json`.

페르소나(사용자 정체성)와 분리된 앱 표시 환경설정. 단일 사용자 가정.
"""
from __future__ import annotations

import json
from pathlib import Path

from config import DATA_ROOT, ensure_data_dirs


THEMES = ("light", "dark", "ocean", "sunset")
FONT_SIZES = ("small", "medium", "large")
_DEFAULT = {"theme": "light", "font": "medium"}


def _path() -> Path:
    ensure_data_dirs()
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return DATA_ROOT / "ui_prefs.json"


def load() -> dict:
    """현재 표시 설정. 파일 없음/손상 시 기본값(light·medium)."""
    p = _path()
    if not p.exists():
        return dict(_DEFAULT)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT)
    theme = raw.get("theme")
    font = raw.get("font")
    return {
        "theme": theme if theme in THEMES else "light",
        "font": font if font in FONT_SIZES else "medium",
    }


def save(*, theme: str, font: str) -> dict:
    """표시 설정 저장 — 알 수 없는 값은 기본값으로 정규화."""
    prefs = {
        "theme": theme if theme in THEMES else "light",
        "font": font if font in FONT_SIZES else "medium",
    }
    _path().write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    return prefs
