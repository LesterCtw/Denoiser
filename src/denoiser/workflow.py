"""User-facing restore workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from denoiser.engine import DenoiseMode
from denoiser.image_io import load_image, save_restored_image


class RestoreEngine(Protocol):
    def restore(self, pixels: np.ndarray, mode: DenoiseMode) -> np.ndarray: ...


@dataclass(frozen=True)
class SingleRestoreResult:
    source_path: Path
    output_path: Path
    mode: DenoiseMode
    raw_pixels: np.ndarray
    restored_pixels: np.ndarray


def restore_single_image(path: Path, mode: DenoiseMode, engine: RestoreEngine) -> SingleRestoreResult:
    image = load_image(path)
    restored_pixels = engine.restore(image.pixels, mode)
    output_path = save_restored_image(image, restored_pixels, mode)

    return SingleRestoreResult(
        source_path=image.source_path,
        output_path=output_path,
        mode=mode,
        raw_pixels=image.pixels,
        restored_pixels=restored_pixels,
    )
