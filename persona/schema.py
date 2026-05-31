"""사용자 페르소나(부서·직무·관심사) 데이터 모델."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Persona:
    """단일 사용자 가정. 멀티유저는 별도 PR.

    - team/dept 는 로드맵 엑셀에서 선택지 제공
    - job 은 자유 입력 (용접 담당, 절단 담당, 검사관 등)
    - interest_lv3 / interest_tasks 는 멀티선택
    - muted_keywords 는 자동 추출(top_keywords) 결과에서 사용자가 × 로 숨긴
      키워드 목록. 다음 렌더부터 해당 키워드는 자동 추출에서 제외된다.
    """
    name: str = ""
    team: str = ""
    dept: str = ""
    job: str = ""
    interest_lv3: list[str] = field(default_factory=list)
    interest_tasks: list[str] = field(default_factory=list)
    muted_keywords: list[str] = field(default_factory=list)

    def is_set(self) -> bool:
        return bool(self.dept or self.job or self.team)

    def label(self) -> str:
        parts = [p for p in (self.dept, self.job) if p]
        return " · ".join(parts) if parts else "(미설정)"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Persona":
        return cls(
            name=str(data.get("name", "")),
            team=str(data.get("team", "")),
            dept=str(data.get("dept", "")),
            job=str(data.get("job", "")),
            interest_lv3=list(data.get("interest_lv3", []) or []),
            interest_tasks=list(data.get("interest_tasks", []) or []),
            muted_keywords=list(data.get("muted_keywords", []) or []),
        )
