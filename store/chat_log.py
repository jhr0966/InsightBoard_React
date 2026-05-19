"""사이드 채팅 히스토리 영구 저장 (JSONL).

각 페이지/채팅이 자체 파일에 보존되도록 `chat_key` 별 분리 지원. 기존 호출(인자 없음)
은 `chat_key="default"` 로 매핑되어 후방 호환을 유지한다 (`data/sola/chat_history.jsonl`
경로 보존).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from config import SOLA_DIR, ensure_data_dirs


_CHAT_DIR_NAME = "chat"
_DEFAULT_KEY = "default"


def _safe_key(chat_key: str) -> str:
    """파일명 안전한 슬러그 (영숫자/`-`/`_` 만)."""
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", chat_key or _DEFAULT_KEY) or _DEFAULT_KEY


def _path(chat_key: str = _DEFAULT_KEY) -> Path:
    ensure_data_dirs()
    if chat_key == _DEFAULT_KEY:
        # 후방 호환: 기존 단일 파일 위치 유지.
        return SOLA_DIR / "chat_history.jsonl"
    chat_dir = SOLA_DIR / _CHAT_DIR_NAME
    chat_dir.mkdir(parents=True, exist_ok=True)
    return chat_dir / f"{_safe_key(chat_key)}.jsonl"


def save_history(messages: list[dict], chat_key: str = _DEFAULT_KEY) -> Path:
    """전체 히스토리를 한 번에 덮어쓴다 (간단·재현성 우선)."""
    p = _path(chat_key)
    with p.open("w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps({"role": m["role"], "content": m["content"]}, ensure_ascii=False))
            f.write("\n")
    return p


def load_history(chat_key: str = _DEFAULT_KEY) -> list[dict]:
    p = _path(chat_key)
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


def reset(chat_key: str = _DEFAULT_KEY) -> None:
    p = _path(chat_key)
    if p.exists():
        p.unlink()
