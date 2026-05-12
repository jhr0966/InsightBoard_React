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
