"""페르소나 JSON 영구 저장 (`data/persona/profile.json`)."""
from __future__ import annotations

import json
from pathlib import Path

from config import DATA_ROOT, ensure_data_dirs
from persona.schema import Persona


def _profile_path() -> Path:
    ensure_data_dirs()
    d = DATA_ROOT / "persona"
    d.mkdir(parents=True, exist_ok=True)
    return d / "profile.json"


def load() -> Persona:
    path = _profile_path()
    if not path.exists():
        return Persona()
    try:
        return Persona.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return Persona()


def save(persona: Persona) -> Path:
    path = _profile_path()
    path.write_text(json.dumps(persona.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def reset() -> None:
    path = _profile_path()
    if path.exists():
        path.unlink()


# ── 온보딩 마법사 "다음에 하기" 영구 마커 ──────────────────────
# 페르소나 미설정이어도 사용자가 "다음에 하기"를 누르면 다시 강제로 띄우지
# 않도록 마커 파일을 남긴다. 페르소나를 실제로 저장하면 마커는 의미 없어진다
# (is_set() True 면 마법사 자체가 안 뜸).

def _dismiss_path() -> Path:
    d = DATA_ROOT / "persona"
    d.mkdir(parents=True, exist_ok=True)
    return d / ".onboarding_dismissed"


def is_onboarding_dismissed() -> bool:
    return _dismiss_path().exists()


def dismiss_onboarding() -> None:
    _dismiss_path().write_text("1", encoding="utf-8")


def clear_onboarding_dismiss() -> None:
    p = _dismiss_path()
    if p.exists():
        p.unlink()

