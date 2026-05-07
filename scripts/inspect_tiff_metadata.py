from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import tifffile


MAX_VALUE_LENGTH = 800
NANOMETERS_PER_CENTIMETER = 10_000_000.0
NANOMETERS_PER_INCH = 25_400_000.0
RESOLUTION_UNIT_NAMES = {
    1: "NONE",
    2: "INCH",
    3: "CENTIMETER",
}


@dataclass(frozen=True)
class TagRecord:
    code: int
    name: str
    value: str

    @property
    def key(self) -> str:
        return f"{self.code}:{self.name}"


@dataclass(frozen=True)
class TiffMetadataReport:
    path: Path
    is_imagej: bool
    is_ome: bool
    page_count: int
    series_axes: str
    series_shape: tuple[int, ...]
    standard_pixel_size_nm: tuple[float, float] | None
    imagej_metadata: str | None
    ome_metadata: str | None
    tags: tuple[TagRecord, ...]


def inspect_tiff(path: Path) -> TiffMetadataReport:
    path = Path(path)
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        tags = tuple(
            TagRecord(
                code=int(tag.code),
                name=str(tag.name),
                value=_format_value(tag.value),
            )
            for tag in sorted(page.tags.values(), key=lambda item: int(item.code))
        )

        return TiffMetadataReport(
            path=path,
            is_imagej=bool(tif.is_imagej),
            is_ome=bool(tif.is_ome),
            page_count=len(tif.pages),
            series_axes=str(tif.series[0].axes),
            series_shape=tuple(int(value) for value in tif.series[0].shape),
            standard_pixel_size_nm=_standard_pixel_size_nm(page.tags),
            imagej_metadata=_format_value(tif.imagej_metadata)
            if tif.imagej_metadata is not None
            else None,
            ome_metadata=_format_value(tif.ome_metadata)
            if tif.ome_metadata is not None
            else None,
            tags=tags,
        )


def format_report(report: TiffMetadataReport) -> str:
    lines = [
        f"File: {report.path}",
        f"Pages: {report.page_count}",
        f"Series axes: {report.series_axes}",
        f"Series shape: {report.series_shape}",
        f"ImageJ TIFF: {report.is_imagej}",
        f"OME-TIFF: {report.is_ome}",
    ]

    if report.standard_pixel_size_nm is None:
        lines.append("Standard TIFF pixel size: not found")
    else:
        x_nm, y_nm = report.standard_pixel_size_nm
        lines.append(
            "Standard TIFF pixel size: "
            f"x={_format_number(x_nm)} nm/px, y={_format_number(y_nm)} nm/px"
        )

    if report.imagej_metadata is not None:
        lines.extend(["", "ImageJ metadata:", report.imagej_metadata])

    if report.ome_metadata is not None:
        lines.extend(["", "OME metadata:", report.ome_metadata])

    lines.append("")
    lines.append("TIFF tags:")
    for tag in report.tags:
        lines.append(f"{tag.code} {tag.name}: {tag.value}")

    return "\n".join(lines)


def format_comparison(
    reference: TiffMetadataReport,
    compared: TiffMetadataReport,
) -> str:
    reference_tags = {tag.key: tag for tag in reference.tags}
    compared_tags = {tag.key: tag for tag in compared.tags}
    keys = sorted(set(reference_tags) | set(compared_tags), key=_tag_sort_key)

    lines = [
        f"Metadata diff: {reference.path} -> {compared.path}",
        "Only missing or changed TIFF tags are shown.",
    ]

    differences = 0
    for key in keys:
        left = reference_tags.get(key)
        right = compared_tags.get(key)
        if left is None:
            differences += 1
            lines.append(f"+ {right.code} {right.name}: {right.value}")
        elif right is None:
            differences += 1
            lines.append(f"- {left.code} {left.name}: {left.value}")
        elif left.value != right.value:
            differences += 1
            lines.append(f"* {left.code} {left.name}:")
            lines.append(f"  reference: {left.value}")
            lines.append(f"  compared:  {right.value}")

    if differences == 0:
        lines.append("No TIFF tag differences.")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect TIFF metadata and compare tags between measurable and output TIFF files."
        )
    )
    parser.add_argument("paths", nargs="+", type=Path, help="TIFF files to inspect")
    args = parser.parse_args(argv)

    reports = [inspect_tiff(path) for path in args.paths]
    for index, report in enumerate(reports):
        if index:
            print("\n" + "=" * 80 + "\n")
        print(format_report(report))

    if len(reports) > 1:
        reference = reports[0]
        for report in reports[1:]:
            print("\n" + "=" * 80 + "\n")
            print(format_comparison(reference, report))

    return 0


def _standard_pixel_size_nm(tags: tifffile.TiffTags) -> tuple[float, float] | None:
    resolution_unit = tags.get("ResolutionUnit")
    x_resolution = tags.get("XResolution")
    y_resolution = tags.get("YResolution")
    if resolution_unit is None or x_resolution is None or y_resolution is None:
        return None

    try:
        unit_code = int(resolution_unit.value)
    except (TypeError, ValueError):
        return None

    if unit_code == 2:
        unit_nm = NANOMETERS_PER_INCH
    elif unit_code == 3:
        unit_nm = NANOMETERS_PER_CENTIMETER
    else:
        return None

    x_pixels_per_unit = _resolution_value(x_resolution.value)
    y_pixels_per_unit = _resolution_value(y_resolution.value)
    if x_pixels_per_unit is None or y_pixels_per_unit is None:
        return None

    return (unit_nm / x_pixels_per_unit, unit_nm / y_pixels_per_unit)


def _resolution_value(value: Any) -> float | None:
    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        try:
            result = float(numerator) / float(denominator)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    else:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None

    if result <= 0:
        return None
    return result


def _format_value(value: Any) -> str:
    if isinstance(value, bytes):
        value = value[:MAX_VALUE_LENGTH]
    text = repr(value)
    if len(text) > MAX_VALUE_LENGTH:
        return text[:MAX_VALUE_LENGTH] + "..."
    return text


def _format_number(value: float) -> str:
    return f"{value:.12g}"


def _tag_sort_key(key: str) -> tuple[int, str]:
    code, name = key.split(":", maxsplit=1)
    return (int(code), name)


if __name__ == "__main__":
    raise SystemExit(main())
