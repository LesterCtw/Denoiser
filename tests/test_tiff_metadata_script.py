from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

from scripts.inspect_tiff_metadata import format_comparison, format_report, inspect_tiff


def test_inspect_tiff_metadata_reports_standard_pixel_size(tmp_path: Path) -> None:
    source = tmp_path / "measurable.tif"
    tifffile.imwrite(
        source,
        np.zeros((2, 2), dtype=np.uint8),
        resolution=((20_000_000, 1), (10_000_000, 1)),
        resolutionunit="CENTIMETER",
    )

    report = inspect_tiff(source)

    assert report.standard_pixel_size_nm == (0.5, 1.0)
    rendered = format_report(report)
    assert "Standard TIFF pixel size: x=0.5 nm/px, y=1 nm/px" in rendered
    assert "282 XResolution: (20000000, 1)" in rendered
    assert "296 ResolutionUnit: <RESUNIT.CENTIMETER: 3>" in rendered


def test_inspect_tiff_metadata_compares_tag_differences(tmp_path: Path) -> None:
    reference = tmp_path / "reference.tif"
    compared = tmp_path / "compared.tif"
    pixels = np.zeros((2, 2), dtype=np.uint8)
    tifffile.imwrite(
        reference,
        pixels,
        resolution=((20_000_000, 1), (10_000_000, 1)),
        resolutionunit="CENTIMETER",
    )
    tifffile.imwrite(compared, pixels)

    diff = format_comparison(inspect_tiff(reference), inspect_tiff(compared))

    assert "Metadata diff:" in diff
    assert "* 282 XResolution:" in diff
    assert "* 283 YResolution:" in diff
    assert "* 296 ResolutionUnit:" in diff
