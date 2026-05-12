"""조선소 제조기술 로드맵 엑셀 스키마.

첨부 엑셀(Master_Table)의 한국어 컬럼을 snake_case 로 정규화한다.
계층: team > dept > lv1 > lv2 > lv3 > task > sub_task.
SWS는 표준작업서 매핑.
"""
from __future__ import annotations

from dataclasses import dataclass


# 첨부3 엑셀 한국어 헤더 → 코드 컬럼
COLUMN_MAP: dict[str, str] = {
    "팀": "team",
    "부서": "dept",
    "분류(Lv1)": "lv1",
    "소분류(Lv2)": "lv2",
    "공정(Lv3)": "lv3",
    "작업": "task",
    "세부 작업": "sub_task",
    "세부작업": "sub_task",
    "작업 정의": "task_def",
    "작업정의": "task_def",
    "SWS 표준번호": "sws_no",
    "SWS표준번호": "sws_no",
    "SWS명": "sws_name",
}

REQUIRED_COLUMNS: tuple[str, ...] = (
    "team", "dept", "lv1", "lv2", "lv3", "task",
)

OPTIONAL_COLUMNS: tuple[str, ...] = (
    "sub_task", "task_def", "sws_no", "sws_name",
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
    sws_no: str = ""
    sws_name: str = ""
