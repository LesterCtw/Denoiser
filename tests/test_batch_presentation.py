from __future__ import annotations

from pathlib import Path

from denoiser.batch_presentation import (
    batch_result_row,
    should_show_batch_file_result,
    visible_batch_result_rows,
)
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


def test_visible_batch_result_rows_hides_skipped_non_image_files() -> None:
    rows = visible_batch_result_rows(
        [
            BatchFileResult(
                source_path=Path("/case/notes.txt"),
                status=BatchFileStatus.SKIPPED,
                message="Unsupported file format: .txt",
            ),
            BatchFileResult(
                source_path=Path("/case/stack.tif"),
                status=BatchFileStatus.SKIPPED,
                message="Stack-like TIFF data is not supported",
            ),
            BatchFileResult(
                source_path=Path("/case/wafer.tif"),
                status=BatchFileStatus.RESTORED,
                message="Restored",
                output_path=Path("/case/denoised_HRSTEM/wafer.tif"),
            ),
        ]
    )

    assert [row.filename for row in rows] == ["stack.tif", "wafer.tif"]


def test_should_show_batch_file_result_keeps_failed_non_image_files() -> None:
    assert should_show_batch_file_result(
        BatchFileResult(
            source_path=Path("/case/notes.txt"),
            status=BatchFileStatus.FAILED,
            message="Unexpected error",
        )
    )
