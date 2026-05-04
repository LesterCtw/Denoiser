from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image

from denoiser.models import DenoiseMode
from denoiser.image_io import ImageFormatError
from denoiser.workflow import restore_single_image


def test_restore_single_image_saves_restored_output_with_selected_mode(tmp_path: Path) -> None:
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):
            assert mode is DenoiseMode.HRSEM
            return pixels + 5

    result = restore_single_image(source, DenoiseMode.HRSEM, FakeEngine())

    assert result.output_path == tmp_path / "denoised_HRSEM" / "wafer.tif"
    assert result.mode is DenoiseMode.HRSEM
    np.testing.assert_array_equal(result.raw_pixels, np.array([[10, 20], [30, 40]], dtype=np.float32))
    np.testing.assert_array_equal(result.restored_pixels, result.raw_pixels + 5)
    np.testing.assert_array_equal(
        tifffile.imread(result.output_path),
        np.array([[15, 25], [35, 40]], dtype=np.uint8),
    )


def test_restore_single_image_rejects_multi_page_tiff_before_engine(tmp_path: Path) -> None:
    source = tmp_path / "stack.tif"
    tifffile.imwrite(source, np.zeros((3, 4), dtype=np.uint8))
    tifffile.imwrite(source, np.ones((3, 4), dtype=np.uint8), append=True)

    class EngineShouldNotRun:
        def restore(self, pixels, mode):
            raise AssertionError("Engine should not run for multi-page TIFF input")

    with pytest.raises(ImageFormatError, match="Multi-page TIFF"):
        restore_single_image(source, DenoiseMode.HRSTEM, EngineShouldNotRun())


def test_restore_single_image_rejects_stack_like_tiff_before_engine(tmp_path: Path) -> None:
    source = tmp_path / "stack_like.tif"
    tifffile.imwrite(
        source,
        np.zeros((2, 3, 4), dtype=np.uint8),
        metadata={"axes": "ZYX"},
    )

    class EngineShouldNotRun:
        def restore(self, pixels, mode):
            raise AssertionError("Engine should not run for stack-like TIFF input")

    with pytest.raises(ImageFormatError, match="Stack-like TIFF"):
        restore_single_image(source, DenoiseMode.HRSTEM, EngineShouldNotRun())


@pytest.mark.parametrize(
    ("filename", "expected_filename"),
    [
        ("wafer.jpg", "wafer.tif"),
        ("wafer.png", "wafer.png"),
        ("wafer.tiff", "wafer.tiff"),
    ],
)
def test_restore_single_image_uses_output_format_rules(
    tmp_path: Path,
    filename: str,
    expected_filename: str,
) -> None:
    source = tmp_path / filename
    pixels = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    if source.suffix == ".tiff":
        tifffile.imwrite(source, pixels)
    else:
        Image.fromarray(pixels).save(source)

    class FakeEngine:
        def restore(self, pixels, mode):
            return pixels

    result = restore_single_image(source, DenoiseMode.HRSTEM, FakeEngine())

    assert result.output_path == tmp_path / "denoised_HRSTEM" / expected_filename
    assert result.output_path.is_file()


def test_restore_single_image_converts_rgba_to_grayscale_without_alpha(tmp_path: Path) -> None:
    source = tmp_path / "rgba.png"
    rgba = np.array([[[255, 0, 0, 0], [0, 255, 0, 255]]], dtype=np.uint8)
    Image.fromarray(rgba).save(source)

    class FakeEngine:
        def restore(self, pixels, mode):
            np.testing.assert_array_equal(pixels, np.array([[76, 149]], dtype=np.float32))
            return pixels

    result = restore_single_image(source, DenoiseMode.LRSTEM, FakeEngine())

    saved = np.asarray(Image.open(result.output_path))
    assert saved.ndim == 2
    np.testing.assert_array_equal(saved, np.array([[76, 149]], dtype=np.uint8))


def test_restore_single_image_rejects_unsupported_input_before_engine(tmp_path: Path) -> None:
    source = tmp_path / "wafer.bmp"
    Image.fromarray(np.zeros((2, 2), dtype=np.uint8)).save(source)

    class EngineShouldNotRun:
        def restore(self, pixels, mode):
            raise AssertionError("Engine should not run for unsupported input")

    with pytest.raises(ImageFormatError, match="Unsupported file format"):
        restore_single_image(source, DenoiseMode.HRSTEM, EngineShouldNotRun())


def test_restore_single_image_rejects_denoised_input_before_engine(tmp_path: Path) -> None:
    source_dir = tmp_path / "denoised_HRSTEM"
    source_dir.mkdir()
    source = source_dir / "wafer.tif"
    tifffile.imwrite(source, np.zeros((2, 2), dtype=np.uint8))

    class EngineShouldNotRun:
        def restore(self, pixels, mode):
            raise AssertionError("Engine should not run for denoised_* input")

    with pytest.raises(ImageFormatError, match="denoised_"):
        restore_single_image(source, DenoiseMode.HRSTEM, EngineShouldNotRun())


def test_restore_single_image_overwrites_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))
    output = tmp_path / "denoised_HRSEM" / "wafer.tif"
    output.parent.mkdir()
    tifffile.imwrite(output, np.full((2, 2), 99, dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):
            return np.full_like(pixels, 15)

    result = restore_single_image(source, DenoiseMode.HRSEM, FakeEngine())

    assert result.output_path == output
    np.testing.assert_array_equal(tifffile.imread(output), np.full((2, 2), 15, dtype=np.uint8))
