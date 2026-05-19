"""LLM 미설정 시 입력 컨텍스트 미리보기.

각 LLM 호출 지점에서 `LLMNotConfigured` 가 발생하면, 빈 에러 메시지 대신
실제 LLM 로 전달될 messages 를 사용자에게 그대로 노출한다. 운영자가 키를
세팅하기 전에 "어떤 컨텍스트가 전달될지" 확인할 수 있도록 돕는다.
"""
from __future__ import annotations


_ROLE_LABELS = {
    "system": "🧭 system",
    "user": "🙋 user",
    "assistant": "🤖 assistant",
}


def format_messages_preview(
    messages: list[dict],
    *,
    header: str | None = None,
    footer_hint: bool = True,
) -> str:
    """LLM 입력 messages 를 사람이 읽을 수 있는 마크다운 블록으로.

    - `header`: 미리보기 상단에 1줄 안내 (없으면 기본 안내).
    - `footer_hint`: True 면 ".env 의 LLM_API_KEY 를 채우면 실제 응답으로 대체된다" 안내 추가.

    출력은 `st.markdown` 으로 그대로 렌더링 가능하며 코드블록(```text```)
    안에 본문을 넣어 들여쓰기·줄바꿈을 보존한다.
    """
    head = header or "⚠️ LLM 미설정 — 호출 시 전달될 입력 컨텍스트 미리보기"
    parts: list[str] = [f"**{head}**", ""]
    for i, msg in enumerate(messages, start=1):
        role = str(msg.get("role", "?"))
        content = str(msg.get("content", "") or "")
        label = _ROLE_LABELS.get(role, role)
        parts.append(f"#### [{i}] {label}")
        parts.append("")
        parts.append("```text")
        parts.append(content)
        parts.append("```")
        parts.append("")
    if footer_hint:
        parts.append("---")
        parts.append("")
        parts.append(
            "> 💡 `.env` 의 `LLM_API_KEY` 를 채우면 위 컨텍스트가 실제 LLM 응답으로 대체됩니다."
        )
    return "\n".join(parts).rstrip() + "\n"
