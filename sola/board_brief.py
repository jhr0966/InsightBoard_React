"""오늘의 보드 SOLA 브리핑 — 매칭 뉴스 N건을 '헤드라인 + 불릿 2~3개' 로 압축.

호출 캐시: 동일 (items 시그니처 · 부서 라벨 · 모델) 조합은 디스크 캐시 사용.
LLM 미설정·실패 시 graceful — 룰 기반 fallback 문장 반환.
"""
from __future__ import annotations

from typing import Sequence

from config import llm_model
from sola.client import LLMNotConfigured, chat
from sola.prompts import SYSTEM_BOARD_BRIEF
from store import cache


def _rule_based_fallback(items: Sequence[dict], persona_label: str) -> str:
    """LLM 미설정·실패 시 — 헤드라인 + 상위 2건 불릿 (LLM 출력과 동일 형식)."""
    n = len(items)
    if n == 0:
        return "오늘 매칭된 뉴스가 없습니다."
    label = persona_label or "내 관심사"
    lines = [f"{label} 기준 챙겨볼 뉴스 {n}건이 도착했어요."]
    for it in list(items)[:2]:
        title = str(it.get("title", "")).replace("\n", " ").strip()[:70]
        src = str(it.get("source_label", "") or it.get("source", "") or "").strip()
        if title:
            lines.append(f"- {title}" + (f" ({src})" if src else ""))
    return "\n".join(lines)


_SENTENCE_END = (".", "!", "?", "다", "요", "음", "함", "됨", "임", ")", "**", "…", "'", '"')


def _sanitize_brief(reply: str) -> str:
    """LLM 출력 정리 — 빈 줄 제거 + max_tokens 절단으로 끊긴 마지막 줄 드롭.

    화면에 "…생산자동화그룹은 이러한" 처럼 문장 중간에서 끊긴 텍스트가 그대로
    노출되던 문제 방어. 형식(헤드라인 + '- ' 불릿)은 렌더러가 해석한다.
    """
    lines = [ln.strip() for ln in (reply or "").splitlines() if ln.strip()]
    if len(lines) > 1:
        last = lines[-1].rstrip()
        if not last.endswith(_SENTENCE_END):
            lines = lines[:-1]
    return "\n".join(lines)


def _format_items(items: Sequence[dict]) -> str:
    if not items:
        return "(매칭 뉴스 없음)"
    lines: list[str] = []
    for i, it in enumerate(items, start=1):
        title = str(it.get("title", "")).replace("\n", " ").strip()[:140]
        # source_label(표시 라벨) 우선 — 내부 ID('tech')가 프롬프트/문장에 새지 않게.
        src = str(it.get("source_label", "") or it.get("source", "") or "").strip()
        summary = str(it.get("summary", "") or "").replace("\n", " ").strip()[:200]
        head = f"[{i}] {title}"
        if src:
            head += f" — {src}"
        lines.append(head + (f"\n    요지: {summary}" if summary else ""))
    return "\n".join(lines)


def _cache_signature(items: Sequence[dict], persona_label: str, task_context: str = "") -> str:
    """캐시 키 — 제목 + 출처 + persona 라벨 (+ 관심 작업정의 길이/해시).

    task_context 가 주입되면 다른 관심 공정의 페르소나가 같은 라벨이어도 다른
    브리핑을 받도록 시그니처에 포함한다(짧은 해시로 키 폭증 방지).
    """
    parts = []
    for it in items:
        t = str(it.get("title", "") or "")[:80]
        s = str(it.get("source", "") or "")[:40]
        parts.append(f"{t}@{s}")
    tc = ""
    if task_context:
        import hashlib
        tc = "#" + hashlib.md5(task_context.encode("utf-8")).hexdigest()[:8]  # noqa: S324 — 캐시 키용
    return f"{persona_label}{tc}|" + "||".join(parts)


def brief(
    items: Sequence[dict],
    persona_label: str = "",
    *,
    task_context: str = "",
    force: bool = False,
) -> str:
    """매칭 뉴스 items 를 LLM 1~2문장 평문으로 압축. 캐시 우선.

    Args:
        items: 각 element = {"title": str, "source": str, "when": str, "summary"?: str}.
        persona_label: 사용자 부서/직무 라벨 (예: "도장1팀 · 검사관"). 빈 문자열 OK.
        task_context: 페르소나 관심 공정 작업정의 블록(sola.task_context). 주입되면
            브리핑이 뉴스를 사용자 공정 맥락(작업흐름·품질리스크·자동화영역)에
            연결해 시사점을 낸다. 빈 문자열 OK.
        force: 캐시 무시.

    Returns:
        첫 줄 = 헤드라인, 이후 "- " 불릿 2~3줄의 멀티라인 평문.
        LLM 미설정·실패 시 같은 형식의 룰 기반 fallback.
    """
    if not items:
        return _rule_based_fallback(items, persona_label)

    sig = _cache_signature(items, persona_label, task_context)
    # v2: 형식이 '헤드라인+불릿' 으로 바뀜 — 구버전 1문장 캐시와 키 분리.
    key = cache.make_key("board_brief_v2", sig, llm_model() or "")
    if not force:
        hit = cache.get(key)
        if hit is not None:
            return hit

    user = (
        f"[부서] {persona_label or '(미설정)'}\n"
        f"[매칭 뉴스 {len(items)}건]\n{_format_items(items)}"
        + (f"\n\n{task_context}" if task_context else "")
    )
    try:
        reply = chat(
            messages=[
                {"role": "system", "content": SYSTEM_BOARD_BRIEF},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=400,
        )
    except LLMNotConfigured:
        return _rule_based_fallback(items, persona_label)
    except Exception:  # noqa: BLE001
        return _rule_based_fallback(items, persona_label)

    reply = _sanitize_brief((reply or "").strip())
    if not reply:
        return _rule_based_fallback(items, persona_label)
    cache.put(key, reply)
    return reply
