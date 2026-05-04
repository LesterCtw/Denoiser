"""Application icon helpers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

from denoiser.runtime_paths import resource_path

APP_ICON_RELATIVE_PATH = Path("assets/icons/denoiser_icon.ico")


def application_icon_path() -> Path | None:
    candidate = resource_path(APP_ICON_RELATIVE_PATH)
    if candidate.is_file():
        return candidate
    return None


def load_application_icon() -> QIcon:
    icon_path = application_icon_path()
    if icon_path is None:
        return QIcon()
    return QIcon(str(icon_path))
