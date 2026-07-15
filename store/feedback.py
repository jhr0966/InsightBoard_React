"""사용자 행동 피드백 이벤트 (개편 Step 9, 계획 §12) — repository seam(I-8) 경유.

이벤트: impression(노출) / open(열람) / save(저장) / dismiss(관련 없음) /
case_open(사례 열람, Step 12) / proposal_created(과제화, Step 13).

원칙:
- "관련 없음"은 UI 숨김이 아니라 **이벤트로 저장** → 랭킹에서 제외되고,
  향후 랭킹 평가(노출됐지만 무시 vs 노출 안 됨 구분)의 원자료가 된다.
- 이벤트에는 `ranking_version` 을 기록 — 어느 랭킹이 노출시킨 기사인지 추적.
- 식별 필드는 `store._audit.stamp` 표준(I-7) — 멀티유저(Step 10) 시 자동 격리.
"""
from __future__ import annotations

from store._audit import DEFAULT_USER, DEFAULT_WORKSPACE, now_iso, stamp
from store.repository import get_repository

ACTIONS = ("impression", "open", "save", "dismiss", "case_open", "proposal_created")

# 이벤트 무한 증가 방지 — impression 이 대부분이라 최근 N건만 유지(평가엔 충분).
_MAX_KEEP = 5000
_TRIM_AT = 8000

_repo = lambda: get_repository("feedback", id_key="id")  # noqa: E731


def record_events(
    events: list[dict], *, user: str = DEFAULT_USER, workspace: str = DEFAULT_WORKSPACE,
) -> int:
    """이벤트 배치 기록. 잘못된 action_type 은 ValueError(라우터가 422 변환)."""
    repo = _repo()
    rows = repo.read_all()
    n = 0
    ts = now_iso()
    for i, ev in enumerate(events):
        action = str(ev.get("action_type", ""))
        if action not in ACTIONS:
            raise ValueError(f"unknown action_type: {action}")
        rec = stamp({
            "id": f"fb-{ts}-{len(rows) + i}",
            "action_type": action,
            "article_id": str(ev.get("article_id", "") or ""),
            "process_id": str(ev.get("process_id", "") or ""),
            "context": str(ev.get("context", "") or ""),
            "ranking_version": int(ev.get("ranking_version", 0) or 0),
        }, user=user, workspace=workspace)
        rows.append(rec)
        n += 1
    if len(rows) > _TRIM_AT:
        rows = rows[-_MAX_KEEP:]
    repo.write_all(rows)
    return n


def dismissed_article_ids(
    *, user: str = DEFAULT_USER, workspace: str = DEFAULT_WORKSPACE,
) -> set[str]:
    """사용자가 '관련 없음' 처리한 기사 — 개인화 랭킹 제외 목록."""
    return {
        str(r.get("article_id", ""))
        for r in _repo().list(user_id=user, workspace_id=workspace)
        if r.get("action_type") == "dismiss" and r.get("article_id")
    }


def summary(*, user: str | None = None) -> dict:
    """액션별 카운트 — 관리 화면·랭킹 평가용."""
    rows = _repo().list(user_id=user) if user else _repo().read_all()
    counts: dict[str, int] = {}
    for r in rows:
        a = str(r.get("action_type", "?"))
        counts[a] = counts.get(a, 0) + 1
    return {"total": len(rows), "by_action": counts}
