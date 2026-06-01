"""기존 로드맵 Parquet → `store.task_defs_db` SQLite 일괄 마이그 (PR-3).

`docs/TASK_DEF_PLAN.md` M1 의 1회성 마이그레이션 도구. 기존에 Parquet 으로만
저장돼 있던 작업 정의를 SQLite 로 옮긴다. Parquet 파일은 건드리지 않는다
(PR-4 가 reader 를 SQLite 로 전환할 때까지 SOT 유지).

Usage:
    python -m scripts.migrate_roadmap_to_sqlite            # 최신 Parquet 마이그
    python -m scripts.migrate_roadmap_to_sqlite --file path/to/roadmap.parquet
    python -m scripts.migrate_roadmap_to_sqlite --dry-run  # 카운트만 출력

Exit code: 마이그 1건 이상 성공 → 0, 읽을 Parquet 없음/0건 → 1.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

from roadmap.query import load_latest
from roadmap.sqlite_sync import sync_dataframe
from store.task_defs_db import db_path


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="migrate_roadmap_to_sqlite",
        description="로드맵 Parquet → SQLite(task_defs) 마이그레이션.",
    )
    parser.add_argument(
        "--file", type=str, default=None,
        help="마이그할 Parquet 경로 (생략 시 roadmap_dir 의 최신).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="실제 쓰지 않고 대상 행 수만 출력.",
    )
    parser.add_argument(
        "--changed-by", type=str, default="migration",
        help="history.changed_by 에 기록할 값.",
    )
    return parser.parse_args(argv)


def _load_df(file: str | None) -> pd.DataFrame:
    if file:
        p = Path(file)
        if not p.exists():
            print(f"[migrate] Parquet 파일 없음: {p}", file=sys.stderr)
            return pd.DataFrame()
        return pd.read_parquet(p)
    return load_latest()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    df = _load_df(args.file)

    if df is None or df.empty:
        print("[migrate] 마이그할 로드맵 데이터가 없습니다.", file=sys.stderr)
        return 1

    if args.dry_run:
        # 실제 쓰지 않고 빌드 가능 건수만 계산.
        from roadmap.sqlite_sync import row_to_task_def

        buildable = sum(
            1 for _, r in df.iterrows() if row_to_task_def(r.to_dict()) is not None
        )
        print(f"[migrate] dry-run — 총 {len(df)}행 중 {buildable}건 마이그 가능 "
              f"(skip {len(df) - buildable}).")
        return 0

    res = sync_dataframe(df, changed_by=args.changed_by, source="migration")
    print(
        f"[migrate] 완료 → SQLite: {db_path()}\n"
        f"          created={res.created} updated={res.updated} skipped={res.skipped}"
    )
    if res.errors:
        print(f"[migrate] 경고 {len(res.errors)}건:", file=sys.stderr)
        for e in res.errors[:10]:
            print(f"  - {e}", file=sys.stderr)

    return 0 if res.total_written > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
