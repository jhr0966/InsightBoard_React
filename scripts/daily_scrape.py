"""Phase 6-B: cron 일일 수집 CLI.

GH Actions workflow 또는 로컬에서 호출.

Usage:
    python -m scripts.daily_scrape                              # 기본 키워드 + 전체 소스 + 등록된 커스텀 RSS
    python -m scripts.daily_scrape --keywords "용접 로봇" "디지털 트윈"
    python -m scripts.daily_scrape --sources naver google       # tech 제외
    python -m scripts.daily_scrape --max-results 20
    python -m scripts.daily_scrape --skip-custom-rss            # 커스텀 RSS 스킵

Exit code: 기본 0 (네트워크 일시 오류로 cron 이 실패 처리되지 않도록).
  `--fail-on-empty` 지정 시 저장 0건이면 exit 1 — cron 의 조용한 starvation 을
  GitHub Actions 가 빨갛게 표면화(scrape-daily.yml 이 이 플래그를 켠다).
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
        description=(
            "조선소 도메인 키워드로 네이버/구글/테크 사이트 + "
            "등록된 커스텀 RSS 출처에서 뉴스를 일일 수집·저장."
        ),
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
    parser.add_argument(
        "--skip-custom-rss",
        action="store_true",
        help="store.sources 에 등록된 커스텀 RSS 출처 수집을 건너뜁니다.",
    )
    parser.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="저장된 기사가 0건이면 exit 1 (cron 무신호 starvation 을 GitHub 가 빨갛게 표면화). "
             "기본은 항상 exit 0 (일시 오류로 cron 이 실패 처리되지 않게).",
    )
    return parser.parse_args(argv)


def _load_extra_feeds() -> list[tuple[str, str]]:
    """`store.sources.custom_sources()` → `(name, url)` 튜플. 실패 시 빈 리스트."""
    try:
        from store import sources as src_store
        return [(c.name, c.url) for c in src_store.custom_sources()]
    except Exception as exc:  # noqa: BLE001
        print(f"[daily_scrape] WARN: custom_sources 로드 실패: {exc}",
              file=sys.stderr, flush=True)
        return []


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    keywords = args.keywords if args.keywords else list(DEFAULT_DAILY_KEYWORDS)

    ensure_data_dirs()

    extra_feeds = [] if args.skip_custom_rss else _load_extra_feeds()
    print(
        f"[daily_scrape] 시작 — 키워드 {len(keywords)}개, 소스 {args.sources}, "
        f"max={args.max_results}, 커스텀 RSS {len(extra_feeds)}건",
        flush=True,
    )

    def _on_step(src: str, kw: str, n: int) -> None:
        label = f"{src}" + (f" [{kw}]" if kw else "")
        print(f"[daily_scrape]   · {label}: {n}건", flush=True)

    import time

    _t0 = time.monotonic()
    report = collect_batch(
        keywords,
        sources=tuple(args.sources),
        max_results=args.max_results,
        on_step=_on_step,
        extra_feeds=extra_feeds or None,
    )
    _duration = time.monotonic() - _t0

    # 런 로그 기록 — 데이터 관리 '수집 헬스' 가 읽는다. 로깅 실패가 cron 을 깨면 안 됨.
    try:
        from store import run_log
        entry = run_log.record_run(report, trigger="cron", duration_s=_duration)
        print(f"[daily_scrape] 런 기록됨: {entry['run_id']} · ok={entry['ok']}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[daily_scrape] WARN: 런 로그 기록 실패: {exc}",
              file=sys.stderr, flush=True)

    print("[daily_scrape] " + report.summary_lines()[0], flush=True)
    if report.errors:
        print(f"[daily_scrape] 일부 오류 {len(report.errors)}건 — 첫 오류: "
              f"{report.errors[0].get('source','?')} / "
              f"{report.errors[0].get('error','')}", flush=True)
    if report.total_articles == 0:
        print(
            "[daily_scrape] WARN: 저장된 기사가 0건입니다.",
            file=sys.stderr,
            flush=True,
        )
        if args.fail_on_empty:
            # 0건은 보통 '조용한 날'이 아니라 수집 파손(차단/셀렉터) → 신호로 실패 처리.
            print("[daily_scrape] --fail-on-empty: 0건이므로 exit 1.",
                  file=sys.stderr, flush=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
