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
import re
from dataclasses import dataclass
from typing import Any, Mapping


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


# v1.0 — `org_meta` 도입 (PR-2). ingest 가 엑셀 외곽 컬럼을 JSON 안으로 주입.
SCHEMA_VERSION: str = "1.0"

ORG_META_KEYS: tuple[str, ...] = (
    "team", "dept", "division", "process", "task", "sub_task",
    "lv1", "lv2", "lv3",
)

ORG_META_REQUIRED: tuple[str, ...] = ("team", "dept")


@dataclass(frozen=True)
class TaskDef:
    """파싱된 작업 정의 — JSON 원본을 dict 로. 비어있으면 모든 필드 빈 값."""
    process_id: str = ""
    process_name: str = ""
    process_description: str = ""
    objectives: tuple[str, ...] = ()
    overall_quality_risks: tuple[str, ...] = ()
    automation_potential_areas: tuple[str, ...] = ()
    # flat-column 엑셀(2026-06+) 에서 들어오는 추가 신호
    work_flow: str = ""
    key_check_points: tuple[str, ...] = ()
    safety_notes: tuple[str, ...] = ()
    main_equipment: tuple[str, ...] = ()
    previous_process: str = ""
    next_process: str = ""
    raw: dict | None = None

    def is_empty(self) -> bool:
        return not (
            self.process_id or self.process_name or self.process_description
            or self.objectives or self.overall_quality_risks
            or self.automation_potential_areas
            or self.work_flow or self.key_check_points
            or self.safety_notes or self.main_equipment
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
        # 신엑셀 구조: dict 리스트 → "risk · consequence" (flat-column 은 문자열 그대로)
        overall_quality_risks=_list_of("overall_quality_risks", head_keys=("risk", "consequence")),
        # 신엑셀 구조: dict 리스트 → "area · technology · expected_effect" (flat-column 은 문자열)
        automation_potential_areas=_list_of(
            "automation_potential_areas",
            head_keys=("area", "technology", "expected_effect"),
        ),
        work_flow=str(obj.get("work_flow", "") or "").strip(),
        key_check_points=_list_of("key_check_points"),
        safety_notes=_list_of("safety_notes"),
        main_equipment=_list_of("main_equipment"),
        previous_process=str(obj.get("previous_process", "") or "").strip(),
        next_process=str(obj.get("next_process", "") or "").strip(),
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
    if task.work_flow:
        lines.append(f"{indent}  작업 흐름: {task.work_flow[:200]}")
    if task.objectives:
        lines.append(f"{indent}  목표: " + " / ".join(o[:80] for o in task.objectives[:3]))
    if task.key_check_points:
        lines.append(f"{indent}  주요 확인사항: " + " / ".join(k[:80] for k in task.key_check_points[:3]))
    if task.overall_quality_risks:
        lines.append(f"{indent}  품질 리스크: " + " / ".join(r[:80] for r in task.overall_quality_risks[:3]))
    if task.safety_notes:
        lines.append(f"{indent}  안전 주의사항: " + " / ".join(s[:80] for s in task.safety_notes[:3]))
    if task.automation_potential_areas:
        lines.append(f"{indent}  자동화 영역: " + " / ".join(a[:80] for a in task.automation_potential_areas[:3]))
    if task.main_equipment:
        lines.append(f"{indent}  주요 사용장비: " + " / ".join(e[:60] for e in task.main_equipment[:5]))
    if task.previous_process or task.next_process:
        flow = " → ".join(
            p for p in (task.previous_process, "(현 공정)", task.next_process) if p
        )
        lines.append(f"{indent}  공정 연결: {flow}")
    return lines


def flatten_for_match(json_text: str | None) -> str:
    """JSON 정의서 → 매칭용 평탄 텍스트.

    `store.match._tokens` 가 한국어/영숫자 토큰 추출 후 set 교집합으로 점수화.
    여기서는 매칭에 의미있는 textual signal (process_name, description,
    objectives, risks, automation areas) 을 모두 합쳐 공백 join. 토큰 추출은
    호출자(`score_matches`) 가 알아서.

    빈 입력 → 빈 문자열.
    """
    t = parse(json_text)
    if t.is_empty():
        return ""
    parts: list[str] = []
    if t.process_name:
        parts.append(t.process_name)
    if t.process_description:
        parts.append(t.process_description)
    if t.work_flow:
        parts.append(t.work_flow)
    parts.extend(t.objectives)
    parts.extend(t.key_check_points)
    parts.extend(t.overall_quality_risks)
    parts.extend(t.safety_notes)
    parts.extend(t.automation_potential_areas)
    parts.extend(t.main_equipment)
    return " ".join(p for p in parts if p)


def first_objective(json_text: str | None) -> str:
    """JSON 정의서의 첫 objective 한 줄 — 보드 카드 tagline 등에 노출."""
    t = parse(json_text)
    if t.objectives:
        return t.objectives[0]
    return ""


# ── flat-column 엑셀(2026-06+) 조립 ─────────────────────────
#
# JSON 열이 없는 엑셀: 개별 컬럼(공정설명·작업흐름·주요확인사항·안전주의사항·
# 주요사용장비·품질리스크·자동화가능영역·이전공정·다음공정)을 구조화 JSON 으로
# 조립한다. `ingest.normalize_columns` 가 task_def_json 이 빈 행에 한해 호출 →
# 이후 매칭/보드/SOLA/SQLite 가 기존과 동일하게 task_def_json 을 읽는다.

# (엑셀 컬럼 코드, JSON 키) — scalar(문자열) 필드
_COL_SCALAR_FIELDS: tuple[tuple[str, str], ...] = (
    ("process_description", "process_description"),
    ("work_flow", "work_flow"),
    ("previous_process", "previous_process"),
    ("next_process", "next_process"),
)

# (엑셀 컬럼 코드, JSON 키) — list 필드. 셀을 줄바꿈/`;`/불릿으로 분리.
# 품질리스크·자동화가능영역은 매칭/SOLA 가 읽는 표준 키로 매핑해 즉시 반영되게 한다.
_COL_LIST_FIELDS: tuple[tuple[str, str], ...] = (
    ("key_check_points", "key_check_points"),
    ("safety_notes", "safety_notes"),
    ("main_equipment", "main_equipment"),
    ("quality_risks", "overall_quality_risks"),
    ("automation_areas", "automation_potential_areas"),
)

_LIST_SPLIT_RE = re.compile(r"[\n;•·]+")
_BULLET_PREFIX_RE = re.compile(r"^\s*[-*•·]\s+")


def split_list_cell(cell: Any) -> list[str]:
    """엑셀 셀 1개 → 항목 리스트. 줄바꿈 / `;` / `•` / `·` 로 분리.

    각 항목의 선행 불릿(`- `, `* `, `• `, `· `)은 제거하고 strip. 빈 항목·중복 제외.
    한 줄이면 1개짜리 리스트, None/빈 셀이면 빈 리스트.
    """
    if cell is None:
        return []
    s = str(cell).strip()
    if not s:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for part in _LIST_SPLIT_RE.split(s):
        item = _BULLET_PREFIX_RE.sub("", part).strip()
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _col_cell(row: Mapping[str, Any], key: str) -> str:
    v = row.get(key, "")
    if v is None:
        return ""
    return str(v).strip()


def assemble_from_columns(row: Mapping[str, Any]) -> dict:
    """flat-column 엑셀 행 → task_def JSON payload(dict).

    org_meta / process_id 는 넣지 않는다(`ingest_org_meta` 가 주입). 신 컬럼에
    내용이 하나도 없으면 빈 dict 를 돌려준다 — 구 포맷(lv1/lv2/lv3) 행은 그대로
    task_def_json 이 비어 기존 동작이 보존된다.

    process_name 컬럼은 없으므로, 신 컬럼에 내용이 있을 때에 한해 세부작업→작업
    중 가장 구체적인 값을 process_name 으로 보강한다(보드 카드·검색·diff 표시명용).
    """
    payload: dict = {}
    for col, field in _COL_SCALAR_FIELDS:
        v = _col_cell(row, col)
        if v:
            payload[field] = v
    for col, field in _COL_LIST_FIELDS:
        items = split_list_cell(row.get(col))
        if items:
            payload[field] = items
    if not payload:
        return {}
    name = _col_cell(row, "sub_task") or _col_cell(row, "task")
    if name:
        payload["process_name"] = name
    return payload


# ── v1.0 org_meta 확장 (PR-2) ──────────────────────────────

class TaskDefJsonError(ValueError):
    """task_def_json 스키마/주입 검증 실패."""


def _normalize_org_meta(meta: dict) -> dict:
    """입력 dict 에서 ORG_META_KEYS 만 추려 정규화 (빈 값 → 누락 처리).

    - 알려진 키만 통과 (unknown key 는 silent 무시)
    - 값은 str 로 강제 + strip. 빈 문자열은 None 으로
    - team/dept 가 비면 TaskDefJsonError
    """
    if not isinstance(meta, dict):
        raise TaskDefJsonError("org_meta must be an object")
    out: dict = {}
    for k in ORG_META_KEYS:
        v = meta.get(k)
        if v is None:
            continue
        sv = str(v).strip()
        if sv:
            out[k] = sv
    for k in ORG_META_REQUIRED:
        if not out.get(k):
            raise TaskDefJsonError(f"org_meta.{k} is required")
    return out


def ingest_org_meta(
    json_text: str | None,
    org_meta: dict,
    *,
    process_id: str | None = None,
    version: str = SCHEMA_VERSION,
) -> str:
    """기존 task_def JSON 텍스트에 `org_meta` + `version` + `process_id` 를 주입.

    - 입력 JSON 이 비어있거나 파싱 실패 → 새 dict 로 시작
    - `org_meta` 는 `_normalize_org_meta` 거쳐 알려진 키만 보존
    - `process_id` 인자가 주어지면 JSON 의 그 필드를 덮어쓰기 (외부 source-of-truth)
    - 항상 `version` 을 보장 (없으면 추가, 다르면 덮어쓰지 않음 — 호환성)
    Returns: 직렬화된 JSON 문자열 (ensure_ascii=False).
    Raises: TaskDefJsonError — org_meta 검증 실패 시.
    """
    base: dict
    if not json_text or not isinstance(json_text, str) or not json_text.strip():
        base = {}
    else:
        try:
            loaded = json.loads(json_text)
        except (json.JSONDecodeError, ValueError):
            base = {}
        else:
            base = loaded if isinstance(loaded, dict) else {}

    base["org_meta"] = _normalize_org_meta(org_meta)
    base.setdefault("version", version)
    if process_id:
        base["process_id"] = str(process_id).strip()

    return json.dumps(base, ensure_ascii=False)


def org_meta_of(json_text: str | None) -> dict:
    """JSON 에서 `org_meta` 딕셔너리만 안전 추출. 없으면 빈 dict."""
    if not json_text or not isinstance(json_text, str):
        return {}
    try:
        obj = json.loads(json_text)
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(obj, dict):
        return {}
    meta = obj.get("org_meta")
    if not isinstance(meta, dict):
        return {}
    # 알려진 키만, 빈 값 제외
    return {
        k: str(meta[k]).strip()
        for k in ORG_META_KEYS
        if meta.get(k) is not None and str(meta[k]).strip()
    }


def validate_task_def_json(json_text: str) -> dict:
    """`store.task_defs_db.upsert` 입력으로 사용 가능한지 검증.

    - JSON 파싱 성공 + dict
    - `org_meta` 존재 + team/dept 비지 않음
    - `process_id` 존재 (top-level)
    Returns: 파싱된 dict (정상).
    Raises: TaskDefJsonError.
    """
    if not json_text or not isinstance(json_text, str):
        raise TaskDefJsonError("empty json_text")
    try:
        obj = json.loads(json_text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise TaskDefJsonError(f"invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise TaskDefJsonError("JSON must be an object")
    pid_raw = obj.get("process_id")
    if not isinstance(pid_raw, str) or not pid_raw.strip():
        raise TaskDefJsonError("process_id is required at top level")
    _normalize_org_meta(obj.get("org_meta") or {})  # raises if invalid
    return obj
