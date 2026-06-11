"""뉴스 소스 표기 단일화 — 내부 수집 ID ↔ 사용자 표시 라벨/분류/그라데이션.

저장 스키마는 그대로(기사 `source` = naver/google/tech/커스텀명, `press` = 매체명)
두고 **표시만** 여기서 환산한다. 소스가 보이는 모든 곳(수집 카드·수집잡·집계 표·
보드 카드·브리핑·채팅 컨텍스트·오류 소스)이 이 모듈을 거친다:

  - 키워드 뉴스(검색 기반): naver → "네이버 뉴스", google → "구글 뉴스"
  - 뉴스 포탈(사이트 피드): tech + press → "AI Times" / "오토메이션월드",
    press 없는 legacy tech → "뉴스 포탈" · 커스텀 RSS → 등록명 그대로
"""
from __future__ import annotations


# 키워드 검색 기반 수집 ID (그 외 source 값은 모두 '뉴스 포탈' 분류)
KEYWORD_SOURCE_IDS: frozenset[str] = frozenset({"naver", "google"})

# 내부 수집 ID → 표시 라벨
SOURCE_ID_LABELS: dict[str, str] = {"naver": "네이버 뉴스", "google": "구글 뉴스"}

# press 가 비어 있는 legacy tech 데이터의 폴백 라벨
PORTAL_FALLBACK_LABEL = "뉴스 포탈"

CATEGORY_LABELS: dict[str, str] = {"keyword": "키워드 뉴스", "portal": "뉴스 포탈"}


def category_of(source: str) -> str:
    """source 값 → 대분류('keyword'|'portal'). naver/google=키워드, 그 외=포탈."""
    return "keyword" if str(source or "").strip() in KEYWORD_SOURCE_IDS else "portal"


def source_label(source: str, press: str = "") -> str:
    """소스 표시 라벨 — 내부 ID 를 절대 노출하지 않는다.

    naver/google → 네이버 뉴스/구글 뉴스, tech → press(AI Times/오토메이션월드,
    없으면 '뉴스 포탈'), 커스텀 RSS → source 에 저장된 등록명 그대로.
    """
    s = str(source or "").strip()
    if s in SOURCE_ID_LABELS:
        return SOURCE_ID_LABELS[s]
    if s == "tech":
        return str(press or "").strip() or PORTAL_FALLBACK_LABEL
    return s or str(press or "").strip() or "기타"


# 표시 라벨 기준 그라데이션 (+ legacy 표시명·ID 별칭 — 과거 저장 데이터 호환)
_GRADIENT_NAVER = "linear-gradient(135deg,#6D28D9,#A78BFA)"
_GRADIENT_GOOGLE = "linear-gradient(135deg,#047857,#14B8A6)"
SOURCE_GRADIENTS: dict[str, str] = {
    "네이버 뉴스": _GRADIENT_NAVER,
    "구글 뉴스": _GRADIENT_GOOGLE,
    "AI Times": "linear-gradient(135deg,#DC2626,#F87171)",
    "오토메이션월드": "linear-gradient(135deg,#D97706,#F59E0B)",
    # legacy 별칭 — source 에 직접 저장된 옛 표시명/ID
    "네이버 기술": _GRADIENT_NAVER,
    "naver": _GRADIENT_NAVER,
    "Google RSS": _GRADIENT_GOOGLE,
    "google": _GRADIENT_GOOGLE,
    "automationworld": "linear-gradient(135deg,#D97706,#F59E0B)",
    "aitimes": "linear-gradient(135deg,#DC2626,#F87171)",
    "뉴스 포탈": "linear-gradient(135deg,#1D4ED8,#60A5FA)",
}
DEFAULT_GRADIENT = "linear-gradient(135deg,#475569,#94A3B8)"


def source_gradient(source: str, press: str = "") -> str:
    """소스 색 그라데이션 — 라벨 기준 조회(별칭 포함), 모르면 중성 회색."""
    return SOURCE_GRADIENTS.get(
        source_label(source, press),
        SOURCE_GRADIENTS.get(str(source or "").strip(), DEFAULT_GRADIENT),
    )
