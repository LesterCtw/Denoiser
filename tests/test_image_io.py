from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from denoiser.engine import DenoiseMode
from denoiser.image_io import (
    ImageData,
    ImageFormatError,
    SourceKind,
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


def test_save_tiff_preserves_safe_standard_metadata(tmp_path: Path) -> None:
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(
        source,
        np.array([[10, 20], [30, 40]], dtype=np.uint8),
        description="beam=200kV",
        software="scope-control",
        datetime="2025:01:02 03:04:05",
        resolution=((25, 1), (50, 1)),
        resolutionunit="CENTIMETER",
    )

    image = load_image(source)
    output = save_restored_image(image, image.pixels + 1, DenoiseMode.HRSTEM)

    with tifffile.TiffFile(output) as tif:
        tags = tif.pages[0].tags
        assert tags["ImageDescription"].value == "beam=200kV"
        assert tags["Software"].value == "scope-control"
        assert tags["DateTime"].value == "2025:01:02 03:04:05"
        assert tags["XResolution"].value == (25, 1)
        assert tags["YResolution"].value == (50, 1)
        assert tags["ResolutionUnit"].value == 3


def test_tiff_skips_unsupported_metadata_with_note(tmp_path: Path) -> None:
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(
        source,
        np.array([[10, 20], [30, 40]], dtype=np.uint8),
        extratags=[(315, "s", 0, "operator-a", True)],
    )

    image = load_image(source)
    output = save_restored_image(image, image.pixels, DenoiseMode.LRSEM)

    assert "Skipped unsupported TIFF metadata tag: Artist" in image.metadata["metadata_notes"]
    with tifffile.TiffFile(output) as tif:
        assert "Artist" not in tif.pages[0].tags


def test_tiff_skips_shape_description_that_would_conflict_with_output(tmp_path: Path) -> None:
    source = tmp_path / "rgb.tif"
    tifffile.imwrite(source, np.zeros((2, 2, 3), dtype=np.uint8))

    image = load_image(source)
    output = save_restored_image(image, image.pixels, DenoiseMode.HRSEM)

    with tifffile.TiffFile(output) as tif:
        assert "ImageDescription" not in tif.pages[0].tags


def test_dm_source_saves_float32_tiff_without_promising_metadata_parity(tmp_path: Path) -> None:
    image = ImageData(
        source_path=tmp_path / "wafer.dm3",
        pixels=np.array([[1, 2], [3, 4]], dtype=np.float32),
        source_dtype=np.dtype(np.float32),
        source_min=1.0,
        source_max=4.0,
        source_kind=SourceKind.DM,
        metadata={"original_metadata": {"Microscope": "DM"}, "metadata": {"Signal": "STEM"}},
    )

    output = save_restored_image(image, image.pixels + 0.5, DenoiseMode.HRSTEM)

    assert output == tmp_path / "denoised_HRSTEM" / "wafer.tif"
    saved = tifffile.imread(output)
    assert saved.dtype == np.float32
    with tifffile.TiffFile(output) as tif:
        assert "ImageDescription" not in tif.pages[0].tags


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


def test_save_png_preserves_safe_text_metadata(tmp_path: Path) -> None:
    source = tmp_path / "wafer.png"
    pnginfo = PngInfo()
    pnginfo.add_text("Microscope", "SEM-A")
    pnginfo.add_text("OperatorNote", "safe calibration note")
    Image.fromarray(np.array([[10, 20], [30, 40]], dtype=np.uint8)).save(
        source,
        pnginfo=pnginfo,
    )

    image = load_image(source)
    output = save_restored_image(image, image.pixels + 1, DenoiseMode.LRSEM)

    with Image.open(output) as saved:
        assert saved.info["Microscope"] == "SEM-A"
        assert saved.info["OperatorNote"] == "safe calibration note"
        assert np.asarray(saved).dtype == np.uint8


def test_rgb_input_converts_to_grayscale(tmp_path: Path) -> None:
    source = tmp_path / "rgb.png"
    rgb = np.zeros((1, 1, 3), dtype=np.uint8)
    rgb[0, 0] = [255, 0, 0]
    Image.fromarray(rgb).save(source)

    image = load_image(source)

    assert image.pixels.shape == (1, 1)
    assert image.source_dtype == np.dtype(np.uint8)
    assert image.pixels[0, 0] == 76.0
