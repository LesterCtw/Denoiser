"""Batch restore presentation mapping.

This keeps UI-facing Batch status wording separate from restore execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from denoiser.image_io import is_supported_input
from denoiser.workflow import BatchFileResult, BatchFileStatus


@dataclass(frozen=True)
class BatchResultRow:
    filename: str
    status: BatchFileStatus
    status_label: str
    detail: str
    output_path: Path | None = None


def batch_result_row(file_result: BatchFileResult) -> BatchResultRow:
    return BatchResultRow(
        filename=file_result.source_path.name,
        status=file_result.status,
        status_label=batch_status_label(file_result.status),
        detail=readable_batch_detail(file_result),
        output_path=file_result.output_path,
    )


def visible_batch_result_rows(
    file_results: list[BatchFileResult],
) -> tuple[BatchResultRow, ...]:
    return tuple(
        batch_result_row(file_result)
        for file_result in file_results
        if should_show_batch_file_result(file_result)
    )


def should_show_batch_file_result(file_result: BatchFileResult) -> bool:
    return is_supported_input(file_result.source_path)


def batch_status_label(status: BatchFileStatus) -> str:
    if status is BatchFileStatus.RESTORED:
        return "Restored"
    if status is BatchFileStatus.FAILED:
        return "Failed"
    if status is BatchFileStatus.CANCELLED:
        return "Cancelled"
    return "Skipped"


def readable_batch_detail(file_result: BatchFileResult) -> str:
    if file_result.status is BatchFileStatus.RESTORED:
        if file_result.output_path is None:
            return "Saved output"
        return f"Saved to {file_result.output_path.parent.name}/{file_result.output_path.name}"
    return file_result.message
