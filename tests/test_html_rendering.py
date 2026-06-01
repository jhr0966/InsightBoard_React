from __future__ import annotations

import ast
from pathlib import Path


def test_ui_does_not_render_component_html_through_markdown_unsafe():
    # 예외:
    #  - components.py: 디자인 토큰/위젯 (사용자 입력 없음)
    #  - styles.py: CSS 자산 inject 전용 — `st.html("<style>")` 가 Streamlit 에서
    #    수만 자 `<style>` 블록을 mount 하지 못함이 확인돼 (DOM 에서 누락),
    #    `st.markdown(unsafe_allow_html=True)` 코드 경로로만 안정 주입.
    #    inject 내용은 디스크의 정적 CSS 파일이라 사용자 입력 아님.
    _ALLOWED = {"components.py", "styles.py"}
    offenders: list[str] = []
    for path in Path("ui").glob("*.py"):
        if path.name in _ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "markdown":
                continue
            if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "st"):
                continue
            for kw in node.keywords:
                if kw.arg == "unsafe_allow_html" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    offenders.append(f"{path}:{node.lineno}")
    assert offenders == []
