from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import rsciio.digitalmicrograph

from denoiser.image_io import (
    ImageData,
    SourceKind,
    _dm_physical_pixel_size_nm,
    _tiff_resolution_from_pixel_size,
)


MAX_VALUE_LENGTH = 200


@dataclass(frozen=True)
class DmSignalReport:
    path: Path
    signal_index: int
    data_shape: tuple[int, ...]
    data_dtype: str
    axes: tuple[dict[str, Any], ...]
    pixel_size_nm: tuple[float, float] | None
    tiff_resolution: tuple[tuple[int, int], tuple[int, int]] | None


def inspect_dm_file(path: Path) -> tuple[DmSignalReport, ...]:
    path = Path(path)
    signals = rsciio.digitalmicrograph.file_reader(str(path))
    reports: list[DmSignalReport] = []

    for index, signal in enumerate(signals):
        data = signal["data"]
        axes = signal.get("axes", [])
        axes_tuple = tuple(axis for axis in axes if isinstance(axis, dict))

        image = ImageData(
            source_path=path,
            pixels=data,
            source_dtype=data.dtype,
            source_min=0.0,
            source_max=1.0,
            source_kind=SourceKind.DM,
            metadata={"axes": list(axes_tuple)},
        )
        pixel_size = _dm_physical_pixel_size_nm(image)
        resolution = (
            _tiff_resolution_from_pixel_size(pixel_size)
            if pixel_size is not None
            else None
        )

        reports.append(
            DmSignalReport(
                path=path,
                signal_index=index,
                data_shape=tuple(int(value) for value in data.shape),
                data_dtype=str(data.dtype),
                axes=axes_tuple,
                pixel_size_nm=(pixel_size.x, pixel_size.y)
                if pixel_size is not None
                else None,
                tiff_resolution=resolution,
            )
        )

    return tuple(reports)


def format_report(report: DmSignalReport) -> str:
    lines = [
        f"File: {report.path}",
        f"Signal index: {report.signal_index}",
        f"Data shape: {report.data_shape}",
        f"Data dtype: {report.data_dtype}",
        "Axes:",
    ]

    if not report.axes:
        lines.append("  not found")
    else:
        for axis in report.axes:
            lines.append("  - " + _format_axis(axis))

    if report.pixel_size_nm is None:
        lines.append("Denoiser DM pixel size candidate: not found")
    else:
        x_nm, y_nm = report.pixel_size_nm
        lines.append(
            "Denoiser DM pixel size candidate: "
            f"x={_format_number(x_nm)} nm/px, y={_format_number(y_nm)} nm/px"
        )

    if report.tiff_resolution is None:
        lines.append("Denoiser TIFF calibration tags: would not be written")
    else:
        x_resolution, y_resolution = report.tiff_resolution
        lines.append(
            "Denoiser TIFF calibration tags: "
            f"XResolution={x_resolution}, YResolution={y_resolution}, "
            "ResolutionUnit=CENTIMETER"
        )

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect RosettaSciIO DM3/DM4 axes and Denoiser pixel calibration."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="DM3/DM4 files to inspect")
    args = parser.parse_args(argv)

    first = True
    for path in args.paths:
        for report in inspect_dm_file(path):
            if not first:
                print("\n" + "=" * 80 + "\n")
            print(format_report(report))
            first = False

    return 0


def _format_axis(axis: dict[str, Any]) -> str:
    keys = ("name", "size", "index_in_array", "scale", "units", "navigate")
    parts = [f"{key}={_format_value(axis.get(key))}" for key in keys]
    return ", ".join(parts)


def _format_value(value: Any) -> str:
    text = repr(value)
    if len(text) > MAX_VALUE_LENGTH:
        return text[:MAX_VALUE_LENGTH] + "..."
    return text


def _format_number(value: float) -> str:
    return f"{value:.12g}"


if __name__ == "__main__":
    raise SystemExit(main())
