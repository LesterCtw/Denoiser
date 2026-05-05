"""Single-image preview presentation helpers."""

from __future__ import annotations

import base64
import html
from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class RawPreview:
    data_url: str
    is_comparing: bool = False


@dataclass(frozen=True)
class ComparisonPreview:
    raw_data_url: str
    restored_data_url: str
    divider_position: float = 0.5
    raw_side: str = "left"
    restored_side: str = "right"
    supports_click_to_jump: bool = True
    supports_drag: bool = True


def raw_preview(preview_pixels: np.ndarray) -> RawPreview:
    return RawPreview(data_url=raw_preview_data_url(preview_pixels))


def comparison_preview(
    raw_pixels: np.ndarray,
    restored_pixels: np.ndarray,
) -> ComparisonPreview:
    return ComparisonPreview(
        raw_data_url=raw_preview_data_url(raw_pixels),
        restored_data_url=raw_preview_data_url(restored_pixels),
    )


def raw_preview_data_url(preview_pixels: np.ndarray) -> str:
    pixels = np.asarray(preview_pixels)
    if pixels.ndim != 2:
        raise ValueError(f"Raw preview expects 2D pixels, got shape {pixels.shape}.")

    display = pixels.astype(np.float32, copy=False)
    minimum = float(np.nanmin(display))
    maximum = float(np.nanmax(display))
    if maximum > minimum:
        display = (display - minimum) / (maximum - minimum)
    else:
        display = np.zeros_like(display, dtype=np.float32)
    display_uint8 = np.clip(np.rint(display * 255), 0, 255).astype(np.uint8)

    buffer = BytesIO()
    Image.fromarray(display_uint8).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def raw_preview_html(preview: RawPreview) -> str:
    source = html.escape(preview.data_url, quote=True)
    return f"""
    <div class="denoiser-preview-frame denoiser-preview-frame-active denoiser-raw-preview">
      <img class="denoiser-preview-image" src="{source}" alt="Raw image">
    </div>
    """


def comparison_html(preview: ComparisonPreview) -> str:
    divider_percent = preview.divider_position * 100
    raw_source = html.escape(preview.raw_data_url, quote=True)
    restored_source = html.escape(preview.restored_data_url, quote=True)
    return f"""
    <div class="denoiser-preview-frame denoiser-preview-frame-active denoiser-comparison"
         style="--divider-position: {preview.divider_position}; --divider-frame-position: {divider_percent}%"
         data-divider="{preview.divider_position}"
         data-raw-side="{preview.raw_side}"
         data-restored-side="{preview.restored_side}"
         role="slider"
         tabindex="0"
         aria-label="Before after comparison divider"
         aria-valuemin="0"
         aria-valuemax="100"
         aria-valuenow="{divider_percent}"
         onkeydown="window.denoiserMoveComparisonDividerWithKey(this, event)"
         onpointerdown="
           this.setPointerCapture(event.pointerId);
           window.denoiserSetComparisonDivider(this, event);
         "
         onpointermove="
           if (event.buttons) window.denoiserSetComparisonDivider(this, event);
         ">
      <img class="denoiser-comparison-raw"
           src="{raw_source}"
           alt="Raw image"
           onload="window.denoiserRefreshComparisonDivider(this.closest('.denoiser-comparison'))">
      <img class="denoiser-comparison-restored"
           src="{restored_source}"
           alt="Restored image"
           onload="window.denoiserRefreshComparisonDivider(this.closest('.denoiser-comparison'))">
      <div class="denoiser-comparison-divider"></div>
      <div class="denoiser-comparison-hit-target"></div>
    </div>
    """
