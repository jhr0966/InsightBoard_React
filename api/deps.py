"""요청 컨텍스트 의존성 — 인증·테넌시 (Phase 1 no-op).

Phase 1: 단일 사용자라 항상 `local`/`default` 를 주입한다(인증 없음).
Phase 2: 이 함수 한 곳에서 토큰/세션을 검증해 실제 `user_id`/`workspace_id` 를
주입하면, 라우터·store 호출부는 손대지 않고 멀티유저로 전환된다.
"""
from __future__ import annotations

from dataclasses import dataclass

from store._audit import DEFAULT_USER, DEFAULT_WORKSPACE


@dataclass(frozen=True)
class Identity:
    """현재 요청의 행위 주체. Phase 2 에서 토큰으로부터 채워진다."""
    user_id: str
    workspace_id: str


def current_identity() -> Identity:
    """FastAPI 의존성 — 현재 요청의 Identity.

    Phase 1 no-op: 항상 기본 사용자/워크스페이스. 교체 지점은 여기 한 곳.
    """
    return Identity(user_id=DEFAULT_USER, workspace_id=DEFAULT_WORKSPACE)
