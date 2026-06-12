"""데이터 관리 — 순수 프레젠테이션 헬퍼 (부작용 없음).

#133 뉴스 수집 재설계 이후, 옛 필터 폼·3탭/그룹 라우팅·옛 카드 빌더는 모두 제거됐다
(카드 브라우저·기사 모달·설정 서브뷰가 대체). 지금 남은 것은 **기사 나이 라벨**뿐 —
출처색 그라데이션·라벨은 `ui.news_sources` 로 단일화됐다.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _news_age_label(when: str) -> str:
    """ISO 시각 → '3시간 전' / '어제' / '5월 17일'. 카드·표·모달 메타에 노출."""
    if not when:
        return ""
    try:
        ts = when.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "방금"
        if secs < 3600:
            return f"{secs // 60}분 전"
        if secs < 86400:
            return f"{secs // 3600}시간 전"
        if secs < 172800:
            return "어제"
        if secs < 86400 * 30:
            return f"{secs // 86400}일 전"
        return f"{dt.month}월 {dt.day}일"
    except Exception:
        return ""
