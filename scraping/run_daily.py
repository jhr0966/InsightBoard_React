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
) -> CollectionReport:
    """키워드×소스 배치 수집.

    Args:
        keywords: 검색어 리스트. 비어 있으면 키워드 기반 소스는 스킵.
        sources: 사용 소스 ID — {"naver", "google", "tech"} 부분집합.
        max_results: 키워드/사이트 당 최대 기사 수.
        on_step: (source, keyword, found_count) 진행 콜백 (저장 직전이 아닌 검색 직후).

    Returns:
        CollectionReport — 소스당 1 entry, 실패는 errors 에 별도 누적.

    부수효과: `store.news_db.save_articles` 가 오늘자 디렉토리에 parquet 저장.
    """
    report = CollectionReport()
    selected = tuple(s for s in sources if s in SOURCE_IDS)
    keyword_list = [k.strip() for k in keywords if k and k.strip()]

    for src in selected:
        if src in KEYWORD_SOURCES:
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
                    report.errors.append(
                        {"source": src, "keyword": kw, "error": str(e)}
                    )
            if bucket:
                path = save_articles(bucket, source=src)
                report.saved.append(
                    {
                        "source": src,
                        "keywords": used_keywords,
                        "count": len(bucket),
                        "path": str(path) if path else "",
                    }
                )
        elif src == "tech":
            try:
                articles = tech_sites.search_all(max_results_per_site=max_results)
                path = save_articles(articles, source="tech")
                report.saved.append(
                    {
                        "source": "tech",
                        "keywords": [],
                        "count": len(articles),
                        "path": str(path) if path else "",
                    }
                )
                if on_step:
                    on_step("tech", "", len(articles))
            except Exception as e:  # noqa: BLE001
                report.errors.append(
                    {"source": "tech", "keyword": "", "error": str(e)}
                )
    return report
