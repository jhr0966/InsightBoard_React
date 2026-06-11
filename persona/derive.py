"""페르소나 입력 → SOLA(LLM) 관심사 추출 + 작업정의(task_defs_db) 토큰 매칭.

흐름 (온보딩 완료 / 프로필 저장 / "다시 분석" 버튼에서 호출):
  1. `extract_interests(persona)` — 프로필 텍스트를 LLM 에 보내 관심사 키워드
     5~10개 추출. `store.cache` 로 캐시(같은 프로필이면 재호출 없음).
     LLM 미설정(`LLMNotConfigured`)·네트워크 오류 시 **규칙 폴백** — 입력
     항목(관심 키워드·작업·공정·직무·부서)의 토큰을 그대로 사용.
  2. `match_task_defs(interests)` — 추출 키워드를 작업정의 토큰과 매칭해
     연관 공정(lv3)별 작업 추천 목록 생성.
  3. `derive_and_store(persona)` — 1+2 실행 후 persona 의
     `derived_interests` / `matched_processes` / `derived_at` 갱신·영구 저장.

CLAUDE.md 규칙: LLM 호출은 `sola.client` 경유 단일 진입.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from persona.schema import Persona


# store.match 와 동일 철학의 경량 토크나이저 (한글/영문/숫자 2자+, 잡음 제외).
_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_NOISE = {"작업", "공정", "기술", "관련", "통해", "대한", "위한", "그리고", "또는",
          "담당", "엔지니어", "관리", "업무"}

MAX_INTERESTS = 10
MIN_INTERESTS = 5  # LLM 프롬프트 상 목표치 — 폴백은 있는 만큼만.
MAX_MATCHED_PROCESSES = 8
MAX_TASKS_PER_PROCESS = 5


def _tokens(text: str) -> list[str]:
    return [w for w in _TOKEN_RE.findall((text or "").lower()) if w not in _NOISE]


def profile_text(persona: Persona) -> str:
    """LLM 입력·캐시 키에 쓰는 프로필 평탄 텍스트 (사용자 입력 항목만)."""
    lines: list[str] = []
    if persona.dept:
        lines.append(f"부서: {persona.dept}")
    if persona.team:
        lines.append(f"팀: {persona.team}")
    if persona.job:
        lines.append(f"직무: {persona.job}")
    if persona.interest_lv3:
        lines.append("관심 공정: " + ", ".join(persona.interest_lv3))
    if persona.interest_tasks:
        lines.append("관심 작업: " + ", ".join(persona.interest_tasks))
    if persona.interest_keywords:
        lines.append("관심 키워드: " + ", ".join(persona.interest_keywords))
    return "\n".join(lines)


def _parse_llm_keywords(raw: str) -> list[str]:
    """LLM 응답(콤마 구분 한 줄 기대) → 키워드 리스트. 잡음 라인·중복 방어."""
    out: list[str] = []
    seen: set[str] = set()
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for part in re.split(r"[,;·]+", line):
            kw = part.strip().strip("-•*\"'` ").strip()
            if not kw or len(kw) > 40:
                continue
            if kw not in seen:
                seen.add(kw)
                out.append(kw)
    return out[:MAX_INTERESTS]


def _call_llm(text: str) -> str:
    """sola.client 경유 단일 LLM 호출 — 테스트에서 이 함수를 patch 한다."""
    from sola import client as sola_client
    from sola.prompts import SYSTEM_PERSONA_INTERESTS

    return sola_client.chat(
        [
            {"role": "system", "content": SYSTEM_PERSONA_INTERESTS},
            {"role": "user", "content": f"[사용자 프로필]\n{text}"},
        ],
        temperature=0.2,
        max_tokens=200,
    )


def fallback_interests(persona: Persona) -> list[str]:
    """규칙 폴백 — 입력 항목의 토큰/구문을 그대로 관심사로 사용 (LLM 불요).

    우선순위: 관심 키워드(원문) → 관심 작업 → 관심 공정 → 직무·부서 토큰.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        v = (value or "").strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)

    for kw in persona.interest_keywords:
        _add(kw)
    for kw in persona.interest_tasks:
        _add(kw)
    for kw in persona.interest_lv3:
        _add(kw)
    for tok in _tokens(f"{persona.job} {persona.dept}"):
        _add(tok)
    return out[:MAX_INTERESTS]


