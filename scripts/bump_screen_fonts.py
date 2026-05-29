"""화면별 v2 CSS 의 font-size px 값을 일괄 bump.

scale.css 의 selector-level override 가 5개 화면 모두를 빠짐없이 덮는 것이
어려우니, 추출된 screen CSS 자체를 한 번 손봐 베이스 사이즈를 올린다.
시안 원본 (.design-handoff/) 은 그대로 두고 우리 사본만 갱신.

알고리즘:
  - 'font-size: Xpx' 또는 'font-size: X.Ypx' 매칭
  - X < 12 → +4 (작은 메타 라벨, 가장 큰 절대 bump)
  - 12 ≤ X < 18 → +5 (본문 / 캡션)
  - 18 ≤ X < 28 → +6 (헤드라인)
  - 28 ≤ X       → +5 (대형 숫자 / 큰 헤드)

CLI:
    python scripts/bump_screen_fonts.py            # 모두 bump
    python scripts/bump_screen_fonts.py --dry-run  # 변경 사항만 출력
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


SCREEN_CSS_DIR = Path("assets/v2/screens")
FONT_RE = re.compile(r"font-size:\s*([\d.]+)px")


def bump_value(orig: float) -> float:
    if orig < 12:
        return orig + 4
    if orig < 18:
        return orig + 5
    if orig < 28:
        return orig + 6
    return orig + 5


def _format(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:g}"


def process(path: Path, *, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        orig = float(m.group(1))
        new = bump_value(orig)
        n += 1
        return f"font-size: {_format(new)}px"

    new_text = FONT_RE.sub(repl, text)
    if not dry_run and n > 0:
        path.write_text(new_text, encoding="utf-8")
    return n


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    if not SCREEN_CSS_DIR.exists():
        print(f"missing: {SCREEN_CSS_DIR}")
        return 2
    for css in sorted(SCREEN_CSS_DIR.glob("*.css")):
        n = process(css, dry_run=dry_run)
        flag = "(dry-run)" if dry_run else ""
        print(f"  {css.name:32s}  bumped {n} font-size rules {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
