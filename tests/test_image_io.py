from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

from denoiser.engine import DenoiseMode
from denoiser.image_io import (
    ImageFormatError,
    is_inside_denoised_folder,
    load_image,
    output_path_for_input,
    output_suffix_for_input,
    prepare_output_pixels,
    save_restored_image,
)


def test_output_suffix_rules() -> None:
    assert output_suffix_for_input(Path("a.tif")) == ".tif"
    assert output_suffix_for_input(Path("a.tiff")) == ".tiff"
    assert output_suffix_for_input(Path("a.png")) == ".png"
    assert output_suffix_for_input(Path("a.jpg")) == ".tif"
    assert output_suffix_for_input(Path("a.jpeg")) == ".tif"
    assert output_suffix_for_input(Path("a.dm3")) == ".tif"
    assert output_suffix_for_input(Path("a.dm4")) == ".tif"


def test_output_path_uses_mode_folder_and_overwrite_name(tmp_path: Path) -> None:
    source = tmp_path / "case" / "wafer01.jpg"
    expected = tmp_path / "case" / "denoised_HRSTEM" / "wafer01.tif"

    assert output_path_for_input(source, DenoiseMode.HRSTEM) == expected


def test_detects_denoised_folder() -> None:
    assert is_inside_denoised_folder(Path("case/denoised_HRSTEM/a.tif"))
    assert is_inside_denoised_folder(Path("case/DENOISED_lrsem/a.tif"))
    assert not is_inside_denoised_folder(Path("case/raw/a.tif"))


def test_load_and_save_uint16_tiff_preserves_dtype_and_clips(tmp_path: Path) -> None:
    source = tmp_path / "wafer.tif"
    original = np.array([[100, 200], [300, 400]], dtype=np.uint16)
    tifffile.imwrite(source, original)

    image = load_image(source)
    restored = np.array([[50.2, 210.4], [390.6, 500.9]], dtype=np.float32)

    output = save_restored_image(image, restored, DenoiseMode.LRSTEM)
    saved = tifffile.imread(output)

    assert output == tmp_path / "denoised_LRSTEM" / "wafer.tif"
    assert saved.dtype == np.uint16
    np.testing.assert_array_equal(saved, np.array([[100, 210], [391, 400]], dtype=np.uint16))


def test_prepare_output_rejects_shape_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.zeros((2, 2), dtype=np.uint8))
    image = load_image(source)

    try:
        prepare_output_pixels(image, np.zeros((3, 3), dtype=np.float32))
    except ImageFormatError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Expected ImageFormatError")


def test_jpeg_saves_as_tiff(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    Image.fromarray(np.array([[10, 20], [30, 40]], dtype=np.uint8)).save(source)

    image = load_image(source)
    output = save_restored_image(image, image.pixels, DenoiseMode.HRSEM)

    assert output == tmp_path / "denoised_HRSEM" / "photo.tif"
    assert tifffile.imread(output).dtype == np.uint8


def test_rgb_input_converts_to_grayscale(tmp_path: Path) -> None:
    source = tmp_path / "rgb.png"
    rgb = np.zeros((1, 1, 3), dtype=np.uint8)
    rgb[0, 0] = [255, 0, 0]
    Image.fromarray(rgb).save(source)

    image = load_image(source)

    assert image.pixels.shape == (1, 1)
    assert image.source_dtype == np.dtype(np.uint8)
    assert image.pixels[0, 0] == 76.0
