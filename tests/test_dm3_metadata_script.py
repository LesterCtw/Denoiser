from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rsciio.digitalmicrograph

from scripts.inspect_dm3_metadata import format_report, inspect_dm_file


def test_inspect_dm3_metadata_reports_axes_and_denoiser_candidate(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    source = tmp_path / "wafer.dm3"
    source.write_bytes(b"synthetic placeholder")

    def fake_file_reader(filename: str) -> list[dict[str, Any]]:
        assert filename == str(source)
        return [
            {
                "data": np.array([[1, 2], [3, 4]], dtype=np.float32),
                "axes": [
                    {
                        "name": "y",
                        "size": 2,
                        "index_in_array": 0,
                        "scale": -1.25,
                        "units": "nm",
                        "navigate": False,
                    },
                    {
                        "name": "x",
                        "size": 2,
                        "index_in_array": 1,
                        "scale": -0.5,
                        "units": "nm",
                        "navigate": False,
                    },
                ],
            }
        ]

    monkeypatch.setattr(rsciio.digitalmicrograph, "file_reader", fake_file_reader)

    report = inspect_dm_file(source)[0]
    rendered = format_report(report)

    assert report.data_shape == (2, 2)
    assert report.pixel_size_nm == (0.5, 1.25)
    assert "scale=-0.5" in rendered
    assert "Denoiser DM pixel size candidate: x=0.5 nm/px, y=1.25 nm/px" in rendered
    assert "ResolutionUnit=CENTIMETER" in rendered