def extract_interests(
    persona: Persona, *, use_cache: bool = True
) -> tuple[list[str], str]:
    """프로필 → 관심사 키워드 5~10개.

    Returns:
        (키워드 리스트, source) — source ∈ {"llm", "cache", "fallback"}.
        프로필이 비면 ([], "fallback").
    """
    text = profile_text(persona)
    if not text.strip():
        return [], "fallback"

    from store import cache as sola_cache

    cache_key = sola_cache.make_key("persona_interests_v1", text)
    if use_cache:
        cached = sola_cache.get(cache_key)
        if cached is not None:
            parsed = _parse_llm_keywords(cached)
            if parsed:
                return parsed, "cache"

    try:
        raw = _call_llm(text)
        parsed = _parse_llm_keywords(raw)
        if parsed:
            sola_cache.put(cache_key, ", ".join(parsed))
            return parsed, "llm"
    except Exception:  # noqa: BLE001 — LLMNotConfigured·타임아웃·네트워크 모두 폴백
        pass
    return fallback_interests(persona), "fallback"


# ── 작업정의 매칭 ────────────────────────────────────────────

def _row_text(row: dict) -> str:
    """task_defs_db row → 매칭용 평탄 텍스트 (scalar + task_def_text)."""
    parts = [
        str(row.get("process") or ""),
        str(row.get("task") or ""),
        str(row.get("division") or ""),
        str(row.get("task_def_text") or ""),
    ]
    return " ".join(p for p in parts if p)


def _kw_hits(kw_tokens: list[str], row_tokens: set[str]) -> int:
    """관심 키워드 토큰 vs 작업 토큰 — 부분 포함(복합어) 허용 매칭 수."""
    hits = 0
    for kt in kw_tokens:
        if kt in row_tokens:
            hits += 1
            continue
        if any(kt in rt or rt in kt for rt in row_tokens):
            hits += 1
    return hits


def match_task_defs(interests: list[str]) -> list[dict]:
    """추출 관심사 ↔ 작업정의(task_defs_db.list_all) 토큰 매칭.

    Returns:
        [{"process": lv3 공정명, "tasks": [작업명...], "score": float,
          "matched": [매칭된 관심사...]}] — score 내림차순 상위
        `MAX_MATCHED_PROCESSES` 개.
    """
    if not interests:
        return []
    from store import task_defs_db

    try:
        rows = task_defs_db.list_all()
    except Exception:  # noqa: BLE001 — DB 미생성 등은 빈 추천
        return []
    if not rows:
        return []

    kw_token_map = {kw: _tokens(kw) for kw in interests}
    agg: dict[str, dict] = {}
    for row in rows:
        process = str(row.get("process") or "").strip() or "(공정 미지정)"
        task = str(row.get("task") or "").strip()
        row_tokens = set(_tokens(_row_text(row)))
        if not row_tokens:
            continue
        row_score = 0.0
        row_matched: list[str] = []
        for kw, kts in kw_token_map.items():
            if not kts:
                continue
            hits = _kw_hits(kts, row_tokens)
            if hits:
                row_score += hits / len(kts)  # 키워드 토큰 커버리지 비율
                row_matched.append(kw)
        if row_score <= 0:
            continue
        slot = agg.setdefault(
            process, {"process": process, "tasks": [], "score": 0.0, "matched": []}
        )
        slot["score"] += row_score
        if task and task not in slot["tasks"]:
            slot["tasks"].append(task)
        for kw in row_matched:
            if kw not in slot["matched"]:
                slot["matched"].append(kw)

    ranked = sorted(agg.values(), key=lambda s: s["score"], reverse=True)
    out: list[dict] = []
    for slot in ranked[:MAX_MATCHED_PROCESSES]:
        out.append({
            "process": slot["process"],
            "tasks": slot["tasks"][:MAX_TASKS_PER_PROCESS],
            "score": round(float(slot["score"]), 2),
            "matched": slot["matched"],
        })
    return out


# ── 통합 진입점 ──────────────────────────────────────────────

def derive_and_store(persona: Persona, *, force: bool = False) -> Persona:
    """관심사 추출 + 작업정의 매칭 → persona derived 필드 갱신·영구 저장.

    Args:
        force: True 면 캐시 무시(다시 분석 버튼).

    Returns: 갱신된 persona (실패해도 기존 derived 유지한 persona 반환).
    """
    from persona import store as persona_store

    try:
        interests, source = extract_interests(persona, use_cache=not force)
        persona.derived_interests = interests
        persona.matched_processes = match_task_defs(interests)
        persona.derived_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        persona.derived_source = source
        persona_store.save(persona)
    except Exception:  # noqa: BLE001 — 분석 실패가 프로필 저장 흐름을 깨면 안 됨
        pass
    return persona
