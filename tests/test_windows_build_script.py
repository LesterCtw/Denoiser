from __future__ import annotations

import tomllib
from pathlib import Path

from scripts.check_dm3_pyinstaller_imports import (
    PYINSTALLER_HIDDEN_IMPORTS,
    REQUIRED_IMPORTS,
)


def test_release_dependency_flow_uses_nicegui_native_window_not_pyside6() -> None:
    script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    lockfile = Path("uv.lock").read_text(encoding="utf-8").lower()
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    for dependency in ['"nicegui>=2.0"', '"pywebview>=5.0"']:
        assert f"python -m pip install {dependency}" in script

    assert 'python -m pip install "PySide6>=6.7"' not in script
    assert "PySide6" not in requirements
    assert "PySide6>=6.7" not in pyproject["project"]["dependencies"]
    assert all(
        "PySide6" not in dependency
        for dependencies in pyproject["project"]["optional-dependencies"].values()
        for dependency in dependencies
    )
    assert "pyside6" not in lockfile
    assert "shiboken6" not in lockfile


def test_windows_build_includes_rosettasciio_dm_lazy_import() -> None:
    script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")

    for hidden_import in PYINSTALLER_HIDDEN_IMPORTS:
        assert f"--hidden-import {hidden_import}" in script


def test_windows_build_packages_nicegui_app_and_bundled_resources() -> None:
    script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")

    for option in [
        "--onedir",
        "--windowed",
        "--name Denoiser",
        "--icon \"$iconPath\"",
        "--collect-data nicegui",
        "--add-data \"assets;assets\"",
        "--add-data \"models;models\"",
        "--add-data \"licenses;licenses\"",
        "src\\denoiser\\app.py",
    ]:
        assert option in script


def test_dm3_pyinstaller_probe_covers_required_import_chain() -> None:
    assert REQUIRED_IMPORTS == [
        "rsciio.digitalmicrograph",
        "rsciio.digitalmicrograph._api",
        "rsciio.utils.file",
        "rsciio.utils._distributed",
        "dask.array",
        "box",
        "dateutil.parser",
        "pint",
        "yaml",
    ]


def test_dm3_pyinstaller_hidden_imports_cover_lazy_dependencies() -> None:
    assert PYINSTALLER_HIDDEN_IMPORTS == [
        "rsciio.utils._distributed",
        "pint",
        "yaml",
    ]
