"""Application icon helpers."""

from __future__ import annotations

from pathlib import Path

from denoiser.runtime_paths import resource_path

APP_ICON_RELATIVE_PATH = Path("assets/icons/denoiser_icon.ico")


def application_icon_path() -> Path | None:
    candidate = resource_path(APP_ICON_RELATIVE_PATH)
    if candidate.is_file():
        return candidate
    return None
