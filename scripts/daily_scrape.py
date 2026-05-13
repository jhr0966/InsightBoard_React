"""Phase 6-B: cron 일일 수집 CLI.

GH Actions workflow 또는 로컬에서 호출.

Usage:
    python -m scripts.daily_scrape                              # 기본 키워드 + 전체 소스 + enrich 30건
    python -m scripts.daily_scrape --keywords "용접 로봇" "디지털 트윈"
    python -m scripts.daily_scrape --sources naver google       # tech 제외
    python -m scripts.daily_scrape --max-results 20
    python -m scripts.daily_scrape --enrich-max 0               # enrich 비활성
    python -m scripts.daily_scrape --enrich-max 50 --no-llm     # 본문 fetch 만, LLM 미사용

Exit code: 항상 0 (네트워크 일시 오류로 cron 이 실패 처리되지 않도록).
오류는 stdout 으로 보고하되 saved 0 건이면 stderr 경고만 남긴다.
"""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from config import DEFAULT_DAILY_KEYWORDS, ensure_data_dirs
from scraping.run_daily import SOURCE_IDS, collect_batch

DEFAULT_ENRICH_MAX = 30


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="daily_scrape",
        description="조선소 도메인 키워드로 네이버/구글/테크 사이트 뉴스를 일일 수집·enrich·저장.",
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
        "--enrich-max",
        type=int,
        default=DEFAULT_ENRICH_MAX,
        help=f"수집 직후 본문 enrich 할 최대 기사 수 (cron 1회당 LLM 호출 상한 보호). "
        f"0 이면 enrich 단계 스킵. 기본 {DEFAULT_ENRICH_MAX}.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="enrich 시 LLM(키워드·요약) 호출을 끄고 본문 fetch 만 수행.",
    )
    return parser.parse_args(argv)


def _run_enrich(*, max_n: int, with_llm: bool) -> None:
    """수집 직후 호출 — 오늘자 디렉토리에서 content 부족 기사 N건 enrich + upsert.

    실패는 격리: enrich 자체가 raise 해도 cron 전체는 영향 없음 (caller 가 catch).
    """
    from scraping import enrich as enrich_mod
    from store.news_db import load_all_today, upsert_articles

    df = load_all_today()
    if df.empty:
        print("[daily_scrape] enrich: 오늘 수집된 기사 없음, 스킵.", flush=True)
        return

    need = df[df["content"].astype(str).str.len() < 50] if "content" in df.columns else df
    target = need.head(max_n).to_dict(orient="records")
    if not target:
        print("[daily_scrape] enrich: 모든 기사가 이미 본문 확보됨, 스킵.", flush=True)
        return

    print(
        f"[daily_scrape] enrich 시작 — {len(target)}건 (LLM {'사용' if with_llm else '미사용'})",
        flush=True,
    )

    def _cb(done: int, total: int, _art: dict) -> None:
        if done == total or done % 10 == 0:
            print(f"[daily_scrape]   · enrich {done}/{total}", flush=True)

    enriched = enrich_mod.enrich_articles(target, with_llm=with_llm, progress_cb=_cb)

    by_src: dict[str, list[dict]] = {}
    for art in enriched:
        by_src.setdefault(art.get("source", "naver"), []).append(art)
    for src, items in by_src.items():
        upsert_articles(items, source=src)

    enriched_cnt = sum(1 for a in enriched if a.get("content"))
    print(
        f"[daily_scrape] enrich 완료 — 본문 확보 {enriched_cnt}/{len(enriched)}건",
        flush=True,
    )


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

    if args.enrich_max > 0 and report.total_articles > 0:
        try:
            _run_enrich(max_n=args.enrich_max, with_llm=not args.no_llm)
        except Exception as e:  # noqa: BLE001 — cron 전체를 죽이지 않음
            print(
                f"[daily_scrape] enrich 실패(격리): {type(e).__name__}: {e}",
                file=sys.stderr,
                flush=True,
            )
    elif args.enrich_max == 0:
        print("[daily_scrape] enrich 단계 스킵 (--enrich-max 0).", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
