from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from denoiser.app_icon import APP_ICON_RELATIVE_PATH, application_icon_path, load_application_icon


def test_application_icon_exists_at_expected_project_path() -> None:
    assert APP_ICON_RELATIVE_PATH.as_posix() == "assets/icons/denoiser_icon.ico"
    assert application_icon_path() is not None


def test_application_icon_loads_in_qt() -> None:
    QApplication.instance() or QApplication([])

    icon = load_application_icon()

    assert not icon.isNull()
    assert icon.availableSizes()


def test_application_icon_path_uses_pyinstaller_resource_root(monkeypatch, tmp_path) -> None:
    bundle_root = tmp_path / "_internal"
    icon_path = bundle_root / APP_ICON_RELATIVE_PATH
    icon_path.parent.mkdir(parents=True)
    icon_path.write_bytes(b"icon")
    monkeypatch.setattr("sys._MEIPASS", str(bundle_root), raising=False)

    assert application_icon_path() == icon_path
