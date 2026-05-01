from __future__ import annotations

from pathlib import Path

from denoiser.engine import DenoiseMode
from denoiser.output_paths import (
    is_inside_denoised_folder,
    output_path_for_input,
    output_suffix_for_input,
)


def test_output_suffix_rules() -> None:
    assert output_suffix_for_input(Path("a.tif")) == ".tif"
    assert output_suffix_for_input(Path("a.tiff")) == ".tiff"
    assert output_suffix_for_input(Path("a.png")) == ".png"
    assert output_suffix_for_input(Path("a.jpg")) == ".tif"
    assert output_suffix_for_input(Path("a.jpeg")) == ".tif"
    assert output_suffix_for_input(Path("a.dm3")) == ".tif"
    assert output_suffix_for_input(Path("a.dm4")) == ".tif"


def test_output_path_uses_mode_folder_and_overwrite_name(tmp_path: Path) -> None:
    source = tmp_path / "case" / "wafer01.jpg"
    expected = tmp_path / "case" / "denoised_HRSTEM" / "wafer01.tif"

    assert output_path_for_input(source, DenoiseMode.HRSTEM) == expected


def test_detects_denoised_folder() -> None:
    assert is_inside_denoised_folder(Path("case/denoised_HRSTEM/a.tif"))
    assert is_inside_denoised_folder(Path("case/DENOISED_lrsem/a.tif"))
    assert not is_inside_denoised_folder(Path("case/raw/a.tif"))
