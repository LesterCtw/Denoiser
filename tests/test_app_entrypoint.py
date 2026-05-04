from __future__ import annotations

import ast
from pathlib import Path


def test_pyinstaller_app_script_calls_main_when_executed() -> None:
    source = Path("src/denoiser/app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and ast.unparse(node.test) == "__name__ == '__main__'"
        for node in tree.body
    )
