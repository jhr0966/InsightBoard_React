from __future__ import annotations

import ast
from pathlib import Path


def test_ui_does_not_render_component_html_through_markdown_unsafe():
    offenders: list[str] = []
    for path in Path("ui").glob("*.py"):
        if path.name == "components.py":
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
