"""Phase 6-B: cron 일일 수집 CLI.

GH Actions workflow 또는 로컬에서 호출.

Usage:
    python -m scripts.daily_scrape                              # 기본 키워드 + 전체 소스
    python -m scripts.daily_scrape --keywords "용접 로봇" "디지털 트윈"
    python -m scripts.daily_scrape --sources naver google       # tech 제외
    python -m scripts.daily_scrape --max-results 20

Exit code: 항상 0 (네트워크 일시 오류로 cron 이 실패 처리되지 않도록).
오류는 stdout 으로 보고하되 saved 0 건이면 stderr 경고만 남긴다.
"""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from config import DEFAULT_DAILY_KEYWORDS, ensure_data_dirs
from scraping.run_daily import SOURCE_IDS, collect_batch


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="daily_scrape",
        description="조선소 도메인 키워드로 네이버/구글/테크 사이트 뉴스를 일일 수집·저장.",
    )
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=None,
        help=f"검색어 리스트. 미지정 시 config.DEFAULT_DAILY_KEYWORDS ({len(DEFAULT_DAILY_KEYWORDS)}개) 사용.",
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=SOURCE_IDS,
        default=list(SOURCE_IDS),
        help="사용 소스 ID — naver/google/tech 부분집합. 기본: 전체.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="키워드/사이트당 최대 기사 수. 기본 10.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    keywords = args.keywords if args.keywords else list(DEFAULT_DAILY_KEYWORDS)

    ensure_data_dirs()
    print(
        f"[daily_scrape] 시작 — 키워드 {len(keywords)}개, 소스 {args.sources}, max={args.max_results}",
        flush=True,
    )

    def _on_step(src: str, kw: str, n: int) -> None:
        label = f"{src}" + (f" [{kw}]" if kw else "")
        print(f"[daily_scrape]   · {label}: {n}건", flush=True)

    report = collect_batch(
        keywords,
        sources=tuple(args.sources),
        max_results=args.max_results,
        on_step=_on_step,
    )

    print("[daily_scrape] " + report.summary_lines()[0], flush=True)
    if report.total_articles == 0:
        print(
            "[daily_scrape] WARN: 저장된 기사가 0건입니다.",
            file=sys.stderr,
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
