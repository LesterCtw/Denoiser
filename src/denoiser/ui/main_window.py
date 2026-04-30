"""Main Denoiser window skeleton."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from denoiser.engine import DenoiseMode, OnnxDenoiser
from denoiser.image_io import ImageFormatError, image_requires_patch_based
from denoiser.ui.compare_view import CompareView
from denoiser.workflow import (
    BatchFileResult,
    BatchFileStatus,
    BatchRestoreResult,
    RestoreEngine,
    batch_input_paths,
    restore_batch_file,
    restore_single_image,
)


class MainWindow(QMainWindow):
    def __init__(self, engine: RestoreEngine | None = None) -> None:
        super().__init__()
        self._engine = engine or OnnxDenoiser()
        self._single_image_path: Path | None = None
        self._batch_folder_path: Path | None = None
        self._mode_buttons: dict[DenoiseMode, QPushButton] = {}
        self._batch_mode: DenoiseMode = DenoiseMode.HRSTEM
        self._batch_paths: list[Path] = []
        self._batch_results: list[BatchFileResult] = []
        self._batch_index = 0
        self._batch_cancel_requested = False

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
        self._compare_view.clear(f"Selected image: {self._single_image_path}")
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
        self.restore_button.setEnabled(False)
        self._set_status("Restoring...")
        try:
            result = restore_single_image(self._single_image_path, mode, self._engine)
        except Exception as exc:
            self._set_status(f"Cannot restore: {exc}")
        else:
            self._set_status(f"Saved: {result.output_path}")
            self._compare_view.set_images(result.raw_pixels, result.restored_pixels)
        finally:
            self.restore_button.setEnabled(True)

    def _restore_batch_folder(self) -> None:
        if self._batch_folder_path is None:
            self._set_status("Add a folder before starting Batch.")
            return

        self._batch_mode = self._selected_mode()
        self._batch_paths = batch_input_paths(self._batch_folder_path)
        self._batch_results = []
        self._batch_index = 0
        self._batch_cancel_requested = False
        self._batch_list.clear()
        self._set_batch_progress(f"0 of {len(self._batch_paths)} files")
        self._set_status("Batch restoring...")
        self.start_batch_button.hide()
        self.cancel_batch_button.show()
        QTimer.singleShot(0, self._restore_next_batch_file)

    def _cancel_batch_restore(self) -> None:
        self._batch_cancel_requested = True
        self.cancel_batch_button.setEnabled(False)
        self._set_status("Cancelling batch...")

    def _restore_next_batch_file(self) -> None:
        if self._batch_cancel_requested:
            self._cancel_remaining_batch_files()
            self._finish_batch_restore()
            return

        if self._batch_index >= len(self._batch_paths):
            self._finish_batch_restore()
            return

        path = self._batch_paths[self._batch_index]
        file_result = restore_batch_file(path, self._batch_mode, self._engine)
        self._batch_results.append(file_result)
        self._append_batch_file_result(file_result)
        self._batch_index += 1
        self._set_batch_progress(f"{self._batch_index} of {len(self._batch_paths)} files")
        QTimer.singleShot(0, self._restore_next_batch_file)

    def _cancel_remaining_batch_files(self) -> None:
        for path in self._batch_paths[self._batch_index :]:
            file_result = BatchFileResult(
                source_path=path,
                status=BatchFileStatus.CANCELLED,
                message="Not processed",
            )
            self._batch_results.append(file_result)
            self._append_batch_file_result(file_result)

        self._batch_index = len(self._batch_paths)
        self._set_batch_progress(f"{self._batch_index} of {len(self._batch_paths)} files")

    def _finish_batch_restore(self) -> None:
        result = BatchRestoreResult(
            folder_path=self._batch_folder_path or Path(),
            mode=self._batch_mode,
            file_results=self._batch_results,
        )
        self._set_status(
            "Batch complete: "
            f"{result.restored_count} restored, "
            f"{result.failed_count} failed, "
            f"{result.skipped_count} skipped, "
            f"{result.cancelled_count} cancelled."
        )
        self.cancel_batch_button.setEnabled(True)
        self.cancel_batch_button.hide()
        self.start_batch_button.show()

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

    def _set_batch_progress(self, message: str) -> None:
        self._batch_progress.setText(message)

    def _set_status(self, message: str) -> None:
        self._status.setText(message)


def _stylesheet() -> str:
    return """
    QMainWindow {
        background: #ffffff;
        color: #1d1d1f;
        font-family: "Segoe UI", "SF Pro Text", Arial, sans-serif;
        font-size: 14px;
    }

    #Sidebar {
        background: #f5f5f7;
        border-right: 1px solid #e0e0e0;
    }

    #PreviewArea {
        background: #ffffff;
    }

    #Title {
        color: #1d1d1f;
        font-size: 28px;
        font-weight: 600;
    }

    #SectionLabel {
        color: #7a7a7a;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
    }

    #StatusText {
        color: #7a7a7a;
        font-size: 13px;
    }

    QPushButton {
        min-height: 36px;
        padding: 8px 14px;
        border: 1px solid #d2d2d7;
        border-radius: 8px;
        background: #ffffff;
        color: #1d1d1f;
    }

    QPushButton:hover {
        border-color: #b8b8bd;
    }

    QPushButton:checked {
        border-color: #0066cc;
        color: #0066cc;
        background: #eef6ff;
    }

    #PrimaryButton {
        border: none;
        border-radius: 18px;
        background: #0066cc;
        color: #ffffff;
        font-weight: 600;
    }

    #PrimaryButton:hover {
        background: #0071e3;
    }

    #CompareView {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        background: #fafafc;
        color: #7a7a7a;
    }

    #BatchPanel {
        background: #ffffff;
    }

    #BatchProgress {
        color: #1d1d1f;
        font-size: 17px;
        font-weight: 600;
    }

    #BatchList {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        background: #fafafc;
        color: #1d1d1f;
        padding: 8px;
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
