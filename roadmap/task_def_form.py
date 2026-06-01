"""작업 정의 UI 폼 ↔ task_def JSON 변환 (PR-6).

`ui.task_def_manage` 의 추가/수정 폼이 입력한 dict 를 검증 + JSON 직렬화한다.
JSON 자체는 `task_def_json.ingest_org_meta` 가 만들고, 이 모듈은 폼 구조
(objectives 리스트, risks/automation 리스트 등) 를 매니지 가능한 형태로 정리.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from roadmap.task_def_json import (
    ORG_META_KEYS,
    TaskDefJsonError,
    ingest_org_meta,
)


@dataclass
class TaskDefForm:
    """작업 정의 폼 입력값. 모든 list 필드는 사용자가 [+추가]/[-삭제] 한 항목."""
    process_id: str = ""
    process_name: str = ""
    process_description: str = ""
    process_domain: str = ""
    process_category: str = ""
    task_def_text: str = ""
    # 리스트 필드
    objectives: list[str] = field(default_factory=list)
    overall_quality_risks: list[dict] = field(default_factory=list)
    automation_potential_areas: list[dict] = field(default_factory=list)
    # 조직 메타
    org_meta: dict = field(default_factory=dict)

    @classmethod
    def from_db_row(cls, row: dict | None) -> "TaskDefForm":
        """`task_defs_db.get(pid)` 의 결과 dict → 폼 데이터.

        json_obj 에서 필드 추출. row 가 None 이면 빈 폼.
        """
        if not row:
            return cls()
        obj = row.get("json_obj") or {}
        if not isinstance(obj, dict):
            obj = {}
        return cls(
            process_id=str(obj.get("process_id") or row.get("process_id") or ""),
            process_name=str(obj.get("process_name") or ""),
            process_description=str(obj.get("process_description") or ""),
            process_domain=str(obj.get("process_domain") or ""),
            process_category=str(obj.get("process_category") or ""),
            task_def_text=str(row.get("task_def_text") or obj.get("task_def_text") or ""),
            objectives=[str(o) for o in (obj.get("objectives") or []) if str(o).strip()],
            overall_quality_risks=_clean_dict_list(
                obj.get("overall_quality_risks") or [],
                keys=("risk", "consequence"),
            ),
            automation_potential_areas=_clean_dict_list(
                obj.get("automation_potential_areas") or [],
                keys=("area", "technology", "expected_effect"),
            ),
            org_meta=_clean_org_meta(obj.get("org_meta") or {}),
        )

    def to_json(self) -> str:
        """검증 + JSON 직렬화. 실패 → `TaskDefJsonError`."""
        pid = (self.process_id or "").strip()
        if not pid:
            raise TaskDefJsonError("process_id 는 필수입니다.")

        # 기본 payload (org_meta 제외 — ingest_org_meta 가 주입)
        payload: dict = {
            "process_id": pid,
            "process_name": (self.process_name or "").strip(),
            "process_description": (self.process_description or "").strip(),
            "process_domain": (self.process_domain or "").strip(),
            "process_category": (self.process_category or "").strip(),
            "objectives": [o.strip() for o in self.objectives if o and o.strip()],
            "overall_quality_risks": [
                {k: str(v).strip() for k, v in d.items() if str(v).strip()}
                for d in self.overall_quality_risks
                if any(str(v).strip() for v in d.values())
            ],
            "automation_potential_areas": [
                {k: str(v).strip() for k, v in d.items() if str(v).strip()}
                for d in self.automation_potential_areas
                if any(str(v).strip() for v in d.values())
            ],
        }
        if self.task_def_text and self.task_def_text.strip():
            payload["task_def_text"] = self.task_def_text.strip()

        # 빈 string 값 제거 (org_meta 외 top-level)
        payload = {k: v for k, v in payload.items()
                   if v not in ("", None) and not (isinstance(v, list) and not v)
                   or k == "process_id"}  # process_id 는 빈 값이면 위에서 raise

        # org_meta 주입 + 검증
        return ingest_org_meta(json.dumps(payload, ensure_ascii=False),
                                self.org_meta, process_id=pid)

    def add_objective(self, text: str = "") -> None:
        self.objectives.append(text)

    def remove_objective(self, idx: int) -> None:
        if 0 <= idx < len(self.objectives):
            self.objectives.pop(idx)

    def add_risk(self) -> None:
        self.overall_quality_risks.append({"risk": "", "consequence": ""})

    def remove_risk(self, idx: int) -> None:
        if 0 <= idx < len(self.overall_quality_risks):
            self.overall_quality_risks.pop(idx)

    def add_automation(self) -> None:
        self.automation_potential_areas.append(
            {"area": "", "technology": "", "expected_effect": ""}
        )

    def remove_automation(self, idx: int) -> None:
        if 0 <= idx < len(self.automation_potential_areas):
            self.automation_potential_areas.pop(idx)


def _clean_dict_list(items: list, *, keys: tuple[str, ...]) -> list[dict]:
    """리스트 안 항목들 — dict 면 그대로, str 면 첫 key 에 매핑, 그 외 무시."""
    out: list[dict] = []
    for it in items:
        if isinstance(it, dict):
            out.append({k: str(it.get(k) or "") for k in keys})
        elif isinstance(it, str) and it.strip():
            out.append({keys[0]: it.strip(), **{k: "" for k in keys[1:]}})
    return out


def _clean_org_meta(meta: dict) -> dict:
    """알려진 키만 strip 으로 유지."""
    return {k: str(meta[k]).strip()
            for k in ORG_META_KEYS
            if meta.get(k) is not None and str(meta[k]).strip()}
