"""Single image inspection workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from denoiser.engine import InferenceSettings, should_use_patch_based
from denoiser.image_io import load_image


@dataclass(frozen=True)
class SingleImageInspection:
    source_path: Path
    preview_pixels: np.ndarray
    requires_patch_based_restore: bool


def inspect_single_image(
    path: Path,
    settings: InferenceSettings | None = None,
) -> SingleImageInspection:
    image = load_image(path)
    return SingleImageInspection(
        source_path=image.source_path,
        preview_pixels=image.pixels,
        requires_patch_based_restore=should_use_patch_based(
            image.height,
            image.width,
            settings or InferenceSettings(),
        ),
    )
