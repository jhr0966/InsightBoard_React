"""기술 분류 체계(taxonomy) — 안정 ID·별칭(alias)·버전 관리 (개편 Step 7).

과거 히트맵은 기술 7종을 **문자열 하드코딩**(`insights.TECHS`)해 신규 기술·동의어
(비전 AI=머신비전=컴퓨터 비전)를 처리할 수 없었다. 이제:

- 기술은 **안정 ID**(`TECH-CV-001` 형식)로 식별 — 이름을 바꿔도 관계(links의
  technology_ids·사례·제안서 근거)는 유지된다.
- **alias** 로 동의어를 흡수: "비전 AI"·"머신비전" → 컴퓨터 비전.
- 시드는 코드 상수, **운영 편집은 `data/taxonomy/taxonomy.json`** 오버라이드
  (존재하면 우선). 관리 API/화면 확장은 Step 11(관리 메뉴) 몫.
- 규칙 변경 시 `TAXONOMY_VERSION` +1 — 파생 태깅(links.technology_ids) 재빌드 기준.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import config

logger = logging.getLogger(__name__)

TAXONOMY_VERSION = 1

# 시드 분류 — 조선소 AI·자동화 도메인. parent_id 는 향후 계층 확장용(현재 평면).
_SEED: list[dict] = [
    {"technology_id": "TECH-CV-001", "name": "컴퓨터 비전", "parent_id": "TECH-AI",
     "aliases": ["비전", "비전 AI", "머신비전", "외관검사", "결함탐지", "영상인식", "OCR", "3D 스캐닝"],
     "description": "카메라·스캐너 영상 기반 검사/인식/측정", "active": True},
    {"technology_id": "TECH-RB-001", "name": "로보틱스", "parent_id": None,
     "aliases": ["산업용 로봇", "협동 로봇", "협동로봇", "코봇", "용접 로봇", "도장 로봇", "매니퓰레이터", "오비탈 용접"],
     "description": "고정형 산업용·협동 로봇 자동화", "active": True},
    {"technology_id": "TECH-RB-002", "name": "자율이동로봇", "parent_id": "TECH-RB-001",
     "aliases": ["AGV", "AMR", "자율물류", "자율주행", "무인 운반", "트랜스포터"],
     "description": "AGV/AMR 등 이동형 물류 자동화", "active": True},
    {"technology_id": "TECH-PM-001", "name": "예지보전", "parent_id": None,
     "aliases": ["예지보전", "예측 정비", "상태 모니터링", "CBM", "진동 센서", "고장 예측"],
     "description": "설비 상태 기반 고장 예측·정비", "active": True},
    {"technology_id": "TECH-DT-001", "name": "디지털 트윈", "parent_id": None,
     "aliases": ["디지털 트윈", "디지털트윈", "공정 시뮬레이션", "가상 커미셔닝"],
     "description": "가상 모델 기반 공정·설비 시뮬레이션", "active": True},
    {"technology_id": "TECH-GA-001", "name": "생성형 AI", "parent_id": "TECH-AI",
     "aliases": ["생성형 AI", "생성AI", "LLM", "거대언어모델", "문서 자동화", "AI 에이전트", "지식검색", "챗봇"],
     "description": "LLM 기반 문서·지식·에이전트 자동화", "active": True},
    {"technology_id": "TECH-AI", "name": "AI/머신러닝", "parent_id": None,
     "aliases": ["AI", "인공지능", "머신러닝", "딥러닝", "기계학습"],
     "description": "범용 AI·기계학습(하위: 비전·생성형)", "active": True},
    {"technology_id": "TECH-WD-001", "name": "웨어러블", "parent_id": None,
     "aliases": ["외골격", "웨어러블 로봇", "스마트 글래스", "AR 글래스", "AR", "증강현실"],
     "description": "작업자 보조 웨어러블·AR", "active": True},
    {"technology_id": "TECH-IO-001", "name": "IoT/스마트센서", "parent_id": None,
     "aliases": ["IoT", "스마트센서", "스마트 센서", "가스감지", "무선 센서"],
     "description": "센서·사물인터넷 기반 모니터링", "active": True},
    {"technology_id": "TECH-DP-001", "name": "데이터 플랫폼", "parent_id": None,
     "aliases": ["MES", "ERP", "빅데이터", "APS", "스마트팩토리", "스마트 팩토리", "데이터 플랫폼"],
     "description": "생산 데이터·계획 시스템", "active": True},
]

_REQUIRED_KEYS = {"technology_id", "name", "aliases"}


def _override_path() -> Path:
    return config.DATA_ROOT / "taxonomy" / "taxonomy.json"


def load() -> list[dict]:
    """taxonomy 항목 목록 — 오버라이드 파일이 있으면 우선, 없으면 시드.

    오버라이드가 깨져 있으면(스키마 누락 등) 시드로 폴백 — 분류가 비면 히트맵·태깅이
    전부 죽으므로 안전 우선.
    """
    p = _override_path()
    if p.exists():
        try:
            items = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(items, dict):
                items = items.get("technologies", [])
            ok = [it for it in items
                  if isinstance(it, dict) and _REQUIRED_KEYS <= set(it)]
            if ok:
                return ok
            logger.warning("taxonomy 오버라이드에 유효 항목이 없음 — 시드 사용")
        except (json.JSONDecodeError, OSError):
            logger.warning("taxonomy 오버라이드 파싱 실패 — 시드 사용", exc_info=True)
    return [dict(it) for it in _SEED]


def active() -> list[dict]:
    return [t for t in load() if t.get("active", True)]


def get(tech_id: str) -> dict | None:
    for t in load():
        if t["technology_id"] == tech_id:
            return t
    return None


def heatmap_columns() -> list[dict]:
    """히트맵 열 — active 기술의 (technology_id, name). 표시 순서 = 정의 순서."""
    return [{"technology_id": t["technology_id"], "name": t["name"]} for t in active()]


def _terms(t: dict) -> list[str]:
    return [str(t.get("name", ""))] + [str(a) for a in (t.get("aliases") or [])]


def tag_text(text: str) -> list[str]:
    """텍스트에 등장하는 기술의 technology_id 목록 (이름+alias substring, 대소문자 무시).

    links(technology_ids)·사례 태깅·히트맵 카운트가 공용으로 쓴다 — 문자열이 아닌
    **ID** 를 저장해 이름 변경에도 관계가 유지된다(계획 §10).
    """
    tx = (text or "").lower()
    if not tx:
        return []
    out: list[str] = []
    for t in active():
        if any(term.lower() in tx for term in _terms(t) if term):
            out.append(t["technology_id"])
    return out


def mentions(text: str, tech_id: str) -> bool:
    """텍스트가 특정 기술(이름 또는 alias)을 언급하는지 — 히트맵 셀 카운트용."""
    t = get(tech_id)
    if not t:
        return False
    tx = (text or "").lower()
    return any(term.lower() in tx for term in _terms(t) if term)


def id_by_name(name: str) -> str | None:
    """표시 이름 → technology_id (히트맵 셀 클릭의 col 파라미터 역해석)."""
    for t in load():
        if t["name"] == name:
            return t["technology_id"]
    return None
