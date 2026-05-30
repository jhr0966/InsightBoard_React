"""작업 정의 Structured JSON 파서 + 자동화/품질 신호 추출.

신버전 엑셀(2026-05+) 의 `task_def_json` 컬럼은 각 행마다 다음과 같은 JSON 텍스트:

    {
      "process_domain": "조선소 생산관리",
      "process_category": "판넬",
      "process_name": "판넬 선별 (Panel Main Plate Inspection & Loading)",
      "process_id": "PNL-SEL-001",
      "process_description": "...",
      "objectives": ["BOM 기준 주판 수입 검수", ...],
      "related_processes": [...],
      "crane_safety_standards": [...],
      "sub_processes": [...],
      "overall_quality_risks": [...],
      "automation_potential_areas": [...]
    }

이 모듈은 안전한 파싱(실패 시 빈 dict) + 자동화 매칭/LLM 컨텍스트에 자주
쓰는 필드 추출 헬퍼 제공.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


TOP_LEVEL_KEYS: tuple[str, ...] = (
    "process_domain",
    "process_category",
    "process_name",
    "process_id",
    "process_description",
    "objectives",
    "related_processes",
    "crane_safety_standards",
    "sub_processes",
    "overall_quality_risks",
    "automation_potential_areas",
)


@dataclass(frozen=True)
class TaskDef:
    """파싱된 작업 정의 — JSON 원본을 dict 로. 비어있으면 모든 필드 빈 값."""
    process_id: str = ""
    process_name: str = ""
    process_description: str = ""
    objectives: tuple[str, ...] = ()
    overall_quality_risks: tuple[str, ...] = ()
    automation_potential_areas: tuple[str, ...] = ()
    raw: dict | None = None

    def is_empty(self) -> bool:
        return not (
            self.process_id or self.process_name or self.process_description
            or self.objectives or self.overall_quality_risks
            or self.automation_potential_areas
        )


def parse(s: str | None) -> TaskDef:
    """JSON 텍스트 → TaskDef. 파싱 실패 / 빈 입력 → 빈 TaskDef.

    안전: 어떤 입력에도 예외 던지지 않음. raw 가 None 이면 빈 TaskDef.
    """
    if not s or not isinstance(s, str):
        return TaskDef()
    s = s.strip()
    if not s:
        return TaskDef()
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return TaskDef()
    if not isinstance(obj, dict):
        return TaskDef()

    def _flatten_item(item, *, head_keys: tuple[str, ...] = ()) -> str:
        """str/숫자 → 문자열, dict → 'k1: v1 · k2: v2' 평탄화.

        dict 인 경우 head_keys 가 지정되면 그 키들의 값만 추출(없으면 모든 값).
        예) {"area":"X","technology":"Y"} + head_keys=("area","technology")
            → "X · Y"
        """
        if isinstance(item, (str, int, float)):
            return str(item).strip()
        if isinstance(item, dict):
            if head_keys:
                vals = [str(item.get(k, "") or "").strip() for k in head_keys]
                vals = [v for v in vals if v]
                if vals:
                    return " · ".join(vals)
            return " · ".join(
                f"{k}: {v}" for k, v in item.items()
                if isinstance(v, (str, int, float)) and str(v).strip()
            )
        return ""

    def _list_of(key: str, *, head_keys: tuple[str, ...] = ()) -> tuple[str, ...]:
        v = obj.get(key)
        if not isinstance(v, list):
            return ()
        return tuple(s for s in (_flatten_item(item, head_keys=head_keys) for item in v) if s)

    return TaskDef(
        process_id=str(obj.get("process_id", "") or "").strip(),
        process_name=str(obj.get("process_name", "") or "").strip(),
        process_description=str(obj.get("process_description", "") or "").strip(),
        objectives=_list_of("objectives"),
        # 신엑셀 구조: dict 리스트 → "risk · consequence"
        overall_quality_risks=_list_of("overall_quality_risks", head_keys=("risk", "consequence")),
        # 신엑셀 구조: dict 리스트 → "area · technology · expected_effect"
        automation_potential_areas=_list_of(
            "automation_potential_areas",
            head_keys=("area", "technology", "expected_effect"),
        ),
        raw=obj,
    )


def automation_keywords(task: TaskDef, max_n: int = 10) -> list[str]:
    """자동화 매칭에 쓸 키워드 — automation_potential_areas 의 area + technology.

    각 entry 가 "area · technology · expected_effect" 평탄화된 문자열이므로
    " · " 로 분리해 각 토큰을 키워드로. 60자 초과 토큰은 첫 절만.
    """
    out: list[str] = []
    seen: set[str] = set()
    for entry in task.automation_potential_areas:
        for token in entry.split(" · "):
            token = token.strip()
            if not token or token in seen:
                continue
            head = token.split(".")[0].split(",")[0].split(";")[0].strip()
            if head and len(head) <= 60:
                out.append(head)
                seen.add(head)
            if len(out) >= max_n:
                return out
    return out


def to_chat_context_lines(task: TaskDef, *, indent: str = "  ") -> list[str]:
    """LLM 시스템 메시지에 첨부할 다중 라인 — SOLA 가 작업 상세 답변 가능하도록."""
    if task.is_empty():
        return []
    lines: list[str] = []
    if task.process_id or task.process_name:
        head = " · ".join(p for p in (task.process_id, task.process_name) if p)
        lines.append(f"{indent}작업 정의: {head}")
    if task.process_description:
        lines.append(f"{indent}  설명: {task.process_description[:200]}")
    if task.objectives:
        lines.append(f"{indent}  목표: " + " / ".join(o[:80] for o in task.objectives[:3]))
    if task.overall_quality_risks:
        lines.append(f"{indent}  품질 리스크: " + " / ".join(r[:80] for r in task.overall_quality_risks[:3]))
    if task.automation_potential_areas:
        lines.append(f"{indent}  자동화 영역: " + " / ".join(a[:80] for a in task.automation_potential_areas[:3]))
    return lines
