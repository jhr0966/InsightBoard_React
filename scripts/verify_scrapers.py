"""라이브 스크래퍼 수집 검증 CLI — 제목 / 요약 / 썸네일 + 본문 전체 / 대표 이미지.

네이버·구글 키워드 검색 + AI Times·오토메이션월드 메인에서 **실제 수집**을 돌려
각 기사가 제목·본문·이미지를 제대로 채우는지 콘솔로 확인한다. (네트워크 필요)

실행:
    python -m scripts.verify_scrapers
    python -m scripts.verify_scrapers --keywords "스마트 조선소" --n 3

⚠ 이 저장소의 원격 실행 환경 네트워크 정책이 allowlist 프록시면 외부 사이트가
`403 "Host not in allowlist"` 로 막혀 전 소스 0건이 나온다. 그땐 환경의 네트워크
정책을 개방형으로 바꾼 뒤 다시 실행한다 (https://code.claude.com/docs/en/claude-code-on-the-web).
"""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from scraping import enrich, google, naver, tech_sites


def _show(label: str, articles: list[dict], n: int) -> None:
    print(f"\n===== {label}: {len(articles)} 건 =====")
    for a in articles[:n]:
        print(f"  title  : {(a.get('title') or '')[:74]}")
        print(f"  link   : {(a.get('link') or '')[:96]}")
        print(f"  summary: {(a.get('summary') or '')[:80] or '(없음)'}")
        print(f"  image  : {(a.get('image_url') or '')[:96] or '(없음)'}")
        print("  ---")


def _verify_enrich(label: str, articles: list[dict]) -> None:
    """각 소스 첫 기사로 본문 전체 + 대표 이미지 fetch 검증."""
    if not articles:
        print(f"\n[{label}] 수집 0건 — 본문/이미지 enrich 스킵")
        return
    art = articles[0]
    fetched = enrich.fetch_article(art.get("link", ""))
    body = fetched.get("content") or ""
    img = fetched.get("image_url") or ""
    print(f"\n[{label}] {(art.get('title') or '')[:50]}")
    print(f"  본문 길이 : {len(body)} 자")
    print(f"  본문 앞부분: {body[:200]!r}")
    print(f"  대표 이미지: {img[:100] or '(없음)'}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_scrapers", description="라이브 스크래퍼 수집 검증")
    parser.add_argument("--keywords", nargs="*", default=["스마트 조선소"],
                        help="네이버/구글 검색어 (첫 번째 사용, 기본 '스마트 조선소').")
    parser.add_argument("--n", type=int, default=3, help="소스별 표시/검증 건수 (기본 3).")
    args = parser.parse_args(argv)
    kw = (args.keywords or ["스마트 조선소"])[0]

    sources = (
        (f"네이버 '{kw}'", lambda: naver.search(kw, max_results=args.n)),
        (f"구글 '{kw}'", lambda: google.search(kw, max_results=args.n)),
        ("AI Times", lambda: tech_sites.search_site(
            "AI Times", tech_sites.TECH_SITES["AI Times"], max_results=args.n)),
        ("오토메이션월드", lambda: tech_sites.search_site(
            "오토메이션월드", tech_sites.TECH_SITES["오토메이션월드"], max_results=args.n)),
    )

    results: dict[str, list[dict]] = {}
    for label, fn in sources:
        try:
            results[label] = fn()
            _show(label, results[label], args.n)
        except Exception as e:  # noqa: BLE001 — 소스별 실패 격리
            print(f"\n[{label}] 오류: {type(e).__name__}: {e}")
            results[label] = []

    print("\n\n########## 본문/이미지 enrich (각 소스 첫 기사) ##########")
    for label, arts in results.items():
        try:
            _verify_enrich(label, arts)
        except Exception as e:  # noqa: BLE001
            print(f"\n[{label}] enrich 오류: {type(e).__name__}: {e}")

    print("\n\n########## 요약 ##########")
    any_collected = False
    for label, arts in results.items():
        n = len(arts)
        any_collected = any_collected or n > 0
        with_img = sum(1 for a in arts if (a.get("image_url") or "").strip())
        print(f"  {label:24s}: 수집 {n}건 · 썸네일 {with_img}/{n}")
    if not any_collected:
        print("\n⚠ 전 소스 0건 — 네트워크 차단(allowlist) 가능성. "
              "403 'Host not in allowlist' 면 환경 네트워크 정책을 개방형으로 바꾼 뒤 재실행.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
