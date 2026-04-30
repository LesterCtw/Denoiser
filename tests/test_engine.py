from __future__ import annotations

import numpy as np
import pytest

from denoiser.engine import (
    DenoiseEngineError,
    DenoiseMode,
    InferenceSettings,
    OnnxDenoiser,
    should_use_patch_based,
)
from denoiser.models import missing_model_paths


def test_missing_model_paths_reports_missing_required_models(tmp_path) -> None:
    (tmp_path / "sfr_hrstem.onnx").write_bytes(b"model")

    missing = {path.name for path in missing_model_paths(tmp_path)}

    assert missing == {
        "sfr_lrstem.onnx",
        "sfr_hrsem.onnx",
        "sfr_lrsem.onnx",
    }


def test_small_images_use_whole_image_inference() -> None:
    settings = InferenceSettings(whole_image_threshold_px=1536)

    assert not should_use_patch_based(height=1536, width=1200, settings=settings)


def test_onnx_denoiser_restores_2d_pixels_with_selected_mode_model(tmp_path) -> None:
    for tag in ("sfr_hrstem", "sfr_lrstem", "sfr_hrsem", "sfr_lrsem"):
        (tmp_path / f"{tag}.onnx").write_bytes(b"model")

    class FakeSession:
        def __init__(self, model_path):
            self.offset = 7 if model_path.name == "sfr_lrsem.onnx" else 0

        def run(self, input_tensor):
            return input_tensor + self.offset

    denoiser = OnnxDenoiser(models_dir=tmp_path, session_factory=FakeSession)
    pixels = np.array([[1, 2], [3, 4]], dtype=np.float32)

    restored = denoiser.restore(pixels, DenoiseMode.LRSEM)

    np.testing.assert_array_equal(restored, pixels + 7)


def test_onnx_denoiser_reports_missing_model(tmp_path) -> None:
    denoiser = OnnxDenoiser(models_dir=tmp_path)

    with pytest.raises(DenoiseEngineError, match="sfr_hrstem.onnx"):
        denoiser.restore(np.zeros((2, 2), dtype=np.float32), DenoiseMode.HRSTEM)


def test_onnx_denoiser_runs_bundled_model_on_synthetic_image() -> None:
    denoiser = OnnxDenoiser()
    pixels = np.zeros((16, 16), dtype=np.float32)

    restored = denoiser.restore(pixels, DenoiseMode.HRSTEM)

    assert restored.shape == pixels.shape
    assert restored.dtype == np.float32


def test_onnx_denoiser_pads_odd_sized_images_and_crops_output(tmp_path) -> None:
    for tag in ("sfr_hrstem", "sfr_lrstem", "sfr_hrsem", "sfr_lrsem"):
        (tmp_path / f"{tag}.onnx").write_bytes(b"model")

    class EvenOnlySession:
        def __init__(self, model_path):
            pass

        def run(self, input_tensor):
            assert input_tensor.shape == (1, 4, 6, 1)
            return input_tensor + 1

    denoiser = OnnxDenoiser(models_dir=tmp_path, session_factory=EvenOnlySession)
    pixels = np.zeros((3, 5), dtype=np.float32)

    restored = denoiser.restore(pixels, DenoiseMode.HRSTEM)

    assert restored.shape == pixels.shape
    np.testing.assert_array_equal(restored, np.ones((3, 5), dtype=np.float32))
