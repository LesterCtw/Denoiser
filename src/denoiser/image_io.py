"""Image input/output boundary for Denoiser.

Implementation will preserve saved intensity scale and avoid applying preview
normalization to output files.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import numpy as np
import tifffile
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from denoiser.models import DenoiseMode
from denoiser.output_paths import is_inside_denoised_folder, output_path_for_input


SUPPORTED_INPUT_EXTENSIONS = {
    ".tif",
    ".tiff",
    ".png",
    ".jpg",
    ".jpeg",
    ".dm3",
    ".dm4",
}

COMMON_TIFF_TEXT_TAGS = {
    "Artist": 315,
    "Copyright": 33432,
    "DocumentName": 269,
    "HostComputer": 316,
    "Make": 271,
    "Model": 272,
    "PageName": 285,
}

LENGTH_UNITS_TO_NM = {
    "nm": 1.0,
    "nanometer": 1.0,
    "nanometers": 1.0,
    "um": 1000.0,
    "\u00b5m": 1000.0,
    "\u03bcm": 1000.0,
    "micron": 1000.0,
    "microns": 1000.0,
    "micrometer": 1000.0,
    "micrometers": 1000.0,
}


class ImageFormatError(ValueError):
    """Raised when an input image cannot be safely processed by the MVS."""


class SourceKind(str, Enum):
    STANDARD = "standard"
    DM = "dm"


@dataclass(frozen=True)
class ImageData:
    source_path: Path
    pixels: np.ndarray
    source_dtype: np.dtype[Any]
    source_min: float
    source_max: float
    source_kind: SourceKind
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])


@dataclass(frozen=True)
class _PhysicalPixelSizeNm:
    x: float
    y: float


def is_supported_input(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS


def image_dimensions(path: Path) -> tuple[int, int]:
    path = Path(path)
    if not is_supported_input(path):
        raise ImageFormatError(f"Unsupported file format: {path.suffix}")
    if is_inside_denoised_folder(path):
        raise ImageFormatError("Refusing to inspect files inside denoised_* folders.")

    suffix = path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        with tifffile.TiffFile(path) as tif:
            series = _single_2d_tiff_series(tif)
            return int(series.shape[0]), int(series.shape[1])
    if suffix in {".dm3", ".dm4"}:
        image = load_image(path)
        return image.height, image.width

    with Image.open(path) as img:
        width, height = img.size
    return int(height), int(width)


def load_image(path: Path) -> ImageData:
    path = Path(path)
    if not is_supported_input(path):
        raise ImageFormatError(f"Unsupported file format: {path.suffix}")
    if is_inside_denoised_folder(path):
        raise ImageFormatError("Refusing to process files inside denoised_* folders.")

    suffix = path.suffix.lower()
    if suffix in {".dm3", ".dm4"}:
        return _load_dm_image(path)
    if suffix in {".tif", ".tiff"}:
        return _load_tiff_image(path)
    return _load_pillow_image(path)


def save_restored_image(image: ImageData, restored_pixels: np.ndarray, mode: DenoiseMode) -> Path:
    output_path = output_path_for_input(image.source_path, mode)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = prepare_output_pixels(image, restored_pixels)
    if output_path.suffix.lower() in {".tif", ".tiff"}:
        tifffile.imwrite(
            output_path,
            output,
            photometric="minisblack",
            **_tiff_write_options(image),
        )
    elif output_path.suffix.lower() == ".png":
        Image.fromarray(output).save(output_path, **_png_write_options(image))
    else:
        raise ImageFormatError(f"Unsupported output format: {output_path.suffix}")

    return output_path


def prepare_output_pixels(image: ImageData, restored_pixels: np.ndarray) -> np.ndarray:
    restored = np.asarray(restored_pixels)
    if restored.shape != image.pixels.shape:
        raise ImageFormatError(
            f"Restored image shape {restored.shape} does not match input shape {image.pixels.shape}."
        )

    clipped = np.clip(restored.astype(np.float32, copy=False), image.source_min, image.source_max)

    if image.source_kind is SourceKind.DM:
        return clipped.astype(np.float32, copy=False)

    dtype = image.source_dtype
    if np.issubdtype(dtype, np.integer):
        clipped = np.rint(clipped)
        info = np.iinfo(dtype)
        clipped = np.clip(clipped, info.min, info.max)
    return clipped.astype(dtype, copy=False)


def _load_pillow_image(path: Path) -> ImageData:
    with Image.open(path) as img:
        metadata = _safe_png_metadata(img.info) if path.suffix.lower() == ".png" else {}
        array = np.asarray(img)
    return _image_data_from_array(path, array, SourceKind.STANDARD, metadata=metadata)


def _load_tiff_image(path: Path) -> ImageData:
    with tifffile.TiffFile(path) as tif:
        series = _single_2d_tiff_series(tif)
        metadata = _safe_tiff_metadata(tif.pages[0].tags, series.axes)
        array = series.asarray()
    return _image_data_from_array(path, array, SourceKind.STANDARD, metadata=metadata)


def _single_2d_tiff_series(tif: tifffile.TiffFile) -> Any:
    if len(tif.pages) > 1:
        raise ImageFormatError(
            "Multi-page TIFF files are not supported. Use a single 2D image."
        )

    series = tif.series[0]
    if series.axes not in {"YX", "YXS"}:
        raise ImageFormatError(
            f"Stack-like TIFF data is not supported: {series.shape}. "
            "Use a single 2D image."
        )
    return series


def _load_dm_image(path: Path) -> ImageData:
    from rsciio.digitalmicrograph import file_reader

    signals = file_reader(str(path))
    if not signals:
        raise ImageFormatError(f"No image data found in {path.name}.")

    signal = signals[0]
    metadata = {
        "original_metadata": signal.get("original_metadata", {}),
        "metadata": signal.get("metadata", {}),
        "axes": signal.get("axes", []),
    }
    return _image_data_from_array(path, signal["data"], SourceKind.DM, metadata=metadata)


def _safe_tiff_metadata(tags: tifffile.TiffTags, series_axes: str) -> dict[str, Any]:
    safe_metadata: dict[str, Any] = {}
    notes: list[str] = []

    description = tags.get("ImageDescription")
    if description is not None and isinstance(description.value, str):
        if _is_safe_tiff_description(description.value, series_axes):
            safe_metadata["description"] = description.value
        else:
            notes.append("Skipped unsafe TIFF metadata tag: ImageDescription")

    for tag_name, metadata_key in (
        ("Software", "software"),
        ("DateTime", "datetime"),
    ):
        tag = tags.get(tag_name)
        if tag is not None and isinstance(tag.value, str):
            safe_metadata[metadata_key] = tag.value

    resolution_unit = tags.get("ResolutionUnit")
    if resolution_unit is not None and isinstance(resolution_unit.value, int):
        safe_metadata["resolutionunit"] = resolution_unit.value

    x_resolution = tags.get("XResolution")
    y_resolution = tags.get("YResolution")
    if x_resolution is not None and y_resolution is not None:
        safe_metadata["resolution"] = (x_resolution.value, y_resolution.value)

    text_tags: dict[str, str] = {}
    for tag_name in COMMON_TIFF_TEXT_TAGS:
        tag = tags.get(tag_name)
        if tag is not None and isinstance(tag.value, str):
            text_tags[tag_name] = tag.value
    if text_tags:
        safe_metadata["text_tags"] = text_tags

    metadata: dict[str, Any] = {"tiff": safe_metadata}
    if notes:
        metadata["metadata_notes"] = notes
    return metadata


def _is_safe_tiff_description(value: str, series_axes: str) -> bool:
    if _is_ome_tiff_description(value) and series_axes != "YX":
        return False

    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return True
    return not (isinstance(decoded, dict) and "shape" in decoded)


def _is_ome_tiff_description(value: str) -> bool:
    return "<OME " in value[:512] or "<OME>" in value[:512]


def _tiff_write_options(image: ImageData) -> dict[str, Any]:
    options: dict[str, Any] = {"metadata": None}

    if image.source_kind is SourceKind.DM:
        pixel_size = _dm_physical_pixel_size_nm(image)
        if pixel_size is None:
            return options
        return {
            "imagej": True,
            "metadata": {"unit": "nm"},
            "resolution": (
                _pixels_per_nm_resolution(pixel_size.x),
                _pixels_per_nm_resolution(pixel_size.y),
            ),
            "resolutionunit": "NONE",
        }

    if image.source_kind is not SourceKind.STANDARD:
        return options

    tiff_metadata = image.metadata.get("tiff", {})
    if not isinstance(tiff_metadata, dict):
        return options

    for key in ("description", "software", "datetime", "resolution", "resolutionunit"):
        if key in tiff_metadata:
            options[key] = tiff_metadata[key]

    text_tags = tiff_metadata.get("text_tags", {})
    if isinstance(text_tags, dict):
        extratags = _tiff_text_extratags(text_tags)
        if extratags:
            options["extratags"] = extratags

    return options


def _tiff_text_extratags(text_tags: dict[Any, Any]) -> list[tuple[int, str, int, str, bool]]:
    extratags: list[tuple[int, str, int, str, bool]] = []
    for tag_name, tag_code in COMMON_TIFF_TEXT_TAGS.items():
        value = text_tags.get(tag_name)
        if isinstance(value, str):
            extratags.append((tag_code, "s", 0, value, True))
    return extratags


def _dm_physical_pixel_size_nm(image: ImageData) -> _PhysicalPixelSizeNm | None:
    axes = image.metadata.get("axes")
    if not isinstance(axes, list) or image.pixels.ndim != 2:
        return None

    shape = image.pixels.shape
    y_axis = _dm_axis_for_dimension(axes, shape, 0, "y")
    x_axis = _dm_axis_for_dimension(axes, shape, 1, "x")
    if x_axis is None or y_axis is None:
        return None

    x_scale = _axis_scale_nm_per_pixel(x_axis)
    y_scale = _axis_scale_nm_per_pixel(y_axis)
    if x_scale is None or y_scale is None:
        return None

    return _PhysicalPixelSizeNm(x=x_scale, y=y_scale)


def _dm_axis_for_dimension(
    axes: list[Any],
    shape: tuple[int, int],
    dimension_index: int,
    axis_name: str,
) -> dict[str, Any] | None:
    named_axis = _first_matching_axis(
        axes,
        shape,
        dimension_index,
        lambda axis: _axis_name(axis) == axis_name,
    )
    if named_axis is not None:
        return named_axis

    return _first_matching_axis(
        axes,
        shape,
        dimension_index,
        lambda axis: _axis_index(axis) == dimension_index,
    )


def _first_matching_axis(
    axes: list[Any],
    shape: tuple[int, int],
    dimension_index: int,
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any] | None:
    for axis in axes:
        if (
            isinstance(axis, dict)
            and predicate(axis)
            and _axis_matches_dimension_size(axis, shape, dimension_index)
        ):
            return axis
    return None


def _axis_name(axis: dict[str, Any]) -> str:
    return str(axis.get("name", "")).strip().lower()


def _axis_index(axis: dict[str, Any]) -> int | None:
    try:
        return int(axis.get("index_in_array"))
    except (TypeError, ValueError):
        return None


def _axis_matches_dimension_size(
    axis: dict[str, Any],
    shape: tuple[int, int],
    dimension_index: int,
) -> bool:
    size = axis.get("size")
    if size is None:
        return True

    try:
        return int(size) == int(shape[dimension_index])
    except (TypeError, ValueError):
        return False


def _axis_scale_nm_per_pixel(axis: dict[str, Any]) -> float | None:
    try:
        scale = float(axis.get("scale"))
    except (TypeError, ValueError):
        return None

    if not math.isfinite(scale) or scale <= 0:
        return None

    unit_factor = LENGTH_UNITS_TO_NM.get(_normalise_length_unit(axis.get("units")))
    if unit_factor is None:
        return None

    return scale * unit_factor


def _normalise_length_unit(units: Any) -> str:
    return str(units).strip().lower().replace(" ", "")


def _pixels_per_nm_resolution(nm_per_pixel: float) -> tuple[int, int]:
    pixels_per_nm = Fraction(str(1.0 / nm_per_pixel)).limit_denominator(1_000_000)
    return (pixels_per_nm.numerator, pixels_per_nm.denominator)


def _safe_png_metadata(info: dict[str, Any]) -> dict[str, Any]:
    text: dict[str, str] = {}
    notes: list[str] = []

    for key, value in info.items():
        if (
            isinstance(key, str)
            and 0 < len(key) <= 79
            and isinstance(value, str)
            and len(value) <= 65535
        ):
            text[key] = value
        else:
            notes.append(f"Skipped unsafe PNG metadata key: {key}")

    metadata: dict[str, Any] = {}
    if text:
        metadata["png_text"] = text
    if notes:
        metadata["metadata_notes"] = notes
    return metadata


def _png_write_options(image: ImageData) -> dict[str, Any]:
    if image.source_kind is not SourceKind.STANDARD:
        return {}

    text = image.metadata.get("png_text", {})
    if not isinstance(text, dict) or not text:
        return {}

    pnginfo = PngInfo()
    for key, value in text.items():
        if isinstance(key, str) and isinstance(value, str):
            pnginfo.add_text(key, value)

    return {"pnginfo": pnginfo}


def _image_data_from_array(
    path: Path,
    array: np.ndarray,
    source_kind: SourceKind,
    metadata: dict[str, Any] | None = None,
) -> ImageData:
    grayscale = _to_2d_grayscale(array, path)
    pixels = grayscale.astype(np.float32, copy=False)

    if pixels.size == 0:
        raise ImageFormatError(f"Image is empty: {path.name}.")

    return ImageData(
        source_path=path,
        pixels=pixels,
        source_dtype=np.dtype(grayscale.dtype),
        source_min=float(np.nanmin(pixels)),
        source_max=float(np.nanmax(pixels)),
        source_kind=source_kind,
        metadata=metadata or {},
    )


def _to_2d_grayscale(array: np.ndarray, path: Path) -> np.ndarray:
    data = np.asarray(array)

    if data.ndim == 2:
        return data

    if data.ndim == 3 and data.shape[-1] in {3, 4}:
        rgb = data[..., :3].astype(np.float32, copy=False)
        return (rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114).astype(
            data.dtype,
            copy=False,
        )

    raise ImageFormatError(
        f"Unsupported image shape for {path.name}: {data.shape}. "
        "Only 2D grayscale and RGB/RGBA images are supported."
    )
