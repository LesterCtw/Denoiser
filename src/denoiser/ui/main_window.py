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
        self._batch_run: BatchRestoreRun | None = None
        self._batch_cancel_requested = False
        self._restore_task_runner = RestoreTaskRunner()

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

        message = f"Selected: {self._single_image_path.name}. Existing outputs will be overwritten."
        try:
            if image_requires_patch_based(self._single_image_path):
                message += " Large images may take several minutes."
        except ImageFormatError:
            pass
        self._set_status(message)

    def mode_button(self, mode: DenoiseMode) -> QPushButton:
        return self._mode_buttons[mode]

    def status_text(self) -> str:
        return self._status.text()

    def show_batch_mode(self) -> None:
        self._batch_button.click()

    def show_single_mode(self) -> None:
        self._single_button.click()

    def set_batch_folder_path(self, path: Path) -> None:
        self._batch_folder_path = Path(path)
        self._batch_list.clear()
        self._set_batch_progress("0 of 0 files")
        self._set_status(f"Batch folder: {self._batch_folder_path}")

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

        self._status = QLabel("Ready")
        self._status.setObjectName("StatusText")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

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
            self._set_status(f"Saved: {result.output_path}")
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

        self._batch_run = BatchRestoreRun(
            self._batch_folder_path,
            self._selected_mode(),
            self._engine,
        )
        self._batch_cancel_requested = False
        self._batch_list.clear()
        self._update_batch_progress()
        self._set_processing_indicator_visible(True)
        self._set_status("Batch restoring...")
        self.start_batch_button.hide()
        self.cancel_batch_button.show()
        QApplication.processEvents()
        QTimer.singleShot(0, self._restore_next_batch_file)

    def _cancel_batch_restore(self) -> None:
        self._batch_cancel_requested = True
        self.cancel_batch_button.setEnabled(False)
        self._set_status("Cancelling batch...")

    def _restore_next_batch_file(self) -> None:
        assert self._batch_run is not None
        if self._batch_cancel_requested:
            self._append_batch_file_results(self._batch_run.cancel_remaining())
            self._update_batch_progress()
            self._finish_batch_restore()
            return

        if self._batch_run.completed_count >= self._batch_run.total_count:
            self._finish_batch_restore()
            return

        self._restore_task_runner.run(
            self._batch_run.next_file_result,
            self._finish_batch_file_restore,
        )

    def _finish_batch_file_restore(self, file_result, exc: Exception | None) -> None:
        assert self._batch_run is not None
        if exc is not None:
            self._finish_failed_batch_restore(exc)
            return
        assert file_result is not None
        self._append_batch_file_result(file_result)
        self._update_batch_progress()
        QTimer.singleShot(0, self._restore_next_batch_file)

    def _finish_failed_batch_restore(self, exc: Exception) -> None:
        self._set_status(f"Cannot restore batch: {exc}")
        self._set_processing_indicator_visible(False)
        self.cancel_batch_button.setEnabled(True)
        self.cancel_batch_button.hide()
        self.start_batch_button.show()

    def _finish_batch_restore(self) -> None:
        assert self._batch_run is not None
        result = self._batch_run.result()
        self._set_status(
            "Batch complete: "
            f"{result.restored_count} restored, "
            f"{result.failed_count} failed, "
            f"{result.skipped_count} skipped, "
            f"{result.cancelled_count} cancelled."
        )
        self._set_processing_indicator_visible(False)
        self.cancel_batch_button.setEnabled(True)
        self.cancel_batch_button.hide()
        self.start_batch_button.show()

    def _append_batch_file_results(self, file_results) -> None:
        for file_result in file_results:
            self._append_batch_file_result(file_result)

    def _append_batch_file_result(self, file_result) -> None:
        status = _batch_status_label(file_result.status)
        detail = (
            str(file_result.output_path)
            if file_result.output_path is not None
            else file_result.message
        )
        self._batch_list.addItem(
            f"{file_result.source_path.name} - {status}: {detail}"
        )

    def _update_batch_progress(self) -> None:
        assert self._batch_run is not None
        self._set_batch_progress(
            f"{self._batch_run.completed_count} of {self._batch_run.total_count} files"
        )

    def _set_batch_progress(self, message: str) -> None:
        self._batch_progress.setText(message)

    def _set_status(self, message: str) -> None:
        self._status.setText(message)

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

    #StatusText {
        color: #c2c7d0;
        font-size: 13px;
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
        font-size: 17px;
        font-weight: 600;
    }

    #BatchList {
        border: 1px solid #2c3038;
        border-radius: 8px;
        background: #111318;
        color: #e4e7ec;
        padding: 8px;
    }

    #BatchList::item {
        padding: 4px;
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
