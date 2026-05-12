"""저장 경로 유틸. 일자별 디렉토리 생성/탐색."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from config import NEWS_DIR, ROADMAP_DIR, ensure_data_dirs


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def news_dir_for(date_str: str | None = None) -> Path:
    ensure_data_dirs()
    d = NEWS_DIR / (date_str or _today())
    d.mkdir(parents=True, exist_ok=True)
    return d


def roadmap_dir() -> Path:
    ensure_data_dirs()
    return ROADMAP_DIR


def latest_parquet(base: Path, glob: str = "*.parquet") -> Path | None:
    files = sorted(base.glob(glob))
    return files[-1] if files else None
