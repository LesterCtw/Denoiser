from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import tifffile
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from denoiser.engine import DenoiseMode
from denoiser.ui.compare_view import CompareView
from denoiser.ui.main_window import MainWindow


def test_batch_ui_can_switch_between_single_and_batch_modes() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(engine=object())
    window.show()

    window.show_batch_mode()
    assert window.status_text() == "Select a folder for Batch mode."
    assert window.start_batch_button.isVisible()
    assert not window.restore_button.isVisible()

    window.show_single_mode()
    assert window.status_text() == "Ready"
    assert window.restore_button.isVisible()
    assert not window.start_batch_button.isVisible()


def test_batch_ui_restores_folder_and_shows_progress_status(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    supported = tmp_path / "wafer.tif"
    unsupported = tmp_path / "notes.txt"
    tifffile.imwrite(supported, np.array([[10, 20], [30, 40]], dtype=np.uint8))
    unsupported.write_text("skip me")

    class FakeEngine:
        def restore(self, pixels, mode):
            assert mode is DenoiseMode.HRSEM
            return pixels + 4

    window = MainWindow(engine=FakeEngine())
    window.show_batch_mode()
    window.set_batch_folder_path(tmp_path)
    window.mode_button(DenoiseMode.HRSEM).click()

    window.start_batch_button.click()

    output = tmp_path / "denoised_HRSEM" / "wafer.tif"
    assert output.is_file()
    assert "Batch complete: 1 restored, 1 skipped." in window.status_text()
    assert window.batch_progress_text() == "2 of 2 files"
    assert any("wafer.tif - Restored" in text for text in window.batch_status_texts())
    assert any("notes.txt - Skipped" in text for text in window.batch_status_texts())
    compare_view = window.findChild(CompareView, "CompareView")
    assert compare_view is not None
    assert not compare_view.has_images()
