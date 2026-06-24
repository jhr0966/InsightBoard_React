"""Phase 6-B: cron 일일 수집 모듈 — UI 와 독립된 배치 진입점.

`scripts/daily_scrape.py` CLI 및 GH Actions workflow 가 사용. UI 의
`_run_collect` 와 동일한 search→save_articles 흐름을 평탄 함수로 재구성하되,
키워드 리스트(여러 개) × 소스 전체를 한 번에 처리하고 결과를 dict 로 반환한다.

핵심 설계 — 동일 소스의 키워드별 결과는 메모리에 누적한 뒤 소스당 한 번만
`save_articles` 를 호출한다. 파일명 stamp 가 초 단위라 같은 초 내 다중 호출 시
덮어쓰기가 발생할 수 있기 때문.

소스 표기는 내부 ID 기준: "naver", "google", "tech" (UI 한국어 라벨과 별개).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from scraping import enrich as _enrich
from scraping import google as google_news
from scraping import naver as naver_news
from scraping import tech_sites
from store.news_db import save_articles


SOURCE_IDS = ("naver", "google", "tech")
KEYWORD_SOURCES = ("naver", "google")  # tech 는 키워드와 무관, 1회만 실행


@dataclass
class CollectionReport:
    """배치 수집 결과 요약. CLI/workflow 로그용.

    saved: 소스당 1개 entry — {"source", "keywords", "count", "path"}.
    errors: 키워드/소스 단위 실패 — {"source", "keyword", "error"}.
    """

    saved: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    @property
    def total_articles(self) -> int:
        return sum(int(r.get("count", 0)) for r in self.saved)

    @property
    def total_files(self) -> int:
        return sum(1 for r in self.saved if r.get("path"))

    def summary_lines(self) -> list[str]:
        lines = [
            f"수집 완료: {self.total_articles}건 / {self.total_files}개 파일"
        ]
        for r in self.saved:
            kws = ", ".join(r.get("keywords") or []) or "-"
            lines.append(
                f"  · {r['source']:6s} [{kws}] {r['count']}건 → {r.get('path') or '저장 안 함'}"
            )
        for e in self.errors:
            kw = e.get("keyword") or "-"
            lines.append(f"  ✗ {e['source']:6s} [{kw}] 오류: {e['error']}")
        return lines


def _run_keyword_source(
    src: str, keyword: str, max_results: int
) -> list[dict]:
    if src == "naver":
        return naver_news.search(keyword, max_results=max_results)
    if src == "google":
        return google_news.search(keyword, max_results=max_results)
    raise ValueError(f"unsupported keyword source: {src}")


def collect_batch(
    keywords: Sequence[str],
    *,
    sources: Sequence[str] = SOURCE_IDS,
    max_results: int = 10,
    on_step: Callable[[str, str, int], None] | None = None,
    extra_feeds: Sequence[tuple[str, str]] | None = None,
    do_enrich: bool = True,
) -> CollectionReport:
    """키워드×소스 배치 수집 + 커스텀 RSS 피드.

    Args:
        keywords: 검색어 리스트. 비어 있으면 키워드 기반 소스는 스킵.
        sources: 사용 소스 ID — {"naver", "google", "tech"} 부분집합.
        max_results: 키워드/사이트 당 최대 기사 수.
        on_step: (source, keyword, found_count) 진행 콜백 (저장 직전이 아닌 검색 직후).
        extra_feeds: 커스텀 RSS 출처 — `(name, url)` 튜플 리스트. 키워드 무관하게
            한 번씩 fetch 한다. 빈 리스트/None 이면 스킵.

    Returns:
        CollectionReport — 소스당 1 entry, 실패는 errors 에 별도 누적.

    부수효과: `store.news_db.save_articles` 가 오늘자 디렉토리에 parquet 저장.
    """
    report = CollectionReport()
    selected = tuple(s for s in sources if s in SOURCE_IDS)
    keyword_list = [k.strip() for k in keywords if k and k.strip()]

    # 소스별 처리를 (saved, errors) 를 돌려주는 순수 클로저로 분리 — 공유 report 를
    # 직접 건드리지 않으므로 스레드에서 동시 실행해도 안전(파일명은 source 별로 달라
    # 동시 저장 충돌 없음). 결과는 제출 순서대로 병합해 결정적 순서를 보존한다.
    def _do_keyword_source(src: str) -> tuple[list[dict], list[dict]]:
        saved: list[dict] = []
        errors: list[dict] = []
        bucket: list[dict] = []
        used_keywords: list[str] = []
        for kw in keyword_list:
            try:
                articles = _run_keyword_source(src, kw, max_results)
                for art in articles:
                    art.setdefault("query", kw)
                bucket.extend(articles)
                used_keywords.append(kw)
                if on_step:
                    on_step(src, kw, len(articles))
            except Exception as e:  # noqa: BLE001 — 개별 실패 격리
                errors.append({"source": src, "keyword": kw, "error": str(e)})
        if bucket:
            if do_enrich:
                # 검색 결과는 content 가 비어 있다 → 링크에서 본문·og:image 를 병렬 fetch.
                _enrich.enrich_parallel(bucket, with_llm=False)
            path = save_articles(bucket, source=src)
            saved.append({
                "source": src, "keywords": used_keywords,
                "count": len(bucket), "path": str(path) if path else "",
            })
        return saved, errors

    def _do_tech() -> tuple[list[dict], list[dict]]:
        saved: list[dict] = []
        errors: list[dict] = []
        try:
            # 사이트별 HTTP 실패를 errors 로 표면화 → '수집 헬스' 가 감지.
            articles = tech_sites.search_all(
                max_results_per_site=max_results,
                on_error=lambda site, msg: errors.append(
                    {"source": "tech", "keyword": site, "error": msg}
                ),
                # 사이트별 진행 — 모달에 'AI Times'·'오토메이션월드'를 개별 표시.
                on_site=(lambda site, n: on_step("tech", site, n)) if on_step else None,
            )
            if do_enrich:
                _enrich.enrich_parallel(articles, with_llm=False)
            path = save_articles(articles, source="tech")
            # 사이트별 건수 — UI 가 press(사이트명) 기준으로 나눠 표시.
            sites: dict[str, int] = {}
            for art in articles:
                site = str(art.get("press", "") or "").strip()
                if site:
                    sites[site] = sites.get(site, 0) + 1
            saved.append({
                "source": "tech", "keywords": [], "count": len(articles),
                "path": str(path) if path else "", "sites": sites,
            })
        except Exception as e:  # noqa: BLE001
            errors.append({"source": "tech", "keyword": "", "error": str(e)})
        return saved, errors

    def _do_feed(name: str, url: str) -> tuple[list[dict], list[dict]]:
        saved: list[dict] = []
        errors: list[dict] = []
        from scraping import rss as _rss
        try:
            articles = _rss.fetch(url, source_name=name, max_results=max_results)
            if articles:
                if do_enrich:
                    _enrich.enrich_parallel(articles, with_llm=False)
                path = save_articles(articles, source=name)
                saved.append({
                    "source": name, "keywords": [], "count": len(articles),
                    "path": str(path) if path else "",
                })
            if on_step:
                on_step(name, "", len(articles))
        except Exception as e:  # noqa: BLE001
            errors.append({"source": name, "keyword": "", "error": str(e)})
        return saved, errors

    # 작업 목록 — 소스(naver/google/tech) + 커스텀 RSS 피드. 제출 순서 = 병합 순서.
    tasks: list[Callable[[], tuple[list[dict], list[dict]]]] = []
    for src in selected:
        if src in KEYWORD_SOURCES:
            tasks.append(lambda s=src: _do_keyword_source(s))
        elif src == "tech":
            tasks.append(_do_tech)
    for name, url in (extra_feeds or ()):
        tasks.append(lambda n=name, u=url: _do_feed(n, u))

    if not tasks:
        return report

    # 소스 동시 실행 — 각 소스는 검색+본문 enrich 가 네트워크 대기라, 순차로 돌면
    # naver 끝나야 google 시작했다. 동시에 돌려 전체 wall-clock 을 가장 느린 소스
    # 1개 수준으로 줄인다. future 를 제출 순서대로 result() 해 순서 결정성 유지.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as ex:
        futures = [ex.submit(fn) for fn in tasks]
        for fut in futures:
            saved, errors = fut.result()
            report.saved.extend(saved)
            report.errors.extend(errors)

    return report
