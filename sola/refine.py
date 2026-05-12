"""제안서 공동편집 — 현재 MD + 사용자 지시 → 수정된 MD."""
from __future__ import annotations

from persona import context as persona_ctx
from persona.schema import Persona
from sola.client import chat
from sola.prompts import SYSTEM_PROPOSAL_REFINE


def refine_proposal(
    current_md: str,
    instruction: str,
    *,
    persona: Persona | None = None,
    temperature: float = 0.3,
) -> str:
    """현재 제안서 MD 를 사용자 지시에 맞게 수정해 새 MD 를 반환.

    - current_md: 활성 제안서 (보통 [작업장] 좌측 패널의 그대로의 MD).
    - instruction: "리스크 섹션을 강화해", "더 짧게 요약", "보수적 톤으로" 등.
    - persona: 사용자 페르소나 (있으면 시스템 프롬프트에 자동 주입).

    프롬프트 규칙상 출력은 완성된 제안서 전체 MD 만 와야 한다. 호출자는
    이를 그대로 작업장 활성 MD 로 교체하면 된다.
    """
    persona_block = persona_ctx.system_block(persona) if persona else ""
    user = (
        "## [현재 제안서]\n"
        f"{current_md.strip()}\n\n"
        "## [수정 지시]\n"
        f"{instruction.strip()}"
    )
    return chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROPOSAL_REFINE + persona_block},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
