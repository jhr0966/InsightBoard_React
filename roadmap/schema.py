"""조선소 제조기술 로드맵 엑셀 스키마.

엑셀 한국어 헤더를 snake_case 로 정규화한다.

계층 (구버전 / 신버전 호환):
  team > dept > (division) > (process) > lv1 > lv2 > lv3 > task > sub_task

신버전 엑셀 (2026-05+):
  - "분과" → division (예: 구조내업)
  - "공정" → process (예: 판넬, 조립)
  - "공정정의서(줄글)" → task_def (기존)
  - "공정정의서(JSON)" → task_def_json (신규, 구조화된 JSON 텍스트)

호환 매핑 (ingest.normalize_columns):
  - 신엑셀에 lv1/lv2/lv3 가 없으면 division/process/task 로 자동 fallback —
    기존 사용처(보드 ④/⑥, 인사이트 매트릭스/공정 매핑, persona interest_lv3)는
    그대로 동작.
"""
from __future__ import annotations

from dataclasses import dataclass


# 엑셀 한국어 헤더 → 코드 컬럼
COLUMN_MAP: dict[str, str] = {
    # 기본 계층
    "팀": "team",
    "부서": "dept",
    # 신버전 추가 계층
    "분과": "division",
    "공정": "process",
    # 구버전 lv1/lv2/lv3 (호환 유지)
    "분류(Lv1)": "lv1",
    "소분류(Lv2)": "lv2",
    "공정(Lv3)": "lv3",
    # 작업
    "작업": "task",
    "세부 작업": "sub_task",
    "세부작업": "sub_task",
    # 공정 고유 ID (신버전 9 컬럼 폼 — SQLite PK)
    "공정ID": "process_id",
    "공정 ID": "process_id",
    "공정아이디": "process_id",
    # 작업 정의 (줄글 / 구조화 JSON)
    "작업 정의": "task_def",
    "작업정의": "task_def",
    "공정정의서(줄글)": "task_def",
    "공정 정의서(줄글)": "task_def",
    "공정정의서(JSON)": "task_def_json",
    "공정 정의서(JSON)": "task_def_json",
    # SWS
    "SWS 표준번호": "sws_no",
    "SWS표준번호": "sws_no",
    "SWS명": "sws_name",
}

REQUIRED_COLUMNS: tuple[str, ...] = (
    "team", "dept", "lv1", "lv2", "lv3", "task",
)

OPTIONAL_COLUMNS: tuple[str, ...] = (
    "sub_task",
    "task_def",
    "task_def_json",   # 신버전 구조화 JSON
    "division",        # 신버전 "분과"
    "process",         # 신버전 "공정"
    "process_id",      # 신버전 "공정ID" — SQLite PK (없으면 JSON 내부에서 추출)
    "sws_no",
    "sws_name",
)

ALL_COLUMNS: tuple[str, ...] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


@dataclass(frozen=True)
class RoadmapRow:
    team: str
    dept: str
    lv1: str
    lv2: str
    lv3: str
    task: str
    sub_task: str = ""
    task_def: str = ""
    task_def_json: str = ""   # 신규 — Structured JSON 원본 텍스트
    division: str = ""         # 신규 — 분과
    process: str = ""          # 신규 — 공정
    process_id: str = ""       # 신규 — 공정ID (SQLite PK)
    sws_no: str = ""
    sws_name: str = ""
