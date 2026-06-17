"""뉴스 수집 실행 API — `scraping.run_daily.collect_batch` 위임.

키워드×소스 배치 수집 → `store.news_db` parquet 저장. **라이브 네트워크 + (옵션)
LLM enrich** 이므로 동기·장시간일 수 있다.

서버리스(Vercel)에선 `scraping/` 이 번들에서 제외(.vercelignore)되고 쓰기 FS·네트워크
제약이 있어 사용 불가 → `scraping` 을 **지연 import** 해 앱 부팅은 깨지 않고, 호출 시
503 으로 안내한다. 실제 수집은 로컬/전용 백엔드에서 실행.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.deps import Identity, current_identity

router = APIRouter(prefix="/api/collect", tags=["collect"])
# 스키마 기본값 — top-level 에서 scraping 을 import 하지 않기 위해 로컬 상수.
_DEFAULT_SOURCES = ("naver", "google", "tech")


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


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


@router.post("/stream")
def run_collect_stream(body: CollectIn, _identity: Identity = Depends(current_identity)) -> StreamingResponse:
    """수집 실행 — SSE 진행 스트림. collect_batch 를 백그라운드 스레드에서 돌리며
    `on_step`(source·keyword·found) 이벤트를 흘리고, 완료 시 결과 요약을 보낸다.

    프레임 type: start | step | ping(keep-alive) | done | error. SSE 가 연결을
    살려둬 무료 호스팅의 프록시 idle 타임아웃(동기 수집의 'failed to fetch' 행)도 완화.
    """
    try:
        from scraping.run_daily import SOURCE_IDS, collect_batch
    except ImportError as exc:  # 서버리스 등 scraping 미포함 환경
        raise HTTPException(
            status_code=503,
            detail="수집 기능을 사용할 수 없는 환경입니다(서버리스 등). 로컬/전용 백엔드에서 실행하세요.",
        ) from exc

    sources = list(body.sources) if body.sources is not None else list(SOURCE_IDS)
    events: queue.Queue = queue.Queue()
    _SENTINEL = object()

    def _on_step(source: str, keyword: str, found: int) -> None:
        events.put({"type": "step", "source": source, "keyword": keyword, "found": found})

    def _worker() -> None:
        t0 = time.monotonic()
        try:
            report = collect_batch(
                body.keywords, sources=sources, max_results=body.max_results,
                do_enrich=body.do_enrich, on_step=_on_step,
            )
            try:  # 런 로그 — '수집 이력/헬스' 가 읽음. 로깅 실패가 수집을 깨면 안 됨.
                from store import run_log
                run_log.record_run(report, trigger="manual", duration_s=round(time.monotonic() - t0, 1))
            except Exception:  # noqa: BLE001
                pass
            events.put({
                "type": "done",
                "total_articles": report.total_articles,
                "total_files": report.total_files,
                "errors": report.errors,
            })
        except Exception as exc:  # noqa: BLE001 — 네트워크 차단 등 흡수해 프런트에 전달
            events.put({"type": "error", "error": str(exc)})
        finally:
            events.put(_SENTINEL)

    def _gen() -> Iterator[str]:
        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()
        yield _sse({"type": "start"})
        while True:
            try:
                item = events.get(timeout=15)
            except queue.Empty:
                yield _sse({"type": "ping"})  # keep-alive (프록시 idle 방지)
                continue
            if item is _SENTINEL:
                break
            yield _sse(item)
        worker.join(timeout=1)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/status")
def collect_status() -> dict:
    """최근 수집 런 + 14일 일별 상태(수집 설정 화면 이력 섹션)."""
    from store import run_log

    return {"latest": run_log.latest_run(), "daily": run_log.daily_status(days=14)}


@router.get("/runs")
def collect_runs(limit: int = 12) -> list[dict]:
    from store import run_log

    return run_log.load_runs(limit=limit)


class DiagnoseIn(BaseModel):
    url: str


@router.post("/diagnose")
def collect_diagnose(body: DiagnoseIn) -> dict:
    """기사 URL 수집 진단(HTTP·소프트블록·셀렉터). scraping 지연 import."""
    try:
        from scraping.diagnose import diagnose
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="진단 기능을 사용할 수 없는 환경입니다.") from exc
    return diagnose(body.url)
