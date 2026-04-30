"""Image input/output boundary for Denoiser.

Implementation will preserve saved intensity scale and avoid applying preview
normalization to output files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image

from denoiser.engine import (
    DenoiseMode,
    InferenceSettings,
    OUTPUT_FOLDERS,
    should_use_patch_based,
)


SUPPORTED_INPUT_EXTENSIONS = {
    ".tif",
    ".tiff",
    ".png",
    ".jpg",
    ".jpeg",
    ".dm3",
    ".dm4",
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


def is_supported_input(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS


def is_inside_denoised_folder(path: Path) -> bool:
    return any(part.lower().startswith("denoised_") for part in path.parts)


def output_suffix_for_input(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".dm3", ".dm4"}:
        return ".tif"
    return suffix


def output_path_for_input(path: Path, mode: DenoiseMode) -> Path:
    output_dir = path.parent / OUTPUT_FOLDERS[mode]
    return output_dir / f"{path.stem}{output_suffix_for_input(path)}"


def image_requires_patch_based(
    path: Path,
    settings: InferenceSettings | None = None,
) -> bool:
    height, width = image_dimensions(path)
    return should_use_patch_based(height, width, settings or InferenceSettings())


def image_dimensions(path: Path) -> tuple[int, int]:
    path = Path(path)
    if not is_supported_input(path):
        raise ImageFormatError(f"Unsupported file format: {path.suffix}")
    if is_inside_denoised_folder(path):
        raise ImageFormatError("Refusing to inspect files inside denoised_* folders.")

    suffix = path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        with tifffile.TiffFile(path) as tif:
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
        tifffile.imwrite(output_path, output, photometric="minisblack")
    elif output_path.suffix.lower() == ".png":
        Image.fromarray(output).save(output_path)
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
        array = np.asarray(img)
    return _image_data_from_array(path, array, SourceKind.STANDARD)


def _load_tiff_image(path: Path) -> ImageData:
    with tifffile.TiffFile(path) as tif:
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
        array = series.asarray()
    return _image_data_from_array(path, array, SourceKind.STANDARD)


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
