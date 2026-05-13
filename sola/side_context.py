"""사이드 채팅 패널용 시스템 메시지 조립 (순수 함수).

`ui/layout.py:render_chat_panel` 에서 호출.

배치 순서 (가장 우선이 위):
  1. base 시스템 프롬프트 (SYSTEM_CHAT 등)
  2. 페르소나 안내
  3. 현재 화면 컨텍스트
  4. 직전 작성 제안서 (있으면)
  5. 이전 사이클에서 채택된 제안서 N건 (제목·메모만)

`max_chars` 초과 시 뒷부분부터 자른다 (앞 컨텍스트가 더 중요하다는 가정).
"""
from __future__ import annotations

from typing import Iterable, TYPE_CHECKING

from persona import context as persona_ctx
from persona.schema import Persona

if TYPE_CHECKING:
    from store.bookmarks import Bookmark


DEFAULT_MAX_CHARS = 8000
PROPOSAL_HEAD_CHARS = 3000


def build_side_system(
    *,
    base_system: str,
    persona: Persona | None = None,
    page_context: str = "",
    session_proposal: str | None = None,
    adopted_proposals: "Iterable[Bookmark] | None" = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[str, list[str]]:
    """사이드 채팅 시스템 메시지 + 첨부 라벨 리스트 반환.

    Returns:
        (full_system_message, attached_labels)
        attached_labels 는 패널 헤더 UI 에 "📎 페르소나 · 현재 화면 · 채택 제안서 3건"
        형태로 노출해 사용자가 어떤 컨텍스트가 들어갔는지 인지하게 한다.
    """
    parts: list[str] = [base_system]
    labels: list[str] = []

    if persona is not None:
        block = persona_ctx.system_block(persona)
        if block:
            parts.append(block)
            if persona.is_set():
                labels.append(f"페르소나·{persona.dept or '-'}")

    if page_context.strip():
        parts.append(
            "\n\n--- 현재 화면 컨텍스트 ---\n"
            + page_context.strip()
            + "\n--- /화면 ---"
        )
        labels.append("현재 화면")

    if session_proposal and session_proposal.strip():
        prop = session_proposal.strip()[:PROPOSAL_HEAD_CHARS]
        parts.append(
            "\n\n--- 직전 작성 제안서 ---\n"
            + prop
            + "\n--- /제안서 ---"
        )
        labels.append("직전 제안서")

    if adopted_proposals:
        adopted_list = list(adopted_proposals)
        if adopted_list:
            lines = ["\n\n--- 이전 사이클에서 채택된 제안서 ---"]
            for b in adopted_list:
                head = f"- {b.title}"
                if b.decided_at:
                    head += f" (채택: {b.decided_at[:10]})"
                lines.append(head)
                if b.decision_note:
                    lines.append(f"    메모: {b.decision_note}")
            lines.append("--- /채택 ---")
            parts.append("\n".join(lines))
            labels.append(f"채택 제안서 {len(adopted_list)}건")

    full = "".join(parts)
    if len(full) > max_chars:
        full = full[:max_chars] + "\n...[컨텍스트 길이 제한으로 잘림]"
    return full, labels
