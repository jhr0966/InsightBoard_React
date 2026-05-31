"""오늘의 보드 SOLA 브리핑 — 매칭 뉴스 N건을 LLM이 1~2문장으로 압축.

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
    """LLM 미설정·실패 시. 단순 평문 — 이전 동작 그대로."""
    n = len(items)
    if n == 0:
        return "오늘 매칭된 뉴스가 없습니다."
    label = persona_label or "오늘"
    return f"{label} 기준 매칭된 뉴스 {n}건이 두드러집니다."


def _format_items(items: Sequence[dict]) -> str:
    if not items:
        return "(매칭 뉴스 없음)"
    lines: list[str] = []
    for i, it in enumerate(items, start=1):
        title = str(it.get("title", "")).replace("\n", " ").strip()[:140]
        src = str(it.get("source", "") or "").strip()
        summary = str(it.get("summary", "") or "").replace("\n", " ").strip()[:200]
        head = f"[{i}] {title}"
        if src:
            head += f" — {src}"
        lines.append(head + (f"\n    요지: {summary}" if summary else ""))
    return "\n".join(lines)


def _cache_signature(items: Sequence[dict], persona_label: str) -> str:
    """캐시 키 — 제목 + 출처 + persona 라벨."""
    parts = []
    for it in items:
        t = str(it.get("title", "") or "")[:80]
        s = str(it.get("source", "") or "")[:40]
        parts.append(f"{t}@{s}")
    return f"{persona_label}|" + "||".join(parts)


def brief(items: Sequence[dict], persona_label: str = "", *, force: bool = False) -> str:
    """매칭 뉴스 items 를 LLM 1~2문장 평문으로 압축. 캐시 우선.

    Args:
        items: 각 element = {"title": str, "source": str, "when": str, "summary"?: str}.
        persona_label: 사용자 부서/직무 라벨 (예: "도장1팀 · 검사관"). 빈 문자열 OK.
        force: 캐시 무시.

    Returns:
        1~2문장 평문. LLM 미설정·실패 시 룰 기반 fallback.
    """
    if not items:
        return _rule_based_fallback(items, persona_label)

    sig = _cache_signature(items, persona_label)
    key = cache.make_key("board_brief", sig, llm_model() or "")
    if not force:
        hit = cache.get(key)
        if hit is not None:
            return hit

    user = (
        f"[부서] {persona_label or '(미설정)'}\n"
        f"[매칭 뉴스 {len(items)}건]\n{_format_items(items)}"
    )
    try:
        reply = chat(
            messages=[
                {"role": "system", "content": SYSTEM_BOARD_BRIEF},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=220,
        )
    except LLMNotConfigured:
        return _rule_based_fallback(items, persona_label)
    except Exception:  # noqa: BLE001
        return _rule_based_fallback(items, persona_label)

    reply = (reply or "").strip()
    if not reply:
        return _rule_based_fallback(items, persona_label)
    cache.put(key, reply)
    return reply
