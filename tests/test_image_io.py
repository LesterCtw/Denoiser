from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rsciio.digitalmicrograph
import tifffile
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from denoiser.models import DenoiseMode
from denoiser.image_io import (
    ImageData,
    ImageFormatError,
    SourceKind,
    image_dimensions,
    load_image,
    prepare_output_pixels,
    save_restored_image,
)


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


def test_save_tiff_preserves_common_text_metadata_tags(tmp_path: Path) -> None:
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(
        source,
        np.array([[10, 20], [30, 40]], dtype=np.uint8),
        extratags=[
            (269, "s", 0, "doc-name", True),
            (285, "s", 0, "page-name", True),
            (271, "s", 0, "scope-maker", True),
            (272, "s", 0, "scope-model", True),
            (315, "s", 0, "operator-a", True),
            (316, "s", 0, "host-a", True),
            (33432, "s", 0, "copyright-a", True),
        ],
    )

    image = load_image(source)
    output = save_restored_image(image, image.pixels, DenoiseMode.LRSEM)

    with tifffile.TiffFile(output) as tif:
        tags = tif.pages[0].tags
        assert tags["DocumentName"].value == "doc-name"
        assert tags["PageName"].value == "page-name"
        assert tags["Make"].value == "scope-maker"
        assert tags["Model"].value == "scope-model"
        assert tags["Artist"].value == "operator-a"
        assert tags["HostComputer"].value == "host-a"
        assert tags["Copyright"].value == "copyright-a"


def test_tiff_skips_shape_description_that_would_conflict_with_output(tmp_path: Path) -> None:
    source = tmp_path / "rgb.tif"
    tifffile.imwrite(source, np.zeros((2, 2, 3), dtype=np.uint8))

    image = load_image(source)
    output = save_restored_image(image, image.pixels, DenoiseMode.HRSEM)

    with tifffile.TiffFile(output) as tif:
        assert "ImageDescription" not in tif.pages[0].tags


def test_ome_tiff_pixel_size_is_exported_as_standard_resolution_tags(tmp_path: Path) -> None:
    source = tmp_path / "ome.tif"
    tifffile.imwrite(
        source,
        np.array([[10, 20], [30, 40]], dtype=np.uint16),
        ome=True,
        metadata={
            "axes": "YX",
            "PhysicalSizeX": 0.5,
            "PhysicalSizeXUnit": "um",
            "PhysicalSizeY": 1.25,
            "PhysicalSizeYUnit": "um",
        },
    )

    image = load_image(source)
    output = save_restored_image(image, image.pixels + 1, DenoiseMode.HRSEM)

    with tifffile.TiffFile(output) as tif:
        tags = tif.pages[0].tags
        assert not tif.is_ome
        assert "ImageDescription" not in tags
        assert tags["XResolution"].value == (20000, 1)
        assert tags["YResolution"].value == (8000, 1)
        assert tags["ResolutionUnit"].value == 3


def test_tiff_skips_ome_description_after_rgb_to_grayscale(tmp_path: Path) -> None:
    source = tmp_path / "rgb_ome.tif"
    tifffile.imwrite(
        source,
        np.zeros((2, 2, 3), dtype=np.uint8),
        photometric="rgb",
        ome=True,
        metadata={
            "axes": "YXS",
            "PhysicalSizeX": 0.5,
            "PhysicalSizeXUnit": "um",
            "PhysicalSizeY": 1.25,
            "PhysicalSizeYUnit": "um",
        },
    )

    image = load_image(source)
    output = save_restored_image(image, image.pixels, DenoiseMode.HRSEM)

    with tifffile.TiffFile(output) as tif:
        assert not tif.is_ome
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


