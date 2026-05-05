from __future__ import annotations

from pathlib import Path

from scripts.check_dm3_pyinstaller_imports import (
    PYINSTALLER_HIDDEN_IMPORTS,
    REQUIRED_IMPORTS,
)


def test_windows_build_includes_rosettasciio_dm_lazy_import() -> None:
    script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")

    for hidden_import in PYINSTALLER_HIDDEN_IMPORTS:
        assert f"--hidden-import {hidden_import}" in script


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
