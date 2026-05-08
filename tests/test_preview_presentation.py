from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from denoiser.preview_presentation import (
    comparison_html,
    comparison_preview,
    raw_preview,
    raw_preview_html,
)


def test_raw_preview_encodes_2d_pixels_as_png_data_url() -> None:
    preview = raw_preview(np.array([[0, 255]], dtype=np.uint8))

    assert preview.data_url.startswith("data:image/png;base64,")
    assert preview.is_comparing is False


@pytest.mark.parametrize(
    "pixels",
    [
        np.array([[0, 255]], dtype=np.uint8),
        np.array([[1000, 4000]], dtype=np.uint16),
        np.array([[0.0, 1.0]], dtype=np.float32),
        np.array([[-1.0, 1.0]], dtype=np.float32),
    ],
)
def test_raw_preview_normalizes_numeric_ranges_to_uint8_png(pixels: np.ndarray) -> None:
    data_url = raw_preview(pixels).data_url
    payload = data_url.split(",", maxsplit=1)[1]

    preview_pixels = np.asarray(Image.open(BytesIO(base64.b64decode(payload))))

    assert preview_pixels.dtype == np.uint8
    assert preview_pixels.min() == 0
    assert preview_pixels.max() == 255


def test_preview_html_preserves_comparison_interaction_contract() -> None:
    preview = comparison_preview(
        np.array([[0, 255]], dtype=np.uint8),
        np.array([[255, 0]], dtype=np.uint8),
    )

    raw_html = raw_preview_html(raw_preview(np.array([[0, 255]], dtype=np.uint8)))
    compare_html = comparison_html(preview)

    assert "denoiser-raw-preview" in raw_html
    assert "denoiser-comparison" in compare_html
    assert "window.denoiserSetComparisonDivider" in compare_html
    assert 'role="slider"' in compare_html