def test_dm_source_exports_nm_pixel_size_as_standard_resolution_tags(tmp_path: Path) -> None:
    image = ImageData(
        source_path=tmp_path / "wafer.dm3",
        pixels=np.array([[1, 2], [3, 4]], dtype=np.float32),
        source_dtype=np.dtype(np.float32),
        source_min=1.0,
        source_max=4.0,
        source_kind=SourceKind.DM,
        metadata={
            "axes": [
                {
                    "name": "y",
                    "size": 2,
                    "index_in_array": 0,
                    "scale": 1.25,
                    "units": "nm",
                    "navigate": False,
                },
                {
                    "name": "x",
                    "size": 2,
                    "index_in_array": 1,
                    "scale": 0.5,
                    "units": "nm",
                    "navigate": False,
                },
            ],
        },
    )

    output = save_restored_image(image, image.pixels, DenoiseMode.HRSTEM)

    with tifffile.TiffFile(output) as tif:
        tags = tif.pages[0].tags
        assert not tif.is_imagej
        assert tags["XResolution"].value == (20000000, 1)
        assert tags["YResolution"].value == (8000000, 1)
        assert tags["ResolutionUnit"].value == 3


def test_load_dm_image_keeps_reader_axes_for_output_metadata(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    source = tmp_path / "wafer.dm3"
    source.write_bytes(b"synthetic placeholder")

    def fake_file_reader(filename: str) -> list[dict[str, Any]]:
        assert filename == str(source)
        return [
            {
                "data": np.array([[1, 2], [3, 4]], dtype=np.float32),
                "metadata": {},
                "original_metadata": {},
                "axes": [
                    {
                        "name": "y",
                        "size": 2,
                        "index_in_array": 0,
                        "scale": 0.001,
                        "units": "um",
                        "navigate": False,
                    },
                    {
                        "name": "x",
                        "size": 2,
                        "index_in_array": 1,
                        "scale": 0.0005,
                        "units": "um",
                        "navigate": False,
                    },
                ],
            }
        ]

    monkeypatch.setattr(rsciio.digitalmicrograph, "file_reader", fake_file_reader)

    image = load_image(source)
    output = save_restored_image(image, image.pixels, DenoiseMode.HRSEM)

    with tifffile.TiffFile(output) as tif:
        tags = tif.pages[0].tags
        assert not tif.is_imagej
        assert tags["XResolution"].value == (20000000, 1)
        assert tags["YResolution"].value == (10000000, 1)
        assert tags["ResolutionUnit"].value == 3


def test_imagej_tiff_pixel_size_is_exported_as_standard_resolution_tags(tmp_path: Path) -> None:
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(
        source,
        np.array([[10, 20], [30, 40]], dtype=np.uint8),
        imagej=True,
        resolution=(2.0, 1.0),
        metadata={"unit": "nm"},
    )

    image = load_image(source)
    output = save_restored_image(image, image.pixels + 1, DenoiseMode.HRSTEM)

    with tifffile.TiffFile(output) as tif:
        tags = tif.pages[0].tags
        assert not tif.is_imagej
        assert tags["XResolution"].value == (20000000, 1)
        assert tags["YResolution"].value == (10000000, 1)
        assert tags["ResolutionUnit"].value == 3


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


def test_load_image_rejects_single_page_stack_like_tiff(tmp_path: Path) -> None:
    source = tmp_path / "stack_like.tif"
    tifffile.imwrite(
        source,
        np.zeros((2, 3, 4), dtype=np.uint8),
        metadata={"axes": "ZYX"},
    )

    try:
        load_image(source)
    except ImageFormatError as exc:
        assert "Stack-like TIFF" in str(exc)
    else:
        raise AssertionError("Expected ImageFormatError")


def test_image_dimensions_rejects_single_page_stack_like_tiff(tmp_path: Path) -> None:
    source = tmp_path / "stack_like.tif"
    tifffile.imwrite(
        source,
        np.zeros((2, 3, 4), dtype=np.uint8),
        metadata={"axes": "ZYX"},
    )

    try:
        image_dimensions(source)
    except ImageFormatError as exc:
        assert "Stack-like TIFF" in str(exc)
    else:
        raise AssertionError("Expected ImageFormatError")
