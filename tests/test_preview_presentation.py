from __future__ import annotations

import numpy as np

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
