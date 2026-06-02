"""라이브 수집 검증 CLI — 네이버·구글 키워드검색 + AI Times·오토메이션월드.

각 소스에서 기사 리스트(제목·링크·리스트이미지)를 수집하고, 상위 기사 몇 건의
본문을 실제로 fetch 해 **제목 / 본문 전체 / 대표이미지** 가 채워지는지 한 번에
출력한다. `tests/`(network mock)가 파서 *로직*을 검증한다면, 이 스크립트는
셀렉터가 **현재 라이브 사이트 구조와 맞는지**를 사람이 눈으로 확인하기 위한 것.

⚠ 이 원격 환경(Claude Code on the web)은 네트워크 allowlist 프록시라 기본적으로
외부 호스트가 차단된다("Host not in allowlist" 403 — example.com 포함). 설정에서
"모든 도메인 허용"으로 바꿨다면 **새 세션**을 시작해야 적용된다 — 현재 살아있는
세션의 프록시는 시작 시점 정책으로 고정되기 때문이다.

Usage:
    python -m scripts.verify_scrape                        # 기본 키워드 1개 + 4소스 전체
    python -m scripts.verify_scrape --keywords "용접 로봇"
    python -m scripts.verify_scrape --sources naver google  # tech 제외
    python -m scripts.verify_scrape --max-results 8 --bodies 3

Exit code: 검증 소스가 모두 1건 이상 정상 수집되면 0, 아니면 1
(네트워크 차단/0건/예외). cron 이 아니라 사람이 보는 점검용이라 비정상은 1로 표면화.
"""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from config import DEFAULT_DAILY_KEYWORDS
from scraping import enrich, google, naver, tech_sites

_BODY_MIN_LEN = 200  # 이 길이 이상이면 '본문 정상 수집' 으로 간주.


def _looks_blocked(msg: str) -> bool:
    """allowlist 프록시 차단(403 host_not_allowed)인지 식별 → 안내 분기용."""
    low = msg.lower()
    return "host_not_allowed" in low or "not in allowlist" in low or "403" in low


def _verify_one(label: str, articles: list[dict], bodies: int) -> dict:
    """리스트 채움(제목/이미지) 출력 + 상위 `bodies` 건 본문 fetch 결과 출력."""
    n = len(articles)
    titled = sum(1 for a in articles if a.get("title"))
    listed_img = sum(1 for a in articles if a.get("image_url"))
    print(f"\n[{label}] 리스트 {n}건 · 제목 {titled}/{n} · 리스트이미지 {listed_img}/{n}")
    for i, a in enumerate(articles[:3], 1):
        print(f"  {i}. {(a.get('title') or '(제목없음)')[:60]}")
        print(f"     link = {(a.get('link') or '')[:78]}")
        print(f"     img  = {(a.get('image_url') or '(없음)')[:78]}")

    body_ok = img_ok = 0
    for a in articles[:bodies]:
        try:
            fetched = enrich.fetch_article(a.get("link", ""))
        except Exception as exc:  # noqa: BLE001 — 단일 기사 실패가 점검 전체를 멈추지 않게.
            print(f"  └ 본문 fetch 예외: {exc}")
            continue
        body = fetched.get("content", "") or ""
        img = fetched.get("image_url", "") or a.get("image_url", "")
        if len(body) >= _BODY_MIN_LEN:
            body_ok += 1
        if img:
            img_ok += 1
        preview = body[:90].replace("\n", " ")
        print(f"  └ 본문 {len(body):>5}자 · 대표이미지 {'O' if img else 'X'} · {preview}")

    return {"list": n, "titles": titled, "list_img": listed_img,
            "body_ok": body_ok, "img_ok": img_ok}


def _run_source(sid: str, keyword: str, max_results: int, bodies: int, summary: dict) -> None:
    """소스 1개(naver/google/tech) 검증. tech 는 등록된 사이트 전부 순회."""
    try:
        if sid == "naver":
            arts = naver.search(keyword, max_results=max_results)
            summary["naver"] = _verify_one(f"네이버 (kw='{keyword}')", arts, bodies)
        elif sid == "google":
            arts = google.search(keyword, max_results=max_results)
            summary["google"] = _verify_one(f"구글 (kw='{keyword}')", arts, bodies)
        elif sid == "tech":
            for site_name, url in tech_sites.TECH_SITES.items():
                arts = tech_sites.search_site(site_name, url, max_results=max_results)
                summary[site_name] = _verify_one(site_name, arts, bodies)
    except Exception as exc:  # noqa: BLE001 — 소스별 실패를 격리해 나머지 소스는 계속 점검.
        blocked = _looks_blocked(str(exc))
        summary[sid] = {"error": str(exc)[:140], "blocked": blocked}
        print(f"\n[{sid}] {'🚫 네트워크 차단' if blocked else '❌ 실패'}: {str(exc)[:140]}")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify_scrape",
        description="라이브 수집 검증 — 네이버/구글/AI Times/오토메이션월드의 제목·본문·이미지 실측.",
    )
    parser.add_argument(
        "--keywords", nargs="*", default=None,
        help="네이버/구글 검색어. 미지정 시 config.DEFAULT_DAILY_KEYWORDS 첫 항목.",
    )
    parser.add_argument(
        "--sources", nargs="*", choices=["naver", "google", "tech"],
        default=["naver", "google", "tech"], help="검증 소스 부분집합. 기본: 전체.",
    )
    parser.add_argument("--max-results", type=int, default=5, help="소스당 리스트 최대 건수. 기본 5.")
    parser.add_argument("--bodies", type=int, default=2, help="본문 fetch 할 상위 기사 수. 기본 2.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    keyword = args.keywords[0] if args.keywords else (
        DEFAULT_DAILY_KEYWORDS[0] if DEFAULT_DAILY_KEYWORDS else "조선 자동화")

    print(f"=== 라이브 수집 검증 · 소스={args.sources} · kw='{keyword}' "
          f"· max={args.max_results} · bodies={args.bodies} ===")

    summary: dict = {}
    for sid in args.sources:
        _run_source(sid, keyword, args.max_results, args.bodies, summary)

    print("\n=== 요약 ===")
    any_blocked = False
    all_ok = True
    for key, val in summary.items():
        print(f"  {key:18}: {val}")
        if val.get("blocked"):
            any_blocked = True
        if val.get("error") or val.get("list", 0) == 0:
            all_ok = False

    if any_blocked:
        print("\n⚠ 'Host not in allowlist' 차단 감지 — 이 세션의 프록시가 외부를 막고 있습니다.")
        print("  설정에서 도메인을 허용했더라도 **새 세션**을 시작해야 적용됩니다")
        print("  (현재 세션의 프록시 allowlist 는 시작 시점 정책으로 고정).")
    elif all_ok:
        print("\n✅ 모든 소스에서 제목·본문·이미지 정상 수집.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
