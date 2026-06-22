"""작업 정의 시드 — 리포에 커밋된 엑셀을 DB 가 비어 있을 때 1회 적재.

`data/` 는 `.gitignore` + 호스팅 디스크 휘발(무료 플랜)이라 작업 정의가 세션·재배포마다
사라진다. 이 모듈을 컨테이너 부팅 시작 커맨드에서 호출(`python -m roadmap.seed`)하면
DB 가 비어 있을 때 시드 엑셀을 적재한다 — **idempotent**(이미 데이터가 있으면 건너뜀,
영구 디스크/유료 플랜에서 사용자가 재업로드한 데이터를 덮어쓰지 않음).

시드 파일 교체: `roadmap/seed_data/task_defs.xlsx` 를 새 엑셀로 바꾸면 끝.
(앱 startup 이벤트가 아니라 시작 커맨드에서만 도므로 테스트/일반 import 에는 영향 없음.)
"""
from __future__ import annotations

from pathlib import Path

SEED_PATH = Path(__file__).resolve().parent / "seed_data" / "task_defs.xlsx"


def seed_if_empty() -> int:
    """DB 가 비어 있고 시드 파일이 있으면 적재. 적재 건수 반환(건너뛰면 0).

    부수효과: `roadmap.ingest.ingest_excel(replace=True)` 가 SQLite/Parquet/canonical JSON
    을 기록. 실패해도 예외를 올리지 않고 0 을 반환(부팅을 막지 않기 위해 — 시작 커맨드에서
    `|| true` 없이도 안전).
    """
    try:
        from config import ensure_data_dirs
        from store import task_defs_db

        ensure_data_dirs()
        if task_defs_db.list_all():
            return 0  # 이미 데이터 존재 — 건너뜀(사용자 편집 보존)
        if not SEED_PATH.exists():
            return 0

        from roadmap.ingest import ingest_excel

        with open(SEED_PATH, "rb") as f:
            res = ingest_excel(f, replace=True)
        return int(getattr(res, "row_count", 0) or 0)
    except Exception as exc:  # noqa: BLE001 — 시드 실패가 서버 부팅을 막으면 안 됨
        print(f"[seed] 작업 정의 시드 실패(무시): {exc}")
        return 0


if __name__ == "__main__":
    n = seed_if_empty()
    print(f"[seed] 작업 정의 {n}건 적재 완료" if n else "[seed] 건너뜀 (이미 존재하거나 시드 파일 없음)")
