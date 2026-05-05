from __future__ import annotations

import ast
from pathlib import Path


def test_frontend_adr_supersedes_pyside6_with_nicegui_native_window() -> None:
    adr_texts = [
        path.read_text(encoding="utf-8")
        for path in Path("docs/adr").glob("*.md")
    ]

    matching_adrs = [
        text
        for text in adr_texts
        if "NiceGUI native window" in text and "Supersedes ADR 0001" in text
    ]

    assert matching_adrs, "Expected an ADR superseding PySide6 with NiceGUI native window"
    adr = matching_adrs[0]

    assert "## Status\n\nAccepted" in adr
    assert "standard Windows title bar" in adr
    assert "DESIGN.md" in adr
    assert "no PySide6 fallback" in adr
    assert "PyInstaller" in adr


def test_readme_documents_nicegui_frontend_contract_and_preserves_mvs_scope() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "NiceGUI native window" in readme
    assert "repo `DESIGN.md`" in readme
    assert "standard Windows title bar" in readme
    assert "no PySide6 fallback" in readme
    assert "PyInstaller" in readme
    assert "PySide6 application entry point 和基本 main window" not in readme
    assert "PySide6 只保留給舊 frontend 測試與開發支援" not in readme

    for mvs_contract in [
        "Single",
        "Batch",
        "CPU only",
        "Offline use",
        "bundled ONNX models",
        "UI language：English",
    ]:
        assert mvs_contract in readme


def test_context_current_assumptions_use_nicegui_frontend_direction() -> None:
    context = Path("CONTEXT.md").read_text(encoding="utf-8")

    assert "implemented frontend is NiceGUI native window" in context
    assert "standard Windows title bar" in context
    assert "DESIGN.md" in context
    assert "no PySide6 fallback" in context
    assert "The frontend will use PySide6" not in context


def test_original_pyside6_adr_points_to_superseding_nicegui_adr() -> None:
    pyside6_adr = Path(
        "docs/adr/0001-use-pyside6-for-windows-desktop-ui.md"
    ).read_text(encoding="utf-8")

    assert "## Status\n\nSuperseded by ADR 0004" in pyside6_adr


def test_current_frontend_source_tree_has_no_legacy_pyside6_stack() -> None:
    assert not Path("src/denoiser/ui").exists()

    offenders: list[str] = []
    for root in [Path("src"), Path("tests")]:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue

                if any(
                    name == "PySide6"
                    or name.startswith("PySide6.")
                    or name == "denoiser.ui"
                    or name.startswith("denoiser.ui.")
                    for name in names
                ):
                    offenders.append(str(path))

    assert offenders == []


def test_windows_release_docs_describe_nicegui_package_flow() -> None:
    build_guide = Path("docs/windows-build-and-package.md").read_text(
        encoding="utf-8"
    )
    verification = Path("docs/windows-release-verification.md").read_text(
        encoding="utf-8"
    )
    combined = build_guide + "\n" + verification

    assert 'python -m pip install "nicegui>=2.0"' in build_guide
    assert 'python -m pip install "pywebview>=5.0"' in build_guide
    assert 'python -m pip install "PySide6>=6.7"' not in combined
    assert "NiceGUI native window" in combined
    assert "Single image dialog" in verification
    assert "Batch folder dialog" in verification
    assert "Batch restore smoke test" in verification
    assert "_internal\\models\\sfr_hrstem.onnx" in verification
    assert "_internal\\licenses\\THIRD_PARTY_NOTICES.md" in verification
