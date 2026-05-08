from __future__ import annotations

from pathlib import Path

from denoiser.models import DenoiseMode
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
    expected = tmp_path / "case" / "denoised_HRSTEM" / "wafer01.jpg.tif"

    assert output_path_for_input(source, DenoiseMode.HRSTEM) == expected


def test_converted_output_paths_preserve_original_suffix_to_avoid_collisions(
    tmp_path: Path,
) -> None:
    sources = [
        tmp_path / "case" / filename
        for filename in ("sample.tif", "sample.jpg", "sample.jpeg", "sample.dm3", "sample.dm4")
    ]

    outputs = [output_path_for_input(source, DenoiseMode.HRSTEM).name for source in sources]

    assert outputs == [
        "sample.tif",
        "sample.jpg.tif",
        "sample.jpeg.tif",
        "sample.dm3.tif",
        "sample.dm4.tif",
    ]
    assert len(outputs) == len(set(outputs))


def test_detects_denoised_folder() -> None:
    assert is_inside_denoised_folder(Path("case/denoised_HRSTEM/a.tif"))
    assert is_inside_denoised_folder(Path("case/DENOISED_lrsem/a.tif"))
    assert not is_inside_denoised_folder(Path("case/raw/a.tif"))
