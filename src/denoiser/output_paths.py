"""Restore output path rules."""

from __future__ import annotations

from pathlib import Path

from denoiser.models import DenoiseMode, bundled_model_for


def is_inside_denoised_folder(path: Path) -> bool:
    return any(part.lower().startswith("denoised_") for part in path.parts)


def output_suffix_for_input(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".dm3", ".dm4"}:
        return ".tif"
    return suffix


def output_path_for_input(path: Path, mode: DenoiseMode) -> Path:
    output_dir = path.parent / bundled_model_for(mode).output_folder
    return output_dir / f"{path.stem}{output_suffix_for_input(path)}"
