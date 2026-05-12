"""SOLA 채팅 히스토리 영구 저장 (JSONL).

단일 활성 대화 가정 — 한 파일에 append/overwrite. 새 대화 시작 시 reset.
"""
from __future__ import annotations

import json
from pathlib import Path

from config import SOLA_DIR, ensure_data_dirs


def _path() -> Path:
    ensure_data_dirs()
    return SOLA_DIR / "chat_history.jsonl"


def save_history(messages: list[dict]) -> Path:
    """전체 히스토리를 한 번에 덮어쓴다 (간단·재현성 우선)."""
    p = _path()
    with p.open("w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps({"role": m["role"], "content": m["content"]}, ensure_ascii=False))
            f.write("\n")
    return p


def load_history() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("role") in {"user", "assistant", "system"}:
            out.append({"role": obj["role"], "content": str(obj.get("content", ""))})
    return out


def reset() -> None:
    p = _path()
    if p.exists():
        p.unlink()
