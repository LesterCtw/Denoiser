from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

from denoiser.image_io import ImageFormatError
from denoiser.single_image_inspection import inspect_single_image


def test_single_image_inspection_loads_preview_pixels_and_patch_requirement(
    tmp_path: Path,
) -> None:
    source = tmp_path / "large.tif"
    tifffile.imwrite(source, np.zeros((1537, 1), dtype=np.uint8))

    inspection = inspect_single_image(source)

    assert inspection.source_path == source
    assert inspection.preview_pixels.shape == (1537, 1)
    assert inspection.requires_patch_based_restore


def test_single_image_inspection_rejects_unsupported_input(tmp_path: Path) -> None:
    source = tmp_path / "wafer.bmp"
    source.write_bytes(b"not used")

    try:
        inspect_single_image(source)
    except ImageFormatError as exc:
        assert "Unsupported file format" in str(exc)
    else:
        raise AssertionError("Expected ImageFormatError")


def test_single_image_inspection_rejects_denoised_folder_input(tmp_path: Path) -> None:
    folder = tmp_path / "denoised_HRSTEM"
    folder.mkdir()
    source = folder / "wafer.tif"
    tifffile.imwrite(source, np.zeros((2, 2), dtype=np.uint8))

    try:
        inspect_single_image(source)
    except ImageFormatError as exc:
        assert "denoised_* folders" in str(exc)
    else:
        raise AssertionError("Expected ImageFormatError")
