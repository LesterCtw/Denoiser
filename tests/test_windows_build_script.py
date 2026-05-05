from __future__ import annotations

from pathlib import Path


def test_windows_build_includes_rosettasciio_dm_lazy_import() -> None:
    script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")

    assert "--hidden-import rsciio.utils._distributed" in script
