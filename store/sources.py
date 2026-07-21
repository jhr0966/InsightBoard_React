"""뉴스 수집 출처 설정 영구화 (`data/sources/config.json`).

기본 출처 3개(네이버 뉴스 / 구글 뉴스 / AI Times)는 항상 목록에 존재.
사용자는 enable/disable 토글로 비활성화할 수 있고, 추가 RSS 출처를 등록할
수도 있다. (오토메이션월드는 2026-07 사이트 폐쇄로 기본 출처에서 제거 —
과거 config 의 disabled 목록에 남아 있어도 무해하게 무시된다.)

Schema (`config.json`):
    {
      "disabled": ["AI Times"],
      "custom": [
        {"name": "조선해양 e뉴스", "url": "https://...", "added_at": "..."}
      ]
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_ROOT, ensure_data_dirs


# 기본(빌트인) 출처 — 사용자가 비활성화는 가능, 제거는 불가.
# 키워드 뉴스(구글) 먼저, 뉴스 포탈(AI Times) 다음.
# (네이버 뉴스는 2026-07 기본 수집에서 제외 — 검색 마크업 미매칭·IP 이슈. 과거
#  config 의 disabled/legacy 항목에 남아 있어도 무해하게 무시된다.)
DEFAULT_SOURCES: tuple[str, ...] = (
    "구글 뉴스",
    "AI Times",
)

# 과거 표시명 → 현 표시명 (disabled 목록 등 영구 설정 호환)
_LEGACY_NAMES: dict[str, str] = {
    "네이버 기술": "네이버 뉴스",
    "Google RSS": "구글 뉴스",
}


@dataclass
class CustomSource:
    name: str
    url: str
    added_at: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "url": self.url, "added_at": self.added_at}

    @classmethod
    def from_dict(cls, d: dict) -> "CustomSource":
        return cls(
            name=str(d.get("name", "") or ""),
            url=str(d.get("url", "") or ""),
            added_at=str(d.get("added_at", "") or ""),
        )


def _config_path() -> Path:
    ensure_data_dirs()
    d = DATA_ROOT / "sources"
    d.mkdir(parents=True, exist_ok=True)
    return d / "config.json"


def _load_raw() -> dict:
    p = _config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(data: dict) -> None:
    _config_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Public API ───────────────────────────────────────────────


def disabled_set() -> frozenset[str]:
    """비활성화된 출처 이름 집합 (기본은 빈 집합). 과거 표시명은 현 이름으로 환산."""
    raw = _load_raw()
    items = raw.get("disabled") or []
    return frozenset(
        _LEGACY_NAMES.get(str(x), str(x)) for x in items if isinstance(x, str)
    )


def is_enabled(name: str) -> bool:
    """기본 출처는 disabled 목록에 없으면 활성. 커스텀 출처는 등록되어 있으면 활성."""
    if name in DEFAULT_SOURCES:
        return name not in disabled_set()
    return any(s.name == name for s in custom_sources())


def toggle_disabled(name: str) -> bool:
    """기본 출처의 disabled 토글. 반환값: 토글 후 enabled 여부.

    커스텀 출처에는 사용 불가(False 반환, 변경 없음).
    """
    if name not in DEFAULT_SOURCES:
        return False
    raw = _load_raw()
    # 과거 표시명을 현 이름으로 정규화 후 토글 — legacy 항목과 현 항목이 공존하며
    # 토글이 무력화되는 것을 방지.
    disabled = {
        _LEGACY_NAMES.get(str(x), str(x))
        for x in (raw.get("disabled") or [])
        if isinstance(x, str)
    }
    if name in disabled:
        disabled.discard(name)
        enabled_after = True
    else:
        disabled.add(name)
        enabled_after = False
    raw["disabled"] = sorted(disabled)
    _save_raw(raw)
    return enabled_after


def custom_sources() -> list[CustomSource]:
    raw = _load_raw()
    items = raw.get("custom") or []
    out: list[CustomSource] = []
    for it in items:
        if isinstance(it, dict):
            out.append(CustomSource.from_dict(it))
    return out


def add_custom(name: str, url: str) -> CustomSource:
    """커스텀 RSS 출처 추가. 같은 이름이 이미 있으면 ValueError.

    빈 이름/URL 도 ValueError. URL 은 http(s):// prefix 만 간단 검증.
    """
    name = (name or "").strip()
    url = (url or "").strip()
    if not name:
        raise ValueError("이름이 비어 있습니다.")
    if not url:
        raise ValueError("URL 이 비어 있습니다.")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL 은 http:// 또는 https:// 로 시작해야 합니다.")
    if name in DEFAULT_SOURCES:
        raise ValueError(f"'{name}' 은 기본 출처와 같은 이름입니다.")

    raw = _load_raw()
    items = raw.get("custom") or []
    if any(it.get("name") == name for it in items if isinstance(it, dict)):
        raise ValueError(f"'{name}' 출처가 이미 등록되어 있습니다.")

    new_item = CustomSource(
        name=name, url=url,
        added_at=datetime.now(timezone.utc).isoformat(),
    )
    items.append(new_item.to_dict())
    raw["custom"] = items
    _save_raw(raw)
    return new_item


def remove_custom(name: str) -> bool:
    """커스텀 출처 제거. 반환: 실제로 제거됐는지."""
    raw = _load_raw()
    items = raw.get("custom") or []
    before = len(items)
    items = [it for it in items if isinstance(it, dict) and it.get("name") != name]
    if len(items) == before:
        return False
    raw["custom"] = items
    _save_raw(raw)
    return True


def all_active() -> list[str]:
    """현재 활성 출처 이름 (기본 - disabled + 커스텀)."""
    disabled = disabled_set()
    out = [n for n in DEFAULT_SOURCES if n not in disabled]
    out.extend(s.name for s in custom_sources())
    return out
