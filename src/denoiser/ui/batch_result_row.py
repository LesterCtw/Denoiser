"""Batch result row rendering for the PySide6 UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from denoiser.workflow import BatchFileResult, BatchFileStatus


@dataclass(frozen=True)
class BatchResultListEntry:
    item_text: str
    row_widget: QWidget


def batch_result_list_entry(file_result: BatchFileResult) -> BatchResultListEntry:
    status = batch_status_label(file_result.status)
    detail = (
        _short_path_label(file_result.output_path)
        if file_result.output_path is not None
        else file_result.message
    )
    return BatchResultListEntry(
        item_text=f"{file_result.source_path.name} - {status}: {detail}",
        row_widget=_batch_result_row(
            filename=file_result.source_path.name,
            status=status,
            status_kind=file_result.status,
            detail=readable_batch_detail(file_result.status, detail),
        ),
    )


def batch_status_label(status: BatchFileStatus) -> str:
    if status is BatchFileStatus.RESTORED:
        return "Restored"
    if status is BatchFileStatus.FAILED:
        return "Failed"
    if status is BatchFileStatus.CANCELLED:
        return "Cancelled"
    return "Skipped"


def readable_batch_detail(status: BatchFileStatus, detail: str) -> str:
    if status is BatchFileStatus.RESTORED:
        return f"Saved to {detail}"
    if detail.startswith("Unsupported file format:"):
        return detail.replace("Unsupported file format:", "Unsupported format", 1)
    if detail.startswith("Multi-page TIFF files are not supported."):
        return "Multi-page TIFF not supported. Use a single 2D image."
    return detail


def _short_path_label(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


def _batch_result_row(
    filename: str,
    status: str,
    status_kind: BatchFileStatus,
    detail: str,
) -> QWidget:
    row = QFrame()
    row.setObjectName("BatchResultItem")
    layout = QVBoxLayout(row)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(10)

    filename_label = QLabel(filename)
    filename_label.setObjectName("BatchFileName")
    filename_label.setWordWrap(True)
    header.addWidget(filename_label, 1)

    badge = QLabel(status)
    badge.setObjectName(_batch_status_badge_name(status_kind))
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    header.addWidget(badge)

    layout.addLayout(header)

    detail_label = QLabel(detail)
    detail_label.setObjectName("BatchFileDetail")
    detail_label.setWordWrap(True)
    layout.addWidget(detail_label)

    return row


def _batch_status_badge_name(status: BatchFileStatus) -> str:
    if status is BatchFileStatus.RESTORED:
        return "BatchStatusRestored"
    if status is BatchFileStatus.FAILED:
        return "BatchStatusFailed"
    if status is BatchFileStatus.CANCELLED:
        return "BatchStatusCancelled"
    return "BatchStatusSkipped"
