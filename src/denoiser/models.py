"""Model file locations and validation helpers."""

from __future__ import annotations

from pathlib import Path

from denoiser.engine import DEFAULT_MODELS_DIR, DenoiseMode, MODEL_TAGS


MODELS_DIR = DEFAULT_MODELS_DIR


def model_path_for(mode: DenoiseMode, models_dir: Path = MODELS_DIR) -> Path:
    return models_dir / f"{MODEL_TAGS[mode]}.onnx"


def missing_model_paths(models_dir: Path = MODELS_DIR) -> list[Path]:
    return [
        model_path_for(mode, models_dir)
        for mode in DenoiseMode
        if not model_path_for(mode, models_dir).is_file()
    ]
