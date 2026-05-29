"""5 화면 정밀 분석 — bounding box + 가독성 / overflow / 컬럼 간격 측정.

캡처는 1920x1200 (full HD 데스크톱 기준) + 1680x1000 동시.
각 화면의 핵심 요소 박스/스크롤/줄바꿈 메트릭 출력.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from urllib.parse import quote
from pathlib import Path

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
PW = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

AREAS = {
    "board": "📊 오늘의 보드",
    "data": "🧱 데이터 관리",
    "insights": "🔎 인사이트 분석",
    "sola": "🤖 SOLA 작업실",
    "archive": "📦 산출물 보관함",
}

# (selector, label) — 화면별로 측정할 핵심 박스
INSPECT = {
    "board": [
        (".db-topbar", "topbar"),
        (".app-side", "left sidebar"),
        (".app-sola", "right SOLA"),
        (".db-greet", "greet section"),
        (".db-greet-h", "greeting h1"),
        (".db-kpi-grid", "KPI grid"),
        (".db-stories", "top stories"),
        (".db-trend", "trend section"),
    ],
    "data": [
        (".dm-shell > header", "header"),
        (".dm-head-stats", "stats row"),
        (".dm-tabs", "tabs"),
        (".dm-split", "main split"),
        (".dm-jobs", "jobs panel"),
        (".dm-news", "news panel"),
        (".dm-sub-grid", "keyword+roadmap"),
    ],
    "insights": [
        (".ia-shell > header", "header"),
        (".ia-head-stats", "stats row"),
        (".ia-tabs", "tabs"),
        (".ia-trend-grid", "trend grid"),
        (".ia-mtx-wrap", "matrix wrap"),
        (".ia-pc-list", "process map"),
    ],
    "sola": [
        (".ws-shell", "ws shell"),
        (".ws-threads", "threads"),
        (".ws-chat", "chat"),
        (".ws-ctx", "ctx"),
        (".ws-chat-head", "chat header"),
        (".ws-thread-body", "thread body"),
        (".ws-composer", "composer"),
    ],
    "archive": [
        (".oa-shell > header", "header"),
        (".oa-head-stats", "stats row"),
        (".oa-controls", "controls"),
        (".oa-board", "kanban board"),
        (".oa-col", "kanban col"),
    ],
}


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait(port: int, t: int = 30) -> bool:
    import urllib.request
    for _ in range(t * 2):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1).read()
            return True
        except Exception:
            time.sleep(0.5)
    return False


def measure(viewport_w: int = 1920, viewport_h: int = 1200, capture_suffix: str = "") -> dict:
    """Return per-screen measurements + capture full-page PNG."""
    out_dir = Path("data/_verify")
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict] = {}
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(port), "--server.address", "127.0.0.1",
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        if not wait(port):
            return {"error": "streamlit not ready"}

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=PW)
            ctx = browser.new_context(viewport={"width": viewport_w, "height": viewport_h})
            page = ctx.new_page()

            for key, label in AREAS.items():
                url = f"http://127.0.0.1:{port}/?app_area={quote(label)}"
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                try:
                    page.wait_for_selector(".db-topbar", timeout=15000)
                except Exception:
                    pass
                page.wait_for_timeout(2000)

                # capture
                shot = out_dir / f"{key}{capture_suffix}.png"
                page.screenshot(path=str(shot), full_page=True)

                # measurements
                metrics = []
                for sel, name in INSPECT.get(key, []):
                    box_info = page.evaluate(
                        """(sel) => {
                            const el = document.querySelector(sel);
                            if (!el) return null;
                            const r = el.getBoundingClientRect();
                            const s = getComputedStyle(el);
                            return {
                              top: r.top, left: r.left,
                              width: r.width, height: r.height,
                              right: r.right, bottom: r.bottom,
                              overflowX: el.scrollWidth > el.clientWidth,
                              overflowY: el.scrollHeight > el.clientHeight,
                              fs: s.fontSize, lh: s.lineHeight,
                              padding: s.padding, gap: s.gap,
                            };
                        }""",
                        sel,
                    )
                    if box_info:
                        metrics.append({"sel": sel, "name": name, **box_info})
                    else:
                        metrics.append({"sel": sel, "name": name, "missing": True})
                results[key] = {"shot": str(shot), "metrics": metrics}

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    return results


def main() -> int:
    print("== 1920x1200 viewport ==")
    res = measure(1920, 1200, capture_suffix="_hd")
    for key, info in res.items():
        if "metrics" not in info:
            continue
        print(f"\n[{key}]  → {info['shot']}")
        for m in info["metrics"]:
            if m.get("missing"):
                print(f"  MISS  {m['name']:<22s} {m['sel']}")
                continue
            of = "X" if m.get("overflowX") else " "
            of += "Y" if m.get("overflowY") else " "
            print(f"  {of}  {m['name']:<22s} "
                  f"x={m['left']:>4.0f} w={m['width']:>5.0f}  "
                  f"y={m['top']:>5.0f} h={m['height']:>6.0f}  "
                  f"fs={m['fs']:<8s} lh={m['lh']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
