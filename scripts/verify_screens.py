"""Local visual verification — Streamlit 띄우고 playwright 로 스크린샷 캡처.

CLI:
    python scripts/verify_screens.py [area1 area2 ...]
    python scripts/verify_screens.py board data

Streamlit 을 background 로 띄우고 (반드시 `python -m streamlit run app.py`)
playwright headless chromium 으로 각 area 의 스크린샷을 `data/_verify/` 아래
저장한다. v2 화면들의 시각 회귀 가드 용도.

Area 키:
    board → "📊 오늘의 보드"
    data  → "🧱 데이터 관리"
    insights → "🔎 인사이트 분석"
    sola  → "🤖 SOLA 작업실"
    archive → "📦 산출물 보관함"
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

# ── playwright pre-installed at /opt/pw-browsers/chromium-1194/ in this env.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
_PW_CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


AREAS = {
    "board":    "📊 오늘의 보드",
    "data":     "🧱 데이터 관리",
    "insights": "🔎 인사이트 분석",
    "sola":     "🤖 SOLA 작업실",
    "archive":  "📦 산출물 보관함",
}


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_ready(port: int, timeout: float = 30.0) -> bool:
    import urllib.request

    start = time.time()
    url = f"http://127.0.0.1:{port}/healthz"
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main(argv: list[str]) -> int:
    selected = argv or list(AREAS.keys())
    unknown = [a for a in selected if a not in AREAS]
    if unknown:
        print(f"unknown area(s): {unknown} — valid: {list(AREAS)}")
        return 2

    out_dir = Path("data/_verify")
    out_dir.mkdir(parents=True, exist_ok=True)

    port = _find_free_port()
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", str(port),
            "--server.address", "127.0.0.1",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        if not _wait_ready(port):
            log = proc.stdout.read(2048).decode() if proc.stdout else ""
            print(f"streamlit did not become ready in 30s\n{log}")
            return 1
        print(f"streamlit ready on 127.0.0.1:{port}")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=_PW_CHROME)
            ctx = browser.new_context(viewport={"width": 1680, "height": 1000})
            page = ctx.new_page()
            for area_key in selected:
                label = AREAS[area_key]
                url = f"http://127.0.0.1:{port}/?app_area={quote(label)}"
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                # Streamlit pushes components via WebSocket after initial HTML.
                # Wait for the v2 topbar (rendered by app_shell) to appear.
                try:
                    page.wait_for_selector(".db-topbar", timeout=15000)
                except Exception:
                    pass  # v1 화면이거나 셸 미적용 — 그래도 스크린샷은 찍는다
                page.wait_for_timeout(1500)  # 폰트·이미지 settle
                shot_path = out_dir / f"{area_key}.png"
                page.screenshot(path=str(shot_path), full_page=True)
                print(f"  ✓ {area_key}  →  {shot_path}")
            browser.close()
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
