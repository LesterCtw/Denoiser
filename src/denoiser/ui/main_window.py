"""Main Denoiser window skeleton."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from denoiser.engine import DenoiseMode, OnnxDenoiser
from denoiser.ui.compare_view import CompareView
from denoiser.workflow import RestoreEngine, restore_single_image


class MainWindow(QMainWindow):
    def __init__(self, engine: RestoreEngine | None = None) -> None:
        super().__init__()
        self._engine = engine or OnnxDenoiser()
        self._single_image_path: Path | None = None
        self._mode_buttons: dict[DenoiseMode, QPushButton] = {}

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
        self._set_status(
            f"Selected: {self._single_image_path.name}. Existing outputs will be overwritten."
        )

    def mode_button(self, mode: DenoiseMode) -> QPushButton:
        return self._mode_buttons[mode]

    def status_text(self) -> str:
        return self._status.text()

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
        single_button = QPushButton("Single")
        single_button.setCheckable(True)
        single_button.setChecked(True)
        batch_button = QPushButton("Batch")
        batch_button.setCheckable(True)

        workflow_group = QButtonGroup(sidebar)
        workflow_group.setExclusive(True)
        workflow_group.addButton(single_button)
        workflow_group.addButton(batch_button)

        mode_row.addWidget(single_button)
        mode_row.addWidget(batch_button)
        layout.addLayout(mode_row)

        open_image_button = QPushButton("Open Image")
        open_image_button.clicked.connect(self._open_single_image)
        layout.addWidget(open_image_button)

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

        self._compare_view = CompareView()
        self._compare_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._compare_view, 1, Qt.AlignmentFlag.AlignCenter)

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
    """
