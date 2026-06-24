"""페르소나 관심 작업정의를 LLM 컨텍스트로 선별·주입 (과부하 방지 budget cap).

배경: 작업정의(task_defs_db)는 수십~수백 건이라 전부 LLM 컨텍스트에 넣으면
과부하·비용 폭증·정확도 저하가 일어난다. 그래서 **먼저 좁힌다**:

  1. 페르소나의 `matched_processes`(persona/derive.py 가 LLM·룰로 산출한 관심 공정·
     작업) 를 선별기로 사용 → 상위 N 공정만.
  2. 그 공정의 작업정의 row 만 task_defs_db 에서 조회.
  3. `roadmap.task_def_json.to_chat_context_lines` 로 핵심 신호(설명·작업흐름·품질
     리스크·자동화영역·안전·장비·공정연결)만 평탄화.
  4. 공정 수·작업 수·총 글자수를 캡(cap)으로 제한.

특정 작업을 사용자가 언급하면 `mentioned_task_context` 로 그 작업정의만 주입한다
(채팅에서 "절단 공정 자동화 어떻게?" → 절단 작업정의 주입).

제안서·인사이트·채팅이 모두 이 단일 모듈을 경유해 일관된 선별/포맷/캡을 공유한다.
"""
from __future__ import annotations

from persona.schema import Persona
from roadmap import task_def_json as tdj


# 과부하 방지 기본 캡 — 호출처(제안서/채팅/인사이트)가 필요시 조정.
DEFAULT_MAX_PROCESSES = 3
DEFAULT_MAX_TASKS_PER_PROCESS = 2
DEFAULT_MAX_CHARS = 2500
MENTION_LIMIT = 3


def _rows_for_process(process: str, limit: int) -> list[dict]:
    """단일 공정명(org_meta.process 미러 컬럼) → 작업정의 row 리스트."""
    from store import task_defs_db

    try:
        return task_defs_db.list_all(process=process, limit=limit)
    except Exception:  # noqa: BLE001 — DB 미생성 등은 빈 결과
        return []


