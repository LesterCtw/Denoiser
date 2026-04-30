"""Denoising engine boundary.

This module will host the minimal ONNX inference wrapper derived from the
required tk_r_em behavior. It is intentionally small so the UI does not depend
on the full upstream tk_r_em package at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

import numpy as np


class DenoiseMode(str, Enum):
    HRSTEM = "HRSTEM"
    LRSTEM = "LRSTEM"
    HRSEM = "HRSEM"
    LRSEM = "LRSEM"


@dataclass(frozen=True)
class InferenceSettings:
    whole_image_threshold_px: int = 1536
    patch_size: int = 512
    stride: int = 256
    batch_size: int = 2


class DenoiseEngineError(RuntimeError):
    """Raised when denoising cannot run safely."""


class DenoiseSession(Protocol):
    def run(self, input_tensor: np.ndarray) -> np.ndarray: ...


MODEL_TAGS: dict[DenoiseMode, str] = {
    DenoiseMode.HRSTEM: "sfr_hrstem",
    DenoiseMode.LRSTEM: "sfr_lrstem",
    DenoiseMode.HRSEM: "sfr_hrsem",
    DenoiseMode.LRSEM: "sfr_lrsem",
}

DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


OUTPUT_FOLDERS: dict[DenoiseMode, str] = {
    mode: f"denoised_{mode.value}" for mode in DenoiseMode
}


def should_use_patch_based(height: int, width: int, settings: InferenceSettings) -> bool:
    """Return whether an image should use patch-based inference."""

    return max(height, width) > settings.whole_image_threshold_px


class OnnxDenoiser:
    """Minimal ONNX denoiser for Single workflow restore paths."""

    def __init__(
        self,
        models_dir: Path = DEFAULT_MODELS_DIR,
        session_factory: type[DenoiseSession] | None = None,
        settings: InferenceSettings | None = None,
    ) -> None:
        self._models_dir = Path(models_dir)
        self._session_factory = session_factory or _OrtSession
        self._settings = settings or InferenceSettings()
        self._sessions: dict[DenoiseMode, DenoiseSession] = {}

    def restore(self, pixels: np.ndarray, mode: DenoiseMode) -> np.ndarray:
        source = np.asarray(pixels, dtype=np.float32)
        if source.ndim != 2:
            raise DenoiseEngineError(f"Expected a 2D grayscale image, got shape {source.shape}.")

        if should_use_patch_based(source.shape[0], source.shape[1], self._settings):
            return self._restore_patch_based(source, mode)

        return self._restore_whole_image(source, mode)

    def _restore_whole_image(self, source: np.ndarray, mode: DenoiseMode) -> np.ndarray:
        input_tensor = _pad_2d_to_even(source)[None, :, :, None]
        output_tensor = self._session_for(mode).run(input_tensor)
        output = np.asarray(output_tensor, dtype=np.float32)

        if output.shape != input_tensor.shape:
            raise DenoiseEngineError(
                f"Model output shape {output.shape} does not match input shape {input_tensor.shape}."
            )

        return output[0, : source.shape[0], : source.shape[1], 0]

    def _restore_patch_based(self, source: np.ndarray, mode: DenoiseMode) -> np.ndarray:
        settings = self._settings
        patch_size = settings.patch_size
        stride = settings.stride
        batch_size = settings.batch_size
        if patch_size <= 0 or stride <= 0 or batch_size <= 0:
            raise DenoiseEngineError("Patch settings must be positive integers.")

        height, width = source.shape
        padded_height = max(height, patch_size)
        padded_width = max(width, patch_size)
        padded = np.full((padded_height, padded_width), float(source.mean()), dtype=np.float32)
        padded[:height, :width] = source

        output_sum = np.zeros_like(padded, dtype=np.float32)
        output_count = np.zeros_like(padded, dtype=np.float32)
        starts = [
            (y, x)
            for y in _patch_starts(padded_height, patch_size, stride)
            for x in _patch_starts(padded_width, patch_size, stride)
        ]
        session = self._session_for(mode)

        for batch_start in range(0, len(starts), batch_size):
            batch_positions = starts[batch_start : batch_start + batch_size]
            batch = np.stack(
                [
                    padded[y : y + patch_size, x : x + patch_size]
                    for y, x in batch_positions
                ],
                axis=0,
            )[..., None]
            output_tensor = session.run(batch)
            output = np.asarray(output_tensor, dtype=np.float32)
            if output.shape != batch.shape:
                raise DenoiseEngineError(
                    f"Model output shape {output.shape} does not match patch batch shape {batch.shape}."
                )

            for patch, (y, x) in zip(output[..., 0], batch_positions, strict=True):
                output_sum[y : y + patch_size, x : x + patch_size] += patch
                output_count[y : y + patch_size, x : x + patch_size] += 1

        restored = output_sum / output_count
        return restored[:height, :width]

    def _session_for(self, mode: DenoiseMode) -> DenoiseSession:
        if mode not in self._sessions:
            model_path = self._models_dir / f"{MODEL_TAGS[mode]}.onnx"
            if not model_path.is_file():
                raise DenoiseEngineError(f"Required model file is missing: {model_path.name}")
            self._sessions[mode] = self._session_factory(model_path)
        return self._sessions[mode]


class _OrtSession:
    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self._input_name = self._session.get_inputs()[0].name

    def run(self, input_tensor: np.ndarray) -> np.ndarray:
        return self._session.run(
            None,
            {self._input_name: np.ascontiguousarray(input_tensor, dtype=np.float32)},
        )[0]


def _pad_2d_to_even(source: np.ndarray) -> np.ndarray:
    pad_height = source.shape[0] % 2
    pad_width = source.shape[1] % 2
    if not pad_height and not pad_width:
        return source

    return np.pad(
        source,
        ((0, pad_height), (0, pad_width)),
        mode="constant",
        constant_values=float(source.mean()),
    )


def _patch_starts(length: int, patch_size: int, stride: int) -> list[int]:
    if length <= patch_size:
        return [0]

    starts = list(range(0, length - patch_size + 1, stride))
    final_start = length - patch_size
    if starts[-1] != final_start:
        starts.append(final_start)
    return starts
