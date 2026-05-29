"""인라인 `<svg>...</svg>` → `<img src="data:image/svg+xml;utf8,…">` 변환.

문제: Streamlit `st.html()` 가 보안 sanitizer 로 `<svg>` 태그를 전부 strip.
프로젝트 룰 (tests/test_html_rendering.py) 은 `st.markdown(unsafe_allow_html=True)`
대안 금지. 결과: 아이콘 없는 grid 가 `14px 1fr` 첫 컬럼 비어 두 번째 컬럼이
14px 로 collapse 되는 회귀 (SOLA ws-callout 등).

해결: `<svg>` 마크업을 data-URI 로 감싼 `<img>` 로 교체. img 는 sanitizer 통과.

추가 처리:
  - xmlns 가 없으면 자동 주입
  - stroke="currentColor" / fill="currentColor" → 기본 색(stroke-default arg) 으로 치환
    (img 안에서는 currentColor 가 부모 색 상속 불가)
  - 단일 인용부호 → SVG 내부에서 사용, 외부 src="" 와 충돌 없게

CLI:
    python scripts/inline_svg_to_img.py
    python scripts/inline_svg_to_img.py --dry-run
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote


TARGETS = (
    *Path("assets/v2/screens").glob("*.html"),
    Path("ui/app_shell.py"),
)

SVG_RE = re.compile(r"<svg\b[^>]*?>.*?</svg>", flags=re.DOTALL | re.IGNORECASE)

# currentColor 가 자동 상속 안 됨 — 기본 색 (muted text)
DEFAULT_COLOR = "#475569"  # var(--text-secondary) 와 동일


def _convert_one(svg_str: str) -> str:
    s = svg_str
    # xmlns 주입
    if "xmlns=" not in s:
        s = re.sub(r"<svg\b", "<svg xmlns='http://www.w3.org/2000/svg'", s, count=1)
    # currentColor → 기본 색 (img 안에서는 inherit 불가)
    s = s.replace('stroke="currentColor"', f'stroke="{DEFAULT_COLOR}"')
    s = s.replace('fill="currentColor"', f'fill="{DEFAULT_COLOR}"')
    # 내부 더블쿼트를 싱글쿼트로 — img src="" 안에 들어가야 함
    s = s.replace('"', "'")
    # width/height 추출해 img 에 동일 사이즈 부여 (CSS 가 별도 폭 지정 안 했을 때 대비)
    m_w = re.search(r"width=['\"]?(\d+)['\"]?", svg_str)
    m_h = re.search(r"height=['\"]?(\d+)['\"]?", svg_str)
    w = m_w.group(1) if m_w else None
    h = m_h.group(1) if m_h else None
    size_attr = ""
    if w:
        size_attr += f' width="{w}"'
    if h:
        size_attr += f' height="{h}"'
    return f'<img src="data:image/svg+xml;utf8,{s}"{size_attr} alt="" />'


def process(path: Path, *, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        return _convert_one(m.group(0))

    new_text = SVG_RE.sub(repl, text)
    if not dry_run and n > 0:
        path.write_text(new_text, encoding="utf-8")
    return n


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    total = 0
    for path in TARGETS:
        if not path.exists():
            continue
        n = process(path, dry_run=dry_run)
        total += n
        flag = "(dry-run)" if dry_run else ""
        print(f"  {str(path):45s}  {n:>4d} svg → img {flag}")
    print(f"  total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
