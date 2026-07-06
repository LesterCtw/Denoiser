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
    raw_preview_data_url,
    raw_preview_html,
)


def _preview_pixels_from_data_url(data_url: str) -> np.ndarray:
    payload = data_url.split(",", maxsplit=1)[1]
    return np.asarray(Image.open(BytesIO(base64.b64decode(payload))))


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
    preview_pixels = _preview_pixels_from_data_url(data_url)

    assert preview_pixels.dtype == np.uint8
    assert preview_pixels.min() == 0
    assert preview_pixels.max() == 255


def test_raw_preview_uses_mid_gray_for_constant_images() -> None:
    data_url = raw_preview_data_url(np.full((2, 2), 42, dtype=np.uint16))

    preview_pixels = _preview_pixels_from_data_url(data_url)

    assert preview_pixels.dtype == np.uint8
    assert np.all(preview_pixels == 128)


def test_raw_preview_uses_robust_range_for_large_outliers() -> None:
    pixels = np.append(np.linspace(0, 100, 1000, dtype=np.float32), 10000).reshape(1, -1)

    data_url = raw_preview_data_url(pixels)
    preview_pixels = _preview_pixels_from_data_url(data_url)

    main_image_pixels = preview_pixels[:, :-1]
    assert main_image_pixels.max() > 200
    assert len(np.unique(main_image_pixels)) > 32
    assert preview_pixels[0, -1] == 255


def test_comparison_preview_uses_shared_display_range() -> None:
    preview = comparison_preview(
        np.array([[0, 100]], dtype=np.float32),
        np.array([[100, 200]], dtype=np.float32),
    )

    raw_pixels = _preview_pixels_from_data_url(preview.raw_data_url)
    restored_pixels = _preview_pixels_from_data_url(preview.restored_data_url)

    np.testing.assert_array_equal(raw_pixels, np.array([[0, 128]], dtype=np.uint8))
    np.testing.assert_array_equal(restored_pixels, np.array([[128, 255]], dtype=np.uint8))


def test_comparison_preview_preserves_darker_lower_contrast_restored_result() -> None:
    preview = comparison_preview(
        np.array([[0, 50, 100]], dtype=np.float32),
        np.array([[0, 25, 50]], dtype=np.float32),
    )

    raw_pixels = _preview_pixels_from_data_url(preview.raw_data_url)
    restored_pixels = _preview_pixels_from_data_url(preview.restored_data_url)

    np.testing.assert_array_equal(raw_pixels, np.array([[0, 128, 255]], dtype=np.uint8))
    np.testing.assert_array_equal(restored_pixels, np.array([[0, 64, 128]], dtype=np.uint8))


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
