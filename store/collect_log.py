"""수집 상세 로그 — 디버깅용 구조화 이벤트 + 사람용 요약 타임라인.

`run_log.py` 가 런당 1줄 요약(수집 이력/헬스)인 반면, 여기는 **런당 상세 이벤트
로그**다: 각 단계 소요시간·HTTP/예외·기사별 본문/이미지 확보 여부를 남겨, 수집이
느리거나 누락되는 원인을 로그 한 장으로 진단한다. `data/logs/detail/{run_id}.json`.

두 부분으로 렌더한다:
  1부 요약 타임라인 — 병목·실패를 한눈에 (사람용)
  2부 구조화 이벤트(JSONL) — 단계별 소요·예외·기사별 지표 (디버깅용 본체)

⚠ 서버 파일이라 무료 호스팅 슬립/재배포 시 사라진다 → 수집 직후 확인·복사용.
run_id 는 `run_log` 와 공유해 '수집 이력'과 상세 로그가 같은 런을 가리킨다.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

import config

_DETAIL_DIR = "detail"
_MAX_EVENTS = 4000   # 이벤트 상한 — 런당 폭주 방지(초과분은 dropped 로 집계)
_KEEP_RUNS = 20      # 상세 로그 파일 보관 수(최근 N 런)
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


class CollectLog:
    """수집 1런의 이벤트 수집기. 소스가 병렬 스레드로 돌므로 **스레드 안전**.

    `event(ev, **fields)` 는 `{t: 경과초, ev, ...}` 를 누적한다. `t` 는 생성 시점
    기준 monotonic 경과초(벽시계 아님 — 단계 소요 계산용).
    """

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._lock = threading.Lock()
        self._t0 = time.monotonic()
        self.dropped = 0

    def event(self, ev: str, **fields) -> None:
        rec = {"t": round(time.monotonic() - self._t0, 2), "ev": ev, **fields}
        with self._lock:
            if len(self._events) >= _MAX_EVENTS:
                self.dropped += 1
                return
            self._events.append(rec)

    def events(self) -> list[dict]:
        with self._lock:
            return list(self._events)


# ── 영구화 ────────────────────────────────────────────────────


def _detail_dir(*, create: bool = False) -> Path:
    # config.DATA_ROOT 를 호출 시점에 참조(테스트 monkeypatch 존중).
    d = config.DATA_ROOT / "logs" / _DETAIL_DIR
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def _safe(run_id: str) -> str:
    return _SAFE_ID.sub("", str(run_id))[:64]


def save(run_id: str, log: CollectLog, *, meta: dict | None = None) -> dict:
    """이벤트 로그를 `{run_id}.json` 으로 저장하고 오래된 런은 정리."""
    d = _detail_dir(create=True)
    payload = {
        "run_id": run_id,
        "meta": meta or {},
        "events": log.events(),
        "dropped": log.dropped,
    }
    (d / f"{_safe(run_id)}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    _trim(d)
    return payload


def _trim(d: Path, keep: int = _KEEP_RUNS) -> None:
    try:
        files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for p in files[keep:]:
        try:
            p.unlink()
        except OSError:
            pass


def list_runs(limit: int = 20) -> list[dict]:
    """최근 상세 로그 런 목록(최신 우선) — {run_id, meta, event_count}."""
    d = _detail_dir()
    if not d.exists():
        return []
    files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out: list[dict] = []
    for p in files:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({
            "run_id": obj.get("run_id", p.stem),
            "meta": obj.get("meta", {}),
            "event_count": len(obj.get("events", [])),
        })
    return out


def load(run_id: str) -> dict | None:
    p = _detail_dir() / f"{_safe(run_id)}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ── 렌더 (복사용 텍스트) ──────────────────────────────────────


def render_text(payload: dict) -> str:
    """저장 payload → 복사용 2부 텍스트(1부 요약 + 2부 JSONL 이벤트)."""
    meta = payload.get("meta") or {}
    events = payload.get("events") or []
    lines: list[str] = []

    lines.append(f"■ 수집 런 {meta.get('ts', '')}  (run_id: {payload.get('run_id', '')})")
    dur = meta.get("duration_s")
    lines.append(f"■ 총 소요: {dur}s" if dur is not None else "■ 총 소요: (기록 없음)")
    env = meta.get("env") or {}
    if env:
        lines.append("■ 설정: " + " · ".join(f"{k}={v}" for k, v in env.items()))
    tot = meta.get("totals") or {}
    if tot:
        lines.append(
            f"■ 결과: 저장 {tot.get('total_articles', 0)}건 · "
            f"본문 {tot.get('content_ready', 0)} · 이미지 {tot.get('image_ready', 0)} · "
            f"캐시적중 {tot.get('cache_hits', 0)} · 데드라인중단 {tot.get('deadline_abandoned', 0)}")

    # 소스별 검색 소요(가장 최근 search_done 기준) — 병목 파악.
    by_src_ms: dict[str, int] = {}
    for e in events:
        if e.get("ev") == "search_done":
            by_src_ms[str(e.get("src"))] = by_src_ms.get(str(e.get("src")), 0) + int(e.get("ms", 0) or 0)
        elif e.get("ev") == "enrich_done":
            by_src_ms[f"enrich:{e.get('src')}"] = int(e.get("ms", 0) or 0)
    if by_src_ms:
        lines.append("■ 단계별 소요(ms): " + " · ".join(f"{k}={v}" for k, v in by_src_ms.items()))

    # 구글 원문 링크 복원 요약 — unresolved 가 곧 본문·사진 못 가져오는 기사 수.
    for e in events:
        if e.get("ev") == "resolve":
            tot_r = int(e.get("total", 0) or 0)
            unres = int(e.get("unresolved", 0) or 0)
            rate = f"{round(100 * (tot_r - unres) / tot_r)}%" if tot_r else "-"
            lines.append(
                f"■ 구글 링크 복원 [{e.get('src')}]: {tot_r - unres}/{tot_r} 성공({rate}) · "
                f"직링크 {e.get('direct', 0)} · base64 {e.get('decoded', 0)} · "
                f"batch {e.get('batch', 0)} · redirect {e.get('redirect', 0)} · "
                f"미복원 {unres}(=본문·사진 누락 위험)")

    # 실패/누락 — 검색 오류 + 본문 미확보 enrich 기사.
    fails = [e for e in events
             if e.get("ev") == "search_error"
             or (e.get("ev") == "enrich_item" and (e.get("error") or int(e.get("content_len", 0) or 0) < 50))]
    if fails:
        lines.append(f"■ 실패/누락 {len(fails)}건:")
        for e in fails[:50]:
            if e.get("ev") == "search_error":
                lines.append(f"   ✗ 검색 [{e.get('src')}] \"{e.get('kw', '')}\" — {e.get('error', '')}")
            else:
                why = e.get("error") or f"본문 {e.get('content_len', 0)}자"
                img = "" if e.get("image") else " · 이미지✗"
                lines.append(f"   ✗ enrich {str(e.get('title', ''))[:44]} — {why}{img}")
        if len(fails) > 50:
            lines.append(f"   … 외 {len(fails) - 50}건")

    lines.append("─" * 54)
    lines.append("■ 상세 이벤트 (JSONL — 아래 전체를 복사해 전달하세요):")
    for e in events:
        lines.append(json.dumps(e, ensure_ascii=False))
    if payload.get("dropped"):
        lines.append(f"… (이벤트 {payload['dropped']}건이 상한 {_MAX_EVENTS} 초과로 생략됨)")
    return "\n".join(lines)
