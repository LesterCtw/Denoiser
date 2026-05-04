"""Bundled model inventory for the first Denoiser release."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from denoiser.runtime_paths import resource_path

MODELS_DIR = resource_path("models")


class DenoiseMode(str, Enum):
    HRSTEM = "HRSTEM"
    LRSTEM = "LRSTEM"
    HRSEM = "HRSEM"
    LRSEM = "LRSEM"


@dataclass(frozen=True)
class BundledModel:
    mode: DenoiseMode
    ui_label: str
    model_tag: str
    output_folder: str


BUNDLED_MODELS: tuple[BundledModel, ...] = (
    BundledModel(
        mode=DenoiseMode.HRSTEM,
        ui_label="HRSTEM",
        model_tag="sfr_hrstem",
        output_folder="denoised_HRSTEM",
    ),
    BundledModel(
        mode=DenoiseMode.LRSTEM,
        ui_label="LRSTEM",
        model_tag="sfr_lrstem",
        output_folder="denoised_LRSTEM",
    ),
    BundledModel(
        mode=DenoiseMode.HRSEM,
        ui_label="HRSEM",
        model_tag="sfr_hrsem",
        output_folder="denoised_HRSEM",
    ),
    BundledModel(
        mode=DenoiseMode.LRSEM,
        ui_label="LRSEM",
        model_tag="sfr_lrsem",
        output_folder="denoised_LRSEM",
    ),
)

_MODEL_BY_MODE: dict[DenoiseMode, BundledModel] = {
    bundled_model.mode: bundled_model for bundled_model in BUNDLED_MODELS
}


def supported_denoise_modes() -> tuple[DenoiseMode, ...]:
    return tuple(bundled_model.mode for bundled_model in BUNDLED_MODELS)


def default_denoise_mode() -> DenoiseMode:
    return BUNDLED_MODELS[0].mode


def model_tag_for(mode: DenoiseMode) -> str:
    return _MODEL_BY_MODE[mode].model_tag


def mode_label_for(mode: DenoiseMode) -> str:
    return _MODEL_BY_MODE[mode].ui_label


def output_folder_for_mode(mode: DenoiseMode) -> str:
    return _MODEL_BY_MODE[mode].output_folder


def default_models_dir() -> Path:
    return resource_path("models")


def model_path_for(mode: DenoiseMode, models_dir: Path | None = None) -> Path:
    if models_dir is None:
        models_dir = default_models_dir()
    return models_dir / f"{model_tag_for(mode)}.onnx"


def missing_model_paths(models_dir: Path | None = None) -> list[Path]:
    return [
        model_path_for(mode, models_dir)
        for mode in supported_denoise_modes()
        if not model_path_for(mode, models_dir).is_file()
    ]
