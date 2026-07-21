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
from config import DEFAULT_DAILY_KEYWORDS

router = APIRouter(prefix="/api/collect", tags=["collect"])
# 스키마 기본값 — top-level 에서 scraping 을 import 하지 않기 위해 로컬 상수.
_DEFAULT_SOURCES = ("naver", "google", "tech")


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _keywords_or_default(keywords: list[str]) -> list[str]:
    """키워드가 비면 도메인 기본 키워드(`config.DEFAULT_DAILY_KEYWORDS`)로 폴백.

    naver/google 은 키워드가 있어야 검색하므로, UI '지금 수집'(빈 키워드)·페르소나
    관심 키워드 미설정 시 두 소스가 통째로 비던 문제 방어. tech(AI Times)는
    키워드 무관이라 영향 없음. cron(daily_scrape)은 자체 기본값을 직접 넘긴다.
    """
    cleaned = [k.strip() for k in keywords if k and k.strip()]
    return cleaned or list(DEFAULT_DAILY_KEYWORDS)


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
        _keywords_or_default(body.keywords),
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
    keywords = _keywords_or_default(body.keywords)
    events: queue.Queue = queue.Queue()
    _SENTINEL = object()

    def _on_step(source: str, keyword: str, found: int) -> None:
        events.put({"type": "step", "source": source, "keyword": keyword, "found": found})

    def _on_enrich(done: int, total: int) -> None:
        # 본문 정리(enrich) 전역 진행 — 검색 후 가장 긴 단계라 스피너에 진행률을 준다.
        events.put({"type": "enrich", "done": done, "total": total})

    # 상세 수집 로그(디버깅) — run_log 와 run_id 를 공유해 '수집 이력'과 같은 런을 가리킨다.
    from store import collect_log as _collect_log
    from store import run_log as _run_log
    from datetime import datetime, timezone

    _now = datetime.now(timezone.utc)
    run_id = _run_log._new_run_id(_now)
    clog = _collect_log.CollectLog()

    def _worker() -> None:
        t0 = time.monotonic()
        try:
            report = collect_batch(
                keywords, sources=sources, max_results=body.max_results,
                do_enrich=body.do_enrich, on_step=_on_step, on_enrich=_on_enrich, clog=clog,
            )
            duration = round(time.monotonic() - t0, 1)
            try:  # 런 로그 — '수집 이력/헬스' 가 읽음. 로깅 실패가 수집을 깨면 안 됨.
                _run_log.record_run(report, trigger="manual", duration_s=duration,
                                    run_id=run_id, ts=_now.isoformat())
            except Exception:  # noqa: BLE001
                pass
            try:  # 상세 이벤트 로그 저장 — 수집 로그 버튼이 읽는다.
                _collect_log.save(run_id, clog, meta={
                    "ts": _now.isoformat(), "trigger": "manual", "duration_s": duration,
                    "env": next((e for e in clog.events() if e.get("ev") == "run_start"), {}).get("env", {}),
                    "totals": {
                        "total_articles": report.total_articles,
                        "content_ready": report.stats.get("content_ready", 0),
                        "image_ready": report.stats.get("image_ready", 0),
                        "cache_hits": report.stats.get("cache_hits", 0),
                        "deadline_abandoned": report.stats.get("deadline_abandoned", 0),
                    },
                })
            except Exception:  # noqa: BLE001
                pass
            events.put({
                "type": "done",
                "run_id": run_id,           # 방금 런의 상세 로그를 바로 열 수 있게.
                "total_articles": report.total_articles,
                "total_files": report.total_files,
                "saved": report.saved,      # 출처별 건수(+tech 사이트 분해)
                "errors": report.errors,    # {source, keyword, error}
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


@router.get("/logs")
def collect_logs(limit: int = 20) -> list[dict]:
    """상세 수집 로그가 있는 최근 런 목록(최신 우선) — 로그 버튼 드롭다운용."""
    from store import collect_log

    return collect_log.list_runs(limit=limit)


@router.get("/logs/{run_id}")
def collect_log_detail(run_id: str) -> dict:
    """단일 런의 상세 로그 — 복사용 렌더 텍스트 + 원시 이벤트.

    `text` 는 1부 요약 + 2부 JSONL 이벤트를 합친 복사용 문자열이다.
    """
    from store import collect_log

    payload = collect_log.load(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="해당 런의 상세 로그가 없습니다(휘발됐거나 오래됨).")
    return {
        "run_id": payload.get("run_id", run_id),
        "meta": payload.get("meta", {}),
        "events": payload.get("events", []),
        "dropped": payload.get("dropped", 0),
        "text": collect_log.render_text(payload),
    }


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
