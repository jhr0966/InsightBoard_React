"""파일 기반 단순 캐시. LLM 응답처럼 비싼 계산을 키로 저장.

key는 짧고 안전한 문자열(해시) 권장. 값은 UTF-8 텍스트만.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from config import SOLA_DIR, ensure_data_dirs


def _cache_dir() -> Path:
    ensure_data_dirs()
    d = SOLA_DIR / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_key(*parts: str) -> str:
    """입력 문자열들을 SHA1 로 해시한 16자 키."""
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]


def get(key: str) -> str | None:
    path = _cache_dir() / f"{key}.txt"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def put(key: str, value: str) -> None:
    path = _cache_dir() / f"{key}.txt"
    path.write_text(value, encoding="utf-8")


def clear() -> int:
    """캐시 전체 삭제. 삭제된 파일 수 반환."""
    files = list(_cache_dir().glob("*.txt"))
    for f in files:
        f.unlink(missing_ok=True)
    return len(files)
