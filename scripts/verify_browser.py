"""브라우저로 v2 화면 6개 시각 회귀 검증 — Playwright + 사전설치된 chromium.

Usage:
  # 1) Streamlit 띄운 상태에서
  python scripts/verify_browser.py http://127.0.0.1:8501

  # 2) 결과: /tmp/v2-screens/<area>.png 6장
"""
from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
AREAS = [
    ("board", "📊 오늘의 보드"),
    ("data", "🧱 데이터 관리"),
    ("insights", "🔎 인사이트 분석"),
    ("sola", "🤖 SOLA 작업실"),
    ("archive", "📦 산출물 보관함"),
    ("persona", None),  # ?persona_editor=1
]


def main(base_url: str = "http://127.0.0.1:8501") -> int:
    out = Path("/tmp/v2-screens")
    out.mkdir(parents=True, exist_ok=True)
    fails: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        for slug, area in AREAS:
            errors.clear()
            url = (f"{base_url}/?persona_editor=1" if area is None
                   else f"{base_url}/?app_area={quote(area)}")
            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
                # v2 셸이 inject 될 때까지 대기 — Streamlit 의 websocket 렌더 완료 신호
                try:
                    page.wait_for_selector(".db-topbar", timeout=15000, state="attached")
                except Exception:
                    pass
                page.wait_for_timeout(2000)  # 캐시 미스 / 차트 SVG 렌더 안정화
                shot = out / f"{slug}.png"
                page.screenshot(path=str(shot), full_page=True)
                size = shot.stat().st_size
                err_summary = f" | js_errors={len(errors)}" if errors else ""
                print(f"  ✅ {slug:8s} {size:>6}B  ({shot}){err_summary}")
                if errors:
                    for e in errors[:3]:
                        print(f"     ⚠ {e[:160]}")
            except Exception as exc:
                fails.append(f"{slug}: {exc}")
                print(f"  ❌ {slug}: {exc}")
        b.close()
    if fails:
        print(f"\nFAIL: {len(fails)}/{len(AREAS)}")
        return 1
    print(f"\nOK: {len(AREAS)}/{len(AREAS)} screens captured → {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8501"))
