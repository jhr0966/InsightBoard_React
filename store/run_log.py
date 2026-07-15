"""수집 런 로그 영구화 (JSONL) — Phase F 관측성.

`scraping.run_daily.collect_batch` 가 돌려주는 `CollectionReport` 를 run_id·시각·
트리거·소스별 건수·오류로 구조화해 `data/logs/runs.jsonl` 에 append 한다.
React 수집 화면(Collect)의 '수집 런 타임라인'(`/api/collect/runs`)이 최근 런을 읽어 노출한다 (조용한 실패 감지용).

엔트리 스키마:
    run_id        "20260602-054612-ab12"  (시각 + 4hex)
    ts            ISO8601 (UTC)
    trigger       "cron" | "manual" | "board" | ...
    ok            bool — 오류 0건이면 True
    total_articles, total_files  int
    duration_s    float | None
    content_ready / content_rate_pct    본문(≥50자) 확보 건수·비율 (저장 시점)
    image_ready / image_rate_pct        대표 이미지 확보 건수·비율
    cache_hits           재fetch 회피 캐시 적중 기사 수
    deadline_abandoned   enrich 데드라인 초과로 본문 없이 중단된 기사 수
    enrich_skipped_cap   배치 상한(INSIGHTBOARD_ENRICH_MAX_ARTICLES) 스킵 수
    sources       [{"source", "count", "keywords", "ok": True, ("sites")}, ...]  (saved 기준,
                  sites 는 tech 의 사이트별 건수 {"AI Times": n, ...} — 있을 때만)
    error_sources [source, ...]  (오류 난 소스 — 중복 제거·정렬)
    errors        [{"source", "keyword", "error"}, ...]  (원본 보존)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config

_LOGS_DIR_NAME = "logs"
_RUNS_FILE = "runs.jsonl"
_MAX_KEEP = 500  # 파일 무한 증가 방지 — 최근 N 런만 유지


def _runs_path(*, create: bool = False) -> Path:
    # config.DATA_ROOT 를 호출 시점에 참조 — 테스트(conftest)가 monkeypatch 한 tmp
    # 경로를 그대로 따른다 (from-import 시 import 시점 값 고정 footgun 회피).
    logs_dir = config.DATA_ROOT / _LOGS_DIR_NAME
    if create:
        logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / _RUNS_FILE


def _new_run_id(now: datetime) -> str:
    return f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"


def _field(report, attr: str) -> list:
    """CollectionReport 객체 또는 동형 dict 에서 list 필드 안전 추출."""
    if isinstance(report, dict):
        return list(report.get(attr) or [])
    return list(getattr(report, attr, None) or [])


def entry_from_report(
    report,
    *,
    trigger: str = "manual",
    run_id: str | None = None,
    ts: str | None = None,
    duration_s: float | None = None,
) -> dict:
    """CollectionReport → 구조화 로그 dict (순수 함수, I/O 없음).

    `report` 는 `saved`/`errors` 속성을 갖는 객체(`run_daily.CollectionReport`)
    또는 같은 키를 갖는 dict 를 받는다.
    """
    saved = _field(report, "saved")
    errors = _field(report, "errors")
    stats = (report.get("stats") if isinstance(report, dict)
             else getattr(report, "stats", None)) or {}
    now = datetime.now(timezone.utc)

    sources = []
    for r in saved:
        row = {
            "source": str(r.get("source", "")),
            "count": int(r.get("count", 0) or 0),
            "keywords": list(r.get("keywords") or []),
            "ok": True,
        }
        # tech 의 사이트별 분해(AI Times/오토메이션월드) — 재열람 표가 나눠 표시.
        if isinstance(r.get("sites"), dict) and r["sites"]:
            row["sites"] = {str(k): int(v) for k, v in r["sites"].items()}
        sources.append(row)
    error_sources = sorted({str(e.get("source", "")) for e in errors if e.get("source")})

    # 관측지표(Phase 0 보강) — 병합·튜닝 판단용 원자료. 확보율은 저장 시점 기준.
    total_articles = sum(s["count"] for s in sources)

    def _pct(n: int) -> float:
        return round(n / total_articles * 100, 1) if total_articles else 0.0

    content_ready = int(stats.get("content_ready", 0) or 0)
    image_ready = int(stats.get("image_ready", 0) or 0)

    return {
        "run_id": run_id or _new_run_id(now),
        "ts": ts or now.isoformat(),
        "trigger": str(trigger or "manual"),
        "ok": len(errors) == 0,
        "total_articles": total_articles,
        "total_files": sum(1 for r in saved if r.get("path")),
        "duration_s": round(float(duration_s), 2) if duration_s is not None else None,
        "content_ready": content_ready,
        "content_rate_pct": _pct(content_ready),
        "image_ready": image_ready,
        "image_rate_pct": _pct(image_ready),
        "cache_hits": int(stats.get("cache_hits", 0) or 0),
        "deadline_abandoned": int(stats.get("deadline_abandoned", 0) or 0),
        "enrich_skipped_cap": int(stats.get("enrich_skipped_cap", 0) or 0),
        "sources": sources,
        "error_sources": error_sources,
        "errors": [
            {
                "source": str(e.get("source", "")),
                "keyword": str(e.get("keyword", "") or ""),
                "error": str(e.get("error", "")),
            }
            for e in errors
        ],
    }


def record_run(report, **kwargs) -> dict:
    """report 를 구조화해 `runs.jsonl` 에 append 하고 기록된 엔트리를 반환.

    로깅 실패가 수집 자체를 깨면 안 되므로 호출부에서 try/except 로 감싸는 것을
    권장한다 (여기서는 디렉토리 생성·append 만 수행).
    """
    entry = entry_from_report(report, **kwargs)
    path = _runs_path(create=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _trim(path)
    return entry


# 런 1줄의 보수적 최소 바이트 — 사이즈 게이트용(실제는 ~300~700B). 이보다 작게 잡아야
# "size < max_keep*이값 → 줄 수 < max_keep" 이 항상 참(트림 누락 없음).
_MIN_LINE_BYTES = 80


def _trim(path: Path, max_keep: int = _MAX_KEEP) -> None:
    """파일이 max_keep 줄을 넘으면 최근 max_keep 줄만 남긴다.

    매 append 마다 전체 파일을 읽지 않도록, 파일 크기가 확실히 max_keep 미만인
    동안에는(size < max_keep*_MIN_LINE_BYTES) 읽기를 건너뛴다 (개선 백로그 2.4).
    """
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size < max_keep * _MIN_LINE_BYTES:
        return  # 확실히 max_keep 미만 — 읽기/리라이트 생략
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > max_keep:
        path.write_text("\n".join(lines[-max_keep:]) + "\n", encoding="utf-8")


def load_runs(limit: int = 20) -> list[dict]:
    """최근 런 (최신 우선). 파일이 없거나 깨진 줄은 건너뛴다."""
    path = _runs_path()
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    out.reverse()  # 최신 우선
    return out[:limit] if limit else out


def latest_run() -> dict | None:
    runs = load_runs(limit=1)
    return runs[0] if runs else None


def daily_status(days: int = 14) -> list[str | None]:
    """최근 `days` 일 각 날짜의 수집 런 상태 (오래된→최신, 길이 `days`).

    값: `"ok"`(그날 런이 있고 전부 성공) / `"fail"`(하나라도 실패) / `None`(런 없음).
    하루 여러 런이면 하나라도 실패 시 그날은 `"fail"`. 14일 볼륨 sparkline 에
    일별 성공/실패를 겹쳐 보여주는 데 쓴다(`data_management_v2._hist_html`).
    """
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date()
    buckets: dict[int, str] = {}  # delta(0=오늘 … days-1=가장 오래) → status
    for r in load_runs(limit=0):
        ts = str(r.get("ts", ""))
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
        delta = (today - d).days
        if not (0 <= delta < days):
            continue
        if buckets.get(delta) == "fail":
            continue  # 실패가 우선 — 이미 fail 이면 유지
        buckets[delta] = "ok" if r.get("ok") else "fail"
    return [buckets.get(days - 1 - i) for i in range(days)]