def relevant_processes(persona: Persona, *, max_processes: int = DEFAULT_MAX_PROCESSES) -> list[str]:
    """페르소나 → 관심 공정명 리스트 (matched_processes 우선, interest_lv3 폴백).

    matched_processes 는 persona/derive.py 가 관심사↔작업정의 매칭으로 만든
    `[{"process": lv3, "tasks": [...], "score": ...}]`. 점수순으로 이미 정렬돼 있다.
    분석 전(비어있음)이면 사용자가 직접 고른 interest_lv3 로 폴백한다.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(name: object) -> None:
        p = str(name or "").strip()
        if p and p not in seen and p != "(공정 미지정)":
            seen.add(p)
            out.append(p)

    for m in (persona.matched_processes or []):
        if len(out) >= max_processes:
            break
        if isinstance(m, dict):
            _add(m.get("process"))
    if not out:
        for p in (persona.interest_lv3 or []):
            if len(out) >= max_processes:
                break
            _add(p)
    return out[:max_processes]


def relevant_task_rows(
    persona: Persona,
    *,
    max_processes: int = DEFAULT_MAX_PROCESSES,
    max_tasks_per_process: int = DEFAULT_MAX_TASKS_PER_PROCESS,
) -> list[dict]:
    """페르소나 관심 공정 → 작업정의 row 리스트 (process_id 중복 제거, 캡)."""
    rows: list[dict] = []
    seen: set[str] = set()
    for process in relevant_processes(persona, max_processes=max_processes):
        for row in _rows_for_process(process, max_tasks_per_process):
            pid = str(row.get("process_id") or "")
            if pid and pid in seen:
                continue
            if pid:
                seen.add(pid)
            rows.append(row)
    return rows


def resolve_mentioned_task_rows(query: str, *, limit: int = MENTION_LIMIT) -> list[dict]:
    """사용자 질의에서 '언급된' 작업정의 row.

    자연어 문장에 작업/공정 이름(또는 process_id)이 등장하면 그 작업으로 본다.
    예) "절단 공정 자동화 어떻게?" → '절단' 작업정의. LIKE 전체구문 검색은 문장
    매칭이 안 되므로(예: "%절단 공정 자동화 어떻게?%"), 알려진 이름이 질의에
    포함되는지를 역으로 확인한다. 더 구체적인(긴) 이름 매칭을 우선한다.
    """
    from store import task_defs_db

    q = (query or "").strip().lower()
    if not q:
        return []
    try:
        rows = task_defs_db.list_all()
    except Exception:  # noqa: BLE001
        return []
    scored: list[tuple[int, dict]] = []
    for row in rows:
        names = [str(row.get("task") or ""), str(row.get("process") or ""),
                 str(row.get("process_id") or "")]
        jo = row.get("json_obj")
        if isinstance(jo, dict):
            names.append(str(jo.get("process_name") or ""))
        best = 0
        for name in names:
            name = name.strip()
            if len(name) >= 2 and name.lower() in q:
                best = max(best, len(name))
        if best:
            scored.append((best, row))
    scored.sort(key=lambda t: t[0], reverse=True)  # 긴 이름(더 구체적) 우선
    return [row for _, row in scored[:limit]]


def _row_json_text(row: dict) -> str:
    """row 에서 작업정의 JSON 원본 텍스트 추출.

    task_defs_db row 는 'json'(원본 텍스트) 보유. roadmap.query 매핑은
    'task_def_json' 키를 쓰므로 둘 다 본다.
    """
    return str(row.get("json") or row.get("task_def_json") or "")


def format_rows(
    rows: list[dict],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    header: str = "관련 작업 정의",
) -> tuple[str, list[str]]:
    """작업정의 row 리스트 → (LLM 컨텍스트 블록 문자열, 작업명 라벨 리스트).

    각 row 의 JSON 을 파싱해 to_chat_context_lines 로 핵심 신호만 평탄화. 빈
    정의는 건너뛴다. 총 길이 초과 시 뒤를 잘라 과부하를 막는다. 주입할 내용이
    없으면 ("", []).
    """
    if not rows:
        return "", []
    blocks: list[str] = []
    labels: list[str] = []
    for row in rows:
        td = tdj.parse(_row_json_text(row))
        if td.is_empty():
            continue
        lines = tdj.to_chat_context_lines(td)
        if not lines:
            continue
        name = td.process_name or str(row.get("task") or "") or td.process_id
        blocks.append("\n".join(lines))
        if name:
            labels.append(name)
    if not blocks:
        return "", []
    body = f"--- {header} ---\n" + "\n\n".join(blocks) + "\n--- /작업 정의 ---"
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "\n…[작업정의 컨텍스트 길이 제한으로 일부 생략]"
    return body, labels


def persona_task_context(
    persona: Persona,
    *,
    max_processes: int = DEFAULT_MAX_PROCESSES,
    max_tasks_per_process: int = DEFAULT_MAX_TASKS_PER_PROCESS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[str, list[str]]:
    """페르소나 관심 공정의 작업정의 컨텍스트 — (블록, 라벨). 관심 공정 없으면 ("", [])."""
    rows = relevant_task_rows(
        persona,
        max_processes=max_processes,
        max_tasks_per_process=max_tasks_per_process,
    )
    return format_rows(rows, max_chars=max_chars, header="내 관심 공정 작업 정의")


def mentioned_task_context(
    query: str,
    *,
    limit: int = MENTION_LIMIT,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[str, list[str]]:
    """사용자 질의에서 언급된 작업정의 컨텍스트 — (블록, 라벨). 매칭 없으면 ("", [])."""
    rows = resolve_mentioned_task_rows(query, limit=limit)
    return format_rows(rows, max_chars=max_chars, header="언급된 작업 정의")
