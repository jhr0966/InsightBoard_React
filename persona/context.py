"""페르소나 → LLM 시스템 프롬프트 컨텍스트 블록 생성."""
from __future__ import annotations

from persona.schema import Persona


def system_block(persona: Persona) -> str:
    """SOLA 채팅·제안서·요약에 붙여 쓸 페르소나 안내 블록."""
    if not persona.is_set():
        return ""

    lines = ["--- 사용자 페르소나 ---"]
    if persona.name:
        lines.append(f"- 이름: {persona.name}")
    if persona.team:
        lines.append(f"- 팀: {persona.team}")
    if persona.dept:
        lines.append(f"- 부서: {persona.dept}")
    if persona.job:
        lines.append(f"- 직무: {persona.job}")
    if persona.interest_lv3:
        lines.append(f"- 관심 공정(Lv3): {', '.join(persona.interest_lv3)}")
    if persona.interest_tasks:
        lines.append(f"- 관심 작업: {', '.join(persona.interest_tasks[:10])}")
    if persona.interest_keywords:
        lines.append(f"- 관심 키워드: {', '.join(persona.interest_keywords[:10])}")
    if persona.derived_interests:
        lines.append(f"- SOLA 분석 관심사: {', '.join(persona.derived_interests[:10])}")
    if persona.matched_processes:
        tops = [
            str(m.get("process", "")) for m in persona.matched_processes[:3]
            if m.get("process")
        ]
        if tops:
            lines.append(f"- 연관 공정(분석): {', '.join(tops)}")
    lines.append("")
    lines.append("이 사용자의 직무·부서 관점에서 답변하세요. 관련 없는 일반론은 줄이고 적용 시사점 위주로.")
    return "\n" + "\n".join(lines)
