"""Bundled model inventory for the first Denoiser release."""

from __future__ import annotations

from pathlib import Path

from denoiser.engine import DenoiseMode


MODELS_DIR = Path(__file__).resolve().parents[2] / "models"

MODEL_TAGS: dict[DenoiseMode, str] = {
    DenoiseMode.HRSTEM: "sfr_hrstem",
    DenoiseMode.LRSTEM: "sfr_lrstem",
    DenoiseMode.HRSEM: "sfr_hrsem",
    DenoiseMode.LRSEM: "sfr_lrsem",
}


def model_path_for(mode: DenoiseMode, models_dir: Path = MODELS_DIR) -> Path:
    return models_dir / f"{MODEL_TAGS[mode]}.onnx"


def missing_model_paths(models_dir: Path = MODELS_DIR) -> list[Path]:
    return [
        model_path_for(mode, models_dir)
        for mode in DenoiseMode
        if not model_path_for(mode, models_dir).is_file()
    ]
