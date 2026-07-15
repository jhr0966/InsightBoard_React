"""페르소나 JSON 영구 저장 — 사용자별 파일 (개편 Step 10).

경로: `data/persona/profiles/{user_id}.json`. 과거 단일 파일(`profile.json`)은
기본 사용자(`local`) 프로필로 **최초 접근 시 자동 이관**(원본 보존 — 삭제하지
않고 복사만).

⚠ 파일 저장소는 **단일 서버 파일럿 한정** — 실제 멀티유저 서비스 전환 시
DB 저장소(repository seam, I-8)가 필요하다(docs/INVARIANTS.md I-17).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from config import DATA_ROOT, ensure_data_dirs
from persona.schema import Persona
from store._audit import DEFAULT_USER

_ID_RE = re.compile(r"[^a-zA-Z0-9._-]")
_DOTS_RE = re.compile(r"\.{2,}")  # ".." 연속 점 방어 (파일명 위생)


def _safe_user(user: str) -> str:
    """파일명 안전 슬러그 — deps._sanitize 와 동일 규칙(traversal 차단)."""
    s = _ID_RE.sub("", (user or "").strip())
    s = _DOTS_RE.sub(".", s).strip(".")[:64]
    return s or DEFAULT_USER


def _profiles_dir() -> Path:
    ensure_data_dirs()
    d = DATA_ROOT / "persona" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _legacy_path() -> Path:
    return DATA_ROOT / "persona" / "profile.json"


def _profile_path(user: str = DEFAULT_USER) -> Path:
    user = _safe_user(user)
    p = _profiles_dir() / f"{user}.json"
    # 자동 이관 — 기본 사용자의 새 파일이 없고 과거 단일 파일이 있으면 복사(원본 보존).
    if user == DEFAULT_USER and not p.exists():
        legacy = _legacy_path()
        if legacy.exists():
            try:
                p.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass
    return p


def load(user: str = DEFAULT_USER) -> Persona:
    path = _profile_path(user)
    if not path.exists():
        return Persona()
    try:
        return Persona.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return Persona()


def save(persona: Persona, user: str = DEFAULT_USER) -> Path:
    path = _profile_path(user)
    path.write_text(json.dumps(persona.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def reset(user: str = DEFAULT_USER) -> None:
    path = _profile_path(user)
    if path.exists():
        path.unlink()


# ── 온보딩 마법사 "다음에 하기" 영구 마커 ──────────────────────
# 사용자별 마커 — A 가 넘겨도 B 에겐 마법사가 뜬다.

def _dismiss_path(user: str = DEFAULT_USER) -> Path:
    return _profiles_dir() / f".onboarding_dismissed.{_safe_user(user)}"


def is_onboarding_dismissed(user: str = DEFAULT_USER) -> bool:
    if _dismiss_path(user).exists():
        return True
    # 과거 전역 마커 호환(기본 사용자에게만 인정)
    return _safe_user(user) == DEFAULT_USER and (DATA_ROOT / "persona" / ".onboarding_dismissed").exists()


def dismiss_onboarding(user: str = DEFAULT_USER) -> None:
    _dismiss_path(user).write_text("1", encoding="utf-8")


def clear_onboarding_dismiss(user: str = DEFAULT_USER) -> None:
    p = _dismiss_path(user)
    if p.exists():
        p.unlink()
    legacy = DATA_ROOT / "persona" / ".onboarding_dismissed"
    if _safe_user(user) == DEFAULT_USER and legacy.exists():
        legacy.unlink()
