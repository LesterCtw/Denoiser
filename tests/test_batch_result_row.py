from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from denoiser.ui.batch_result_row import (
    batch_result_list_entry,
    readable_batch_detail,
)
from denoiser.workflow import BatchFileResult, BatchFileStatus


def test_batch_result_list_entry_formats_restored_file(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "wafer.tif"
    output = tmp_path / "denoised_HRSEM" / "wafer.tif"

    entry = batch_result_list_entry(
        BatchFileResult(
            source_path=source,
            status=BatchFileStatus.RESTORED,
            message="Restored",
            output_path=output,
        )
    )

    badge = entry.row_widget.findChild(QLabel, "BatchStatusRestored")
    detail = entry.row_widget.findChild(QLabel, "BatchFileDetail")

    assert app is not None
    assert entry.item_text == "wafer.tif - Restored: denoised_HRSEM/wafer.tif"
    assert badge is not None
    assert badge.text() == "Restored"
    assert detail is not None
    assert detail.text() == "Saved to denoised_HRSEM/wafer.tif"


def test_readable_batch_detail_uses_user_friendly_error_messages() -> None:
    assert (
        readable_batch_detail(
            BatchFileStatus.SKIPPED,
            "Unsupported file format: .py",
        )
        == "Unsupported format .py"
    )
    assert (
        readable_batch_detail(
            BatchFileStatus.SKIPPED,
            "Multi-page TIFF files are not supported.",
        )
        == "Multi-page TIFF not supported. Use a single 2D image."
    )
