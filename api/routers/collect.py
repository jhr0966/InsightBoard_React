"""뉴스 수집 실행 API — `scraping.run_daily.collect_batch` 위임.

키워드×소스 배치 수집 → `store.news_db` parquet 저장. **라이브 네트워크 + (옵션)
LLM enrich** 이므로 동기·장시간일 수 있다.

서버리스(Vercel)에선 `scraping/` 이 번들에서 제외(.vercelignore)되고 쓰기 FS·네트워크
제약이 있어 사용 불가 → `scraping` 을 **지연 import** 해 앱 부팅은 깨지 않고, 호출 시
503 으로 안내한다. 실제 수집은 로컬/전용 백엔드에서 실행.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import Identity, current_identity

router = APIRouter(prefix="/api/collect", tags=["collect"])

# 스키마 기본값 — top-level 에서 scraping 을 import 하지 않기 위해 로컬 상수.
_DEFAULT_SOURCES = ("naver", "google", "tech")


class CollectIn(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    sources: list[str] | None = Field(default=None, description=f"부분집합 {_DEFAULT_SOURCES}")
    max_results: int = Field(default=10, ge=1, le=50)
    do_enrich: bool = True


@router.post("")
def run_collect(body: CollectIn, _identity: Identity = Depends(current_identity)) -> dict:
    try:
        from scraping.run_daily import SOURCE_IDS, collect_batch
    except ImportError as exc:  # 서버리스 등 scraping 미포함 환경
        raise HTTPException(
            status_code=503,
            detail="수집 기능을 사용할 수 없는 환경입니다(서버리스 등). 로컬/전용 백엔드에서 실행하세요.",
        ) from exc

    report = collect_batch(
        body.keywords,
        sources=body.sources if body.sources is not None else SOURCE_IDS,
        max_results=body.max_results,
        do_enrich=body.do_enrich,
    )
    return {
        "total_articles": report.total_articles,
        "total_files": report.total_files,
        "saved": report.saved,
        "errors": report.errors,
    }
