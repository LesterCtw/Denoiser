from __future__ import annotations

from pathlib import Path

from denoiser.batch_presentation import batch_result_row
from denoiser.workflow import BatchFileResult, BatchFileStatus


def test_batch_result_row_formats_restored_output_detail() -> None:
    row = batch_result_row(
        BatchFileResult(
            source_path=Path("/case/wafer.tif"),
            status=BatchFileStatus.RESTORED,
            message="Restored",
            output_path=Path("/case/denoised_HRSTEM/wafer.tif"),
        )
    )

    assert row.filename == "wafer.tif"
    assert row.status is BatchFileStatus.RESTORED
    assert row.status_label == "Restored"
    assert row.detail == "Saved to denoised_HRSTEM/wafer.tif"


def test_batch_result_row_keeps_non_restored_failure_message() -> None:
    row = batch_result_row(
        BatchFileResult(
            source_path=Path("/case/notes.txt"),
            status=BatchFileStatus.SKIPPED,
            message="Unsupported file format: .txt",
        )
    )

    assert row.status_label == "Skipped"
    assert row.detail == "Unsupported file format: .txt"
