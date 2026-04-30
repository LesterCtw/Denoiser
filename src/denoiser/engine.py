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
    """Minimal whole-image ONNX denoiser for the first Single workflow."""

    def __init__(
        self,
        models_dir: Path = DEFAULT_MODELS_DIR,
        session_factory: type[DenoiseSession] | None = None,
    ) -> None:
        self._models_dir = Path(models_dir)
        self._session_factory = session_factory or _OrtSession
        self._sessions: dict[DenoiseMode, DenoiseSession] = {}

    def restore(self, pixels: np.ndarray, mode: DenoiseMode) -> np.ndarray:
        source = np.asarray(pixels, dtype=np.float32)
        if source.ndim != 2:
            raise DenoiseEngineError(f"Expected a 2D grayscale image, got shape {source.shape}.")

        input_tensor = _pad_2d_to_even(source)[None, :, :, None]
        output_tensor = self._session_for(mode).run(input_tensor)
        output = np.asarray(output_tensor, dtype=np.float32)

        if output.shape != input_tensor.shape:
            raise DenoiseEngineError(
                f"Model output shape {output.shape} does not match input shape {input_tensor.shape}."
            )

        return output[0, : source.shape[0], : source.shape[1], 0]

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
