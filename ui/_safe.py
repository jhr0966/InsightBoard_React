"""UI best-effort 가드 — broad except 의 silent 실패를 로깅으로 표면화.

개선 백로그 #3. v2 화면들은 "렌더가 데이터 실패로 깨지지 않게" 거의 모든 데이터
연산을 `try/except: pass` 로 감싸는데, 이게 진짜 오류(LLM 다운·깨진 parquet·계약
위반)를 **무신호**로 삼켜 '무데이터'와 '코드 깨짐'을 구분 못 하게 한다.

`guard(label)` 컨텍스트매니저로 감싸면 예외는 그대로 삼키되(렌더 계속) WARN 로그를
남겨 관측 가능하게 만든다 — UX 변화 없이 blind spot 만 제거.

    today = None
    with guard("데이터 관리 오늘자 로드"):
        today = news_db.load_all_today()
    # 실패해도 today 는 None, 그리고 로그에 스택트레이스가 남는다.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger("ui")


@contextmanager
def guard(label: str, *, level: int = logging.WARNING) -> Iterator[None]:
    """best-effort 블록 — 예외를 삼키고(렌더 계속) `label` 과 함께 로깅한다."""
    try:
        yield
    except Exception:  # noqa: BLE001 — 의도적 best-effort; 로깅으로 표면화
        logger.log(level, "[guard] %s 실패", label, exc_info=True)
