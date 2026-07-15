"""요청 컨텍스트 의존성 — 식별·테넌시 (개편 Step 10: 경량 사용자 식별).

⚠ **X-User-Id 는 인증이 아니다** (계획 §13). 이 헤더는 다음 전제에서만 신뢰한다:
  - 신뢰된 내부 프록시(사내 게이트웨이)가 사용자 검증 후 헤더를 주입하고,
  - 외부 클라이언트가 임의로 헤더를 설정할 수 없는 네트워크 구성일 때.
  개발 환경에서는 직접 헤더를 넣어 다중 사용자를 시뮬레이션할 수 있다.

실서비스 전환(SSO/토큰)은 **이 파일 한 곳**만 교체한다: 토큰 검증 →
user_id/workspace_id/role 추출 → Identity 주입. 라우터·store 는 이미
Identity 를 관통하므로 손대지 않는다.

헤더 미제공 시 기본값(`local`/`default`) — 단일 사용자 파일럿과 100% 호환.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Header

from store._audit import DEFAULT_USER, DEFAULT_WORKSPACE

# 파일명·저장 키로 쓰이므로 슬러그만 허용 (디렉토리 traversal·이상 문자 차단).
_ID_RE = re.compile(r"[^a-zA-Z0-9._-]")
_DOTS_RE = re.compile(r"\.{2,}")  # ".." 연속 점 방어 (파일명 위생)
_ID_MAX = 64


def _sanitize(raw: str | None, default: str) -> str:
    s = _ID_RE.sub("", (raw or "").strip())
    s = _DOTS_RE.sub(".", s).strip(".")[:_ID_MAX]
    return s or default


@dataclass(frozen=True)
class Identity:
    """현재 요청의 행위 주체."""
    user_id: str
    workspace_id: str


def current_identity(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> Identity:
    """FastAPI 의존성 — 현재 요청의 Identity.

    X-User-Id/X-Workspace-Id 헤더(신뢰 프록시 주입 전제)를 슬러그로 정제해 사용.
    미제공 시 단일 사용자 기본값. SSO 교체 지점은 이 함수 한 곳.
    """
    return Identity(
        user_id=_sanitize(x_user_id, DEFAULT_USER),
        workspace_id=_sanitize(x_workspace_id, DEFAULT_WORKSPACE),
    )
