"""사용자 페르소나(부서·직무·관심사) 데이터 모델."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


# 자유 입력 관심 키워드 구분자 — 쉼표 / 세미콜론 / 엔터 / 가운뎃점.
_KW_SPLIT_RE = re.compile(r"[,;\n·]+")

# 관심 키워드 최대 보관 수 (수집 쿼리 폭주 방지).
MAX_INTEREST_KEYWORDS = 20


def parse_keywords_input(text: str) -> list[str]:
    """자유 입력 문자열 → 관심 키워드 리스트 (쉼표/엔터 구분, 중복·공백 제거).

    온보딩 마법사와 프로필 설정 페이지가 공유하는 단일 파서.
    """
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in _KW_SPLIT_RE.split(text):
        kw = raw.strip()
        if kw and kw not in seen:
            seen.add(kw)
            out.append(kw)
    return out[:MAX_INTEREST_KEYWORDS]


@dataclass
class Persona:
    """단일 사용자 가정. 멀티유저는 별도 PR.

    - team/dept 는 로드맵 엑셀에서 선택지 제공
    - job 은 자유 입력 (용접 담당, 절단 담당, 검사관 등)
    - interest_lv3 / interest_tasks 는 멀티선택
    - interest_keywords 는 사용자가 자유 입력한 관심 키워드 (쉼표/엔터 구분).
      수집 키워드와 보드 ⑦ 키워드 관리에 합류한다.
    - muted_keywords 는 자동 추출(top_keywords) 결과에서 사용자가 × 로 숨긴
      키워드 목록. 다음 렌더부터 해당 키워드는 자동 추출에서 제외된다.
    - derived_* 는 SOLA(LLM) 가 입력 항목에서 추출·매칭한 산출물 (persona/derive.py).
      derived_interests = 관심 키워드/주제 5~10개,
      matched_processes = [{"process": lv3, "tasks": [...], "score": float}],
      derived_at = 마지막 분석 시각 (ISO),
      derived_source = 'llm' | 'cache' | 'fallback' (LLM 미설정 폴백 구분).
    """
    name: str = ""
    team: str = ""
    dept: str = ""
    job: str = ""
    interest_lv3: list[str] = field(default_factory=list)
    interest_tasks: list[str] = field(default_factory=list)
    interest_keywords: list[str] = field(default_factory=list)
    muted_keywords: list[str] = field(default_factory=list)
    derived_interests: list[str] = field(default_factory=list)
    matched_processes: list[dict] = field(default_factory=list)
    derived_at: str = ""
    derived_source: str = ""

    def is_set(self) -> bool:
        return bool(self.dept or self.job or self.team)

    def label(self) -> str:
        parts = [p for p in (self.dept, self.job) if p]
        return " · ".join(parts) if parts else "(미설정)"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Persona":
        """저장 JSON → Persona. 구버전 JSON(신규 키 없음)도 기본값으로 로드 (하위호환)."""
        return cls(
            name=str(data.get("name", "")),
            team=str(data.get("team", "")),
            dept=str(data.get("dept", "")),
            job=str(data.get("job", "")),
            interest_lv3=list(data.get("interest_lv3", []) or []),
            interest_tasks=list(data.get("interest_tasks", []) or []),
            interest_keywords=list(data.get("interest_keywords", []) or []),
            muted_keywords=list(data.get("muted_keywords", []) or []),
            derived_interests=list(data.get("derived_interests", []) or []),
            matched_processes=[
                m for m in (data.get("matched_processes", []) or []) if isinstance(m, dict)
            ],
            derived_at=str(data.get("derived_at", "") or ""),
            derived_source=str(data.get("derived_source", "") or ""),
        )
