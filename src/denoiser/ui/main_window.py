"""Main Denoiser window skeleton."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from denoiser.engine import DenoiseMode, OnnxDenoiser
from denoiser.image_io import ImageFormatError, image_requires_patch_based, load_image
from denoiser.ui.batch_restore_runner import BatchRestoreRunner
from denoiser.ui.compare_view import CompareView
from denoiser.ui.restore_task_runner import RestoreTaskRunner
from denoiser.workflow import (
    BatchFileStatus,
    BatchRestoreRun,
    RestoreEngine,
    restore_single_image,
)


class MainWindow(QMainWindow):
    def __init__(self, engine: RestoreEngine | None = None) -> None:
        super().__init__()
        self._engine = engine or OnnxDenoiser()
        self._single_image_path: Path | None = None
        self._batch_folder_path: Path | None = None
        self._mode_buttons: dict[DenoiseMode, QPushButton] = {}
        self._restore_task_runner = RestoreTaskRunner()
        self._batch_restore_runner = BatchRestoreRunner()
        self._status_plain_text = "Ready"

        self.setWindowTitle("Denoiser")
        self.resize(1280, 800)
        self.setMinimumSize(980, 620)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_preview_area(), 1)

        self.setCentralWidget(root)
        self.setStyleSheet(_stylesheet())

    def set_single_image_path(self, path: Path) -> None:
        self._single_image_path = Path(path)
        try:
            image = load_image(self._single_image_path)
        except ImageFormatError as exc:
            self._compare_view.clear(str(exc))
        else:
            self._compare_view.set_raw_image(image.pixels)

        rows = [
            ("File", self._single_image_path.name),
            ("Note", "Existing outputs will be overwritten."),
        ]
        plain_text = (
            f"Selected: {self._single_image_path.name}\n"
            "Existing outputs will be overwritten."
        )
        try:
            if image_requires_patch_based(self._single_image_path):
                rows.append(("Warning", "Large images may take several minutes."))
                plain_text += "\nLarge images may take several minutes."
        except ImageFormatError:
            pass
        self._set_status(
            "Selected image",
            rows=rows,
            tooltip=str(self._single_image_path),
            plain_text=plain_text,
        )

    def mode_button(self, mode: DenoiseMode) -> QPushButton:
        return self._mode_buttons[mode]

    def status_text(self) -> str:
        return self._status_plain_text

    def status_tooltip(self) -> str:
        return self._status_card.toolTip()

    def show_batch_mode(self) -> None:
        self._batch_button.click()

    def show_single_mode(self) -> None:
        self._single_button.click()

    def set_batch_folder_path(self, path: Path) -> None:
        self._batch_folder_path = Path(path)
        self._batch_list.clear()
        self._set_batch_progress("0 of 0 files")
        self._set_status(
            "Batch folder",
            rows=[("Folder", self._batch_folder_path.name)],
            tooltip=str(self._batch_folder_path),
            plain_text=f"Batch folder: {self._batch_folder_path.name}",
        )

    def batch_progress_text(self) -> str:
        return self._batch_progress.text()

    def batch_status_texts(self) -> list[str]:
        return [
            self._batch_list.item(index).text()
            for index in range(self._batch_list.count())
        ]

    def processing_indicator_visible(self) -> bool:
        return not self._processing_indicator.isHidden()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(320)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Denoiser")
        title.setObjectName("Title")
        layout.addWidget(title)

        mode_row = QHBoxLayout()
        self._single_button = QPushButton("Single")
        self._single_button.setCheckable(True)
        self._single_button.setChecked(True)
        self._batch_button = QPushButton("Batch")
        self._batch_button.setCheckable(True)

        workflow_group = QButtonGroup(sidebar)
        workflow_group.setExclusive(True)
        workflow_group.addButton(self._single_button)
        workflow_group.addButton(self._batch_button)

        self._single_button.clicked.connect(self._show_single_controls)
        self._batch_button.clicked.connect(self._show_batch_controls)

        mode_row.addWidget(self._single_button)
        mode_row.addWidget(self._batch_button)
        layout.addLayout(mode_row)

        self._single_controls = QWidget()
        single_controls_layout = QVBoxLayout(self._single_controls)
        single_controls_layout.setContentsMargins(0, 0, 0, 0)
        single_controls_layout.setSpacing(12)
        open_image_button = QPushButton("Open Image")
        open_image_button.clicked.connect(self._open_single_image)
        single_controls_layout.addWidget(open_image_button)

        self._batch_controls = QWidget()
        batch_controls_layout = QVBoxLayout(self._batch_controls)
        batch_controls_layout.setContentsMargins(0, 0, 0, 0)
        batch_controls_layout.setSpacing(12)
        add_folder_button = QPushButton("Add Folder")
        add_folder_button.clicked.connect(self._open_batch_folder)
        batch_controls_layout.addWidget(add_folder_button)

        self._workflow_controls = QStackedWidget()
        self._workflow_controls.addWidget(self._single_controls)
        self._workflow_controls.addWidget(self._batch_controls)
        layout.addWidget(self._workflow_controls)

        model_label = QLabel("Mode")
        model_label.setObjectName("SectionLabel")
        layout.addWidget(model_label)

        model_group = QButtonGroup(sidebar)
        model_group.setExclusive(True)
        for mode in DenoiseMode:
            button = QPushButton(mode.value)
            button.setCheckable(True)
            if mode is DenoiseMode.HRSTEM:
                button.setChecked(True)
            model_group.addButton(button)
            self._mode_buttons[mode] = button
            layout.addWidget(button)

        self.restore_button = QPushButton("Restore")
        self.restore_button.setObjectName("PrimaryButton")
        self.restore_button.clicked.connect(self._restore_selected_image)
        layout.addWidget(self.restore_button)

        self.start_batch_button = QPushButton("Start Batch")
        self.start_batch_button.setObjectName("PrimaryButton")
        self.start_batch_button.clicked.connect(self._restore_batch_folder)
        self.start_batch_button.hide()
        layout.addWidget(self.start_batch_button)

        self.cancel_batch_button = QPushButton("Cancel")
        self.cancel_batch_button.clicked.connect(self._cancel_batch_restore)
        self.cancel_batch_button.hide()
        layout.addWidget(self.cancel_batch_button)

        layout.addStretch(1)

        self._processing_indicator = QProgressBar()
        self._processing_indicator.setObjectName("ProcessingIndicator")
        self._processing_indicator.setRange(0, 0)
        self._processing_indicator.setTextVisible(False)
        self._processing_indicator.hide()
        layout.addWidget(self._processing_indicator)

        self._status_card = QFrame()
        self._status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(self._status_card)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.setSpacing(6)

        self._status_title = QLabel("Ready")
        self._status_title.setObjectName("StatusTitle")
        self._status_title.setWordWrap(True)
        status_layout.addWidget(self._status_title)

        self._status_details = QLabel("")
        self._status_details.setObjectName("StatusDetails")
        self._status_details.setWordWrap(True)
        self._status_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._status_details.hide()
        status_layout.addWidget(self._status_details)

        layout.addWidget(self._status_card)

        return sidebar

    def _build_preview_area(self) -> QWidget:
        preview = QFrame()
        preview.setObjectName("PreviewArea")
        preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(preview)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)

        self._preview_stack = QStackedWidget()

        self._compare_view = CompareView()
        self._compare_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._preview_stack.addWidget(self._compare_view)

        self._batch_panel = QFrame()
        self._batch_panel.setObjectName("BatchPanel")
        batch_layout = QVBoxLayout(self._batch_panel)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        batch_layout.setSpacing(12)
        self._batch_progress = QLabel("0 of 0 files")
        self._batch_progress.setObjectName("BatchProgress")
        batch_layout.addWidget(self._batch_progress)
        self._batch_list = QListWidget()
        self._batch_list.setObjectName("BatchList")
        batch_layout.addWidget(self._batch_list, 1)
        self._preview_stack.addWidget(self._batch_panel)

        layout.addWidget(self._preview_stack, 1)

        return preview

    def _open_single_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Images (*.tif *.tiff *.png *.jpg *.jpeg *.dm3 *.dm4)",
        )
        if filename:
            self.set_single_image_path(Path(filename))

    def _open_batch_folder(self) -> None:
        dirname = QFileDialog.getExistingDirectory(self, "Add Folder", "")
        if dirname:
            self.set_batch_folder_path(Path(dirname))

    def _show_single_controls(self) -> None:
        self._workflow_controls.setCurrentWidget(self._single_controls)
        self._preview_stack.setCurrentWidget(self._compare_view)
        self.restore_button.show()
        self.start_batch_button.hide()
        self.cancel_batch_button.hide()
        self._set_status("Ready")

    def _show_batch_controls(self) -> None:
        self._workflow_controls.setCurrentWidget(self._batch_controls)
        self._preview_stack.setCurrentWidget(self._batch_panel)
        self._compare_view.clear("Batch mode")
        self.restore_button.hide()
        self.start_batch_button.show()
        self.cancel_batch_button.hide()
        self._set_status("Select a folder for Batch mode.")

    def _selected_mode(self) -> DenoiseMode:
        for mode, button in self._mode_buttons.items():
            if button.isChecked():
                return mode
        return DenoiseMode.HRSTEM

    def _restore_selected_image(self) -> None:
        if self._single_image_path is None:
            self._set_status("Open an image before restoring.")
            return

        mode = self._selected_mode()
        path = self._single_image_path
        self._set_single_restore_controls_enabled(False)
        self._set_processing_indicator_visible(True)
        self._set_status("Restoring...")
        QApplication.processEvents()
        QTimer.singleShot(0, lambda: self._start_single_restore(path, mode))

    def _start_single_restore(self, path: Path, mode: DenoiseMode) -> None:
        self._restore_task_runner.run(
            lambda: restore_single_image(path, mode, self._engine),
            self._finish_single_restore,
        )

    def _finish_single_restore(self, result, exc: Exception | None) -> None:
        if exc is not None:
            self._set_status(f"Cannot restore: {exc}")
        else:
            assert result is not None
            self._set_status(
                "Saved output",
                rows=[
                    ("File", result.output_path.name),
                    ("Folder", result.output_path.parent.name),
                ],
                tooltip=str(result.output_path),
                plain_text=(
                    f"Saved: {result.output_path.name}\n"
                    f"Folder: {result.output_path.parent.name}"
                ),
            )
            self._compare_view.set_images(result.raw_pixels, result.restored_pixels)

        self._set_processing_indicator_visible(False)
        self._set_single_restore_controls_enabled(True)

    def _set_single_restore_controls_enabled(self, enabled: bool) -> None:
        self._single_button.setEnabled(enabled)
        self._batch_button.setEnabled(enabled)
        self._single_controls.setEnabled(enabled)
        for button in self._mode_buttons.values():
            button.setEnabled(enabled)
        self.restore_button.setEnabled(enabled)

    def _restore_batch_folder(self) -> None:
        if self._batch_folder_path is None:
            self._set_status("Add a folder before starting Batch.")
            return

        batch_run = BatchRestoreRun(
            self._batch_folder_path,
            self._selected_mode(),
            self._engine,
        )
        self._batch_list.clear()
        self._update_batch_progress(batch_run.completed_count, batch_run.total_count)
        self._set_processing_indicator_visible(True)
        self._set_status("Batch restoring...")
        self.start_batch_button.hide()
        self.cancel_batch_button.show()
        QApplication.processEvents()
        self._batch_restore_runner.start(
            batch_run,
            self._append_batch_file_result,
            self._update_batch_progress,
            self._finish_batch_restore,
            self._finish_failed_batch_restore,
        )

    def _cancel_batch_restore(self) -> None:
        self._batch_restore_runner.cancel()
        self.cancel_batch_button.setEnabled(False)
        self._set_status("Cancelling batch...")

    def _finish_failed_batch_restore(self, exc: Exception) -> None:
        self._set_status(f"Cannot restore batch: {exc}")
        self._set_processing_indicator_visible(False)
        self.cancel_batch_button.setEnabled(True)
        self.cancel_batch_button.hide()
        self.start_batch_button.show()

    def _finish_batch_restore(self, result) -> None:
        summary = (
            f"{result.restored_count} restored, "
            f"{result.failed_count} failed, "
            f"{result.skipped_count} skipped, "
            f"{result.cancelled_count} cancelled."
        )
        self._set_status(
            "Batch complete",
            rows=[
                ("Restored", str(result.restored_count)),
                ("Failed", str(result.failed_count)),
                ("Skipped", str(result.skipped_count)),
                ("Cancelled", str(result.cancelled_count)),
            ],
            plain_text=f"Batch complete: {summary}",
        )
        self._set_processing_indicator_visible(False)
        self.cancel_batch_button.setEnabled(True)
        self.cancel_batch_button.hide()
        self.start_batch_button.show()

    def _append_batch_file_result(self, file_result) -> None:
        status = _batch_status_label(file_result.status)
        detail = (
            _short_path_label(file_result.output_path)
            if file_result.output_path is not None
            else file_result.message
        )
        item = QListWidgetItem(f"{file_result.source_path.name} - {status}: {detail}")
        row = _batch_result_row(
            filename=file_result.source_path.name,
            status=status,
            status_kind=file_result.status,
            detail=_readable_batch_detail(file_result.status, detail),
        )
        item.setSizeHint(row.sizeHint())
        self._batch_list.addItem(item)
        self._batch_list.setItemWidget(item, row)

    def _update_batch_progress(self, completed_count: int, total_count: int) -> None:
        self._set_batch_progress(f"{completed_count} of {total_count} files")

    def _set_batch_progress(self, message: str) -> None:
        self._batch_progress.setText(message)

    def _set_status(
        self,
        title: str,
        rows: list[tuple[str, str]] | None = None,
        tooltip: str | None = None,
        plain_text: str | None = None,
    ) -> None:
        self._status_plain_text = plain_text or title
        self._status_title.setText(title)
        if rows:
            self._status_details.setText(
                "\n".join(f"{label}: {value}" for label, value in rows)
            )
            self._status_details.show()
        else:
            self._status_details.clear()
            self._status_details.hide()
        self._status_card.setToolTip(tooltip or "")

    def _set_processing_indicator_visible(self, visible: bool) -> None:
        self._processing_indicator.setVisible(visible)

def _stylesheet() -> str:
    return """
    QMainWindow {
        background: #111214;
        color: #f2f3f5;
        font-family: "Segoe UI", "SF Pro Text", Arial, sans-serif;
        font-size: 14px;
    }

    #Sidebar {
        background: #181a1f;
        border-right: 1px solid #2c3038;
    }

    #PreviewArea {
        background: #101114;
    }

    #Title {
        color: #f6f7f9;
        font-size: 28px;
        font-weight: 600;
    }

    #SectionLabel {
        color: #aeb4be;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
    }

    #StatusCard {
        border: 1px solid #303641;
        border-radius: 8px;
        background: #12151a;
    }

    #StatusTitle {
        color: #f2f4f8;
        font-size: 15px;
        font-weight: 650;
    }

    #StatusDetails {
        color: #c9d0db;
        font-size: 13px;
        font-weight: 500;
        line-height: 135%;
    }

    #ProcessingIndicator {
        min-height: 6px;
        max-height: 6px;
        border: none;
        border-radius: 3px;
        background: #2c3038;
    }

    #ProcessingIndicator::chunk {
        border-radius: 3px;
        background: #2f80ed;
    }

    QPushButton {
        min-height: 36px;
        padding: 8px 14px;
        border: 1px solid #3a3f49;
        border-radius: 8px;
        background: #23262d;
        color: #eef1f5;
    }

    QPushButton:hover {
        border-color: #596170;
        background: #2a2e36;
    }

    QPushButton:checked {
        border-color: #2f80ed;
        color: #ffffff;
        background: #1d3f6e;
    }

    QPushButton:disabled {
        border-color: #2b2f36;
        background: #1b1d22;
        color: #737b87;
    }

    #PrimaryButton {
        border: none;
        border-radius: 18px;
        background: #2f80ed;
        color: #ffffff;
        font-weight: 600;
    }

    #PrimaryButton:hover {
        background: #4a90f3;
    }

    #PrimaryButton:disabled {
        background: #24415f;
        color: #8fa7c5;
    }

    #CompareView {
        border: 1px solid #2c3038;
        border-radius: 8px;
        background: #15171b;
        color: #aeb4be;
    }

    #BatchPanel {
        background: #15171b;
    }

    #BatchProgress {
        color: #f2f3f5;
        font-size: 20px;
        font-weight: 600;
    }

    #BatchList {
        border: 1px solid #2c3038;
        border-radius: 8px;
        background: #111318;
        color: #e4e7ec;
        font-size: 15px;
        padding: 8px;
    }

    #BatchList::item {
        border: none;
        margin: 0 0 8px 0;
        padding: 0;
    }

    #BatchResultItem {
        border: 1px solid #2a303a;
        border-radius: 8px;
        background: #151820;
    }

    #BatchFileName {
        color: #f1f4f8;
        font-size: 15px;
        font-weight: 650;
    }

    #BatchFileDetail {
        color: #aeb7c4;
        font-size: 13px;
        font-weight: 500;
    }

    #BatchStatusRestored,
    #BatchStatusSkipped,
    #BatchStatusFailed,
    #BatchStatusCancelled {
        min-width: 76px;
        min-height: 24px;
        padding: 4px 8px;
        border-radius: 10px;
        font-size: 12px;
        font-weight: 650;
    }

    #BatchStatusRestored {
        color: #d8f5e3;
        background: #1d5b38;
    }

    #BatchStatusSkipped {
        color: #d8dde6;
        background: #38404d;
    }

    #BatchStatusFailed {
        color: #ffe0e0;
        background: #743030;
    }

    #BatchStatusCancelled {
        color: #ffe8bd;
        background: #6b4b18;
    }
    """


def _batch_status_label(status: BatchFileStatus) -> str:
    if status is BatchFileStatus.RESTORED:
        return "Restored"
    if status is BatchFileStatus.FAILED:
        return "Failed"
    if status is BatchFileStatus.CANCELLED:
        return "Cancelled"
    return "Skipped"


def _short_path_label(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


def _readable_batch_detail(status: BatchFileStatus, detail: str) -> str:
    if status is BatchFileStatus.RESTORED:
        return f"Saved to {detail}"
    if detail.startswith("Unsupported file format:"):
        return detail.replace("Unsupported file format:", "Unsupported format", 1)
    if detail.startswith("Multi-page TIFF files are not supported."):
        return "Multi-page TIFF not supported. Use a single 2D image."
    return detail


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
