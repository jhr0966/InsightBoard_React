"""수집 상세 로그 (feat-collect-log) — 이벤트 계측·저장·렌더·API.

collect_batch 에 CollectLog 를 넘기면 단계별 이벤트(run_start/search_*/enrich_*/
saved/run_end)와 기사별 지표가 쌓이고, save→load→render_text 왕복이 복사용 텍스트를
만든다. 네트워크는 차단 환경이라 naver/google 검색을 mock 한다.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from scraping import run_daily
from store import collect_log

client = TestClient(app)


def _fake_articles(kw: str, n: int = 2) -> list[dict]:
    return [{
        "title": f"{kw} 기사 {i}", "link": f"https://ex.com/{kw}/{i}",
        "press": "테스트신문", "date": "2026-07-21", "summary": "",
        "content": "본문" * 40, "image_url": "https://ex.com/i.jpg",
        "keywords": "", "source": "naver", "query": kw,
    } for i in range(n)]


def _fake_enrich(arts, **k):
    """enrich_parallel 대역 — item_cb 로 기사별 지표를 통보하고 리스트 그대로 반환."""
    cb = k.get("item_cb")
    if cb:
        for a in arts:
            cb({"link": a["link"], "title": a["title"], "content_len": len(str(a.get("content") or "")),
                "image": bool(a.get("image_url")), "ms": 5, "error": ""})
    return arts


def test_collect_log_records_stage_events():
    clog = collect_log.CollectLog()
    with patch.object(run_daily, "_run_keyword_source",
                      lambda src, kw, mx: _fake_articles(kw)), \
         patch.object(run_daily._enrich, "enrich_parallel", _fake_enrich):
        report = run_daily.collect_batch(["용접"], sources=("naver",), max_results=5, clog=clog)

    evs = clog.events()
    kinds = [e["ev"] for e in evs]
    assert kinds[0] == "run_start"
    assert "env" in evs[0] and evs[0]["env"]["workers"] >= 1
    assert "search_start" in kinds and "search_done" in kinds
    assert "enrich_start" in kinds and "enrich_done" in kinds
    assert "enrich_item" in kinds  # 기사별 지표
    assert "saved" in kinds
    assert kinds[-1] == "run_end"
    assert report.total_articles == 2
    # 검색 소요(ms) 가 이벤트에 기록됨
    sd = next(e for e in evs if e["ev"] == "search_done")
    assert "ms" in sd and sd["found"] == 2


def test_on_enrich_reports_global_progress():
    """on_enrich(done, total) 이 소스별 버킷을 전역 누적해 진행률을 통보한다."""
    ticks: list[tuple] = []
    with patch.object(run_daily, "_run_keyword_source",
                      lambda src, kw, mx: _fake_articles(kw, n=3)), \
         patch.object(run_daily._enrich, "enrich_parallel", _fake_enrich_with_progress):
        run_daily.collect_batch(["용접"], sources=("naver",), max_results=5,
                                on_enrich=lambda d, t: ticks.append((d, t)))
    assert ticks, "enrich 진행 콜백이 한 번도 호출되지 않음"
    # enrich_start 에서 total 을 먼저 알림(0,3) → 이후 항목마다 done 증가 → (3,3) 종료
    assert ticks[0] == (0, 3)
    assert ticks[-1] == (3, 3)
    assert [d for d, _ in ticks] == [0, 1, 2, 3]


def _fake_enrich_with_progress(arts, **k):
    cb = k.get("progress_cb")
    if cb:
        for i, _a in enumerate(arts, 1):
            cb(i, len(arts), None)
    return arts


def test_search_error_event_on_failure():
    clog = collect_log.CollectLog()

    def _boom(src, kw, mx):
        raise RuntimeError("403 blocked")

    with patch.object(run_daily, "_run_keyword_source", _boom):
        run_daily.collect_batch(["x"], sources=("naver",), clog=clog)
    errs = [e for e in clog.events() if e["ev"] == "search_error"]
    assert errs and "403" in errs[0]["error"]


def test_save_load_render_roundtrip():
    clog = collect_log.CollectLog()
    clog.event("run_start", env={"workers": 4}, keywords=["a"])
    clog.event("search_done", src="naver", kw="a", found=3, ms=1200)
    clog.event("enrich_item", src="naver", title="좋은 기사", content_len=900, image=True, ms=800, error="")
    clog.event("enrich_item", src="naver", title="빈 기사", content_len=0, image=False, ms=20000,
               error="ReadTimeout: timed out")
    clog.event("run_end", total_s=3.4, total_articles=3)

    saved = collect_log.save("20260721-091203-abcd", clog,
                             meta={"ts": "2026-07-21T09:12:03+00:00", "duration_s": 3.4,
                                   "env": {"workers": 4}, "totals": {"total_articles": 3}})
    assert saved["run_id"] == "20260721-091203-abcd"

    loaded = collect_log.load("20260721-091203-abcd")
    assert loaded is not None and len(loaded["events"]) == 5

    text = collect_log.render_text(loaded)
    assert "수집 런" in text
    assert "설정:" in text and "workers=4" in text
    # 실패/누락 섹션: content_len 0 + ReadTimeout 기사가 잡힘
    assert "실패/누락" in text and "ReadTimeout" in text
    # 2부: JSONL 이벤트가 그대로 포함
    assert '"ev": "run_start"' in text or '"ev":"run_start"' in text


def test_run_id_sanitized_against_traversal():
    clog = collect_log.CollectLog()
    clog.event("run_end", total_s=1)
    collect_log.save("../../etc/passwd", clog, meta={})
    import config
    detail = config.DATA_ROOT / "logs" / "detail"
    names = {p.name for p in detail.glob("*.json")}
    assert all(".." not in n and "/" not in n for n in names)


def test_trim_keeps_recent_runs():
    for i in range(25):
        clog = collect_log.CollectLog()
        clog.event("run_end", total_s=i)
        collect_log.save(f"run-{i:03d}", clog, meta={})
    runs = collect_log.list_runs(limit=100)
    assert len(runs) <= 20  # _KEEP_RUNS


def test_api_logs_list_and_detail_and_404():
    clog = collect_log.CollectLog()
    clog.event("run_start", env={"workers": 4})
    clog.event("run_end", total_s=2.0, total_articles=1)
    collect_log.save("20260721-120000-ffff", clog,
                     meta={"ts": "2026-07-21T12:00:00+00:00", "duration_s": 2.0})

    lst = client.get("/api/collect/logs").json()
    assert any(r["run_id"] == "20260721-120000-ffff" for r in lst)

    detail = client.get("/api/collect/logs/20260721-120000-ffff").json()
    assert detail["run_id"] == "20260721-120000-ffff"
    assert "text" in detail and "수집 런" in detail["text"]

    assert client.get("/api/collect/logs/nope-does-not-exist").status_code == 404
