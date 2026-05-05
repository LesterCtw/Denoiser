from __future__ import annotations

import builtins
import importlib
import sys

import pytest


def import_app_icon_without_pyside6(monkeypatch: pytest.MonkeyPatch):
    original_import = builtins.__import__

    def blocked_import(name: str, *args: object, **kwargs: object):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ModuleNotFoundError("No module named 'PySide6'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    sys.modules.pop("denoiser.app_icon", None)
    return importlib.import_module("denoiser.app_icon")


def test_application_icon_path_is_available_without_pyside6(monkeypatch) -> None:
    app_icon = import_app_icon_without_pyside6(monkeypatch)

    assert app_icon.APP_ICON_RELATIVE_PATH.as_posix() == "assets/icons/denoiser_icon.ico"
    assert app_icon.APP_ICON_SOURCE_RELATIVE_PATH.as_posix() == "assets/icons/denoiser_icon.png"
    assert app_icon.APP_ICON_MACOS_RELATIVE_PATH.as_posix() == "assets/icons/denoiser_icon.icns"
    assert app_icon.application_icon_path() is not None
    assert app_icon.application_icon_source_path() is not None
    assert app_icon.application_macos_icon_path() is not None


def test_application_icon_path_uses_pyinstaller_resource_root(monkeypatch, tmp_path) -> None:
    from denoiser.app_icon import APP_ICON_RELATIVE_PATH, application_icon_path

    bundle_root = tmp_path / "_internal"
    icon_path = bundle_root / APP_ICON_RELATIVE_PATH
    icon_path.parent.mkdir(parents=True)
    icon_path.write_bytes(b"icon")
    monkeypatch.setattr("sys._MEIPASS", str(bundle_root), raising=False)

    assert application_icon_path() == icon_path
