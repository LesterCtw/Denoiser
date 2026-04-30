from __future__ import annotations

import os
from time import monotonic
from pathlib import Path

import numpy as np
import tifffile
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from denoiser.engine import DenoiseMode
from denoiser.ui.compare_view import CompareView
from denoiser.ui.main_window import MainWindow


def process_events_until(app: QApplication, condition) -> None:
    deadline = monotonic() + 2
    while not condition():
        app.processEvents()
        if monotonic() > deadline:
            raise AssertionError("Timed out waiting for UI update")


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
    process_events_until(app, lambda: window.status_text().startswith("Batch complete:"))

    output = tmp_path / "denoised_HRSEM" / "wafer.tif"
    assert output.is_file()
    assert "Batch complete: 1 restored, 0 failed, 1 skipped, 0 cancelled." in window.status_text()
    assert window.batch_progress_text() == "2 of 2 files"
    assert any("wafer.tif - Restored" in text for text in window.batch_status_texts())
    assert any("notes.txt - Skipped" in text for text in window.batch_status_texts())
    compare_view = window.findChild(CompareView, "CompareView")
    assert compare_view is not None
    assert not compare_view.has_images()


def test_batch_ui_reports_failed_files_and_summary(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    failing = tmp_path / "a_fails.tif"
    later = tmp_path / "b_later.tif"
    tifffile.imwrite(failing, np.array([[10, 20], [30, 40]], dtype=np.uint8))
    tifffile.imwrite(later, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class PartlyFailingEngine:
        def restore(self, pixels, mode):
            if pixels[0, 0] == 10:
                raise RuntimeError("model crashed")
            return pixels + 1

    window = MainWindow(engine=PartlyFailingEngine())
    window.show_batch_mode()
    window.set_batch_folder_path(tmp_path)

    window.start_batch_button.click()
    process_events_until(app, lambda: window.status_text().startswith("Batch complete:"))

    assert "Batch complete: 1 restored, 1 failed, 0 skipped, 0 cancelled." in window.status_text()
    assert any("a_fails.tif - Failed: model crashed" in text for text in window.batch_status_texts())
    assert any("b_later.tif - Restored" in text for text in window.batch_status_texts())


def test_batch_ui_can_cancel_remaining_files_between_restores(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    for filename in ("a_first.tif", "b_second.tif", "c_third.tif"):
        tifffile.imwrite(tmp_path / filename, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class FakeEngine:
        restore_count = 0

        def restore(self, pixels, mode):
            self.restore_count += 1
            return pixels + self.restore_count

    engine = FakeEngine()
    window = MainWindow(engine=engine)
    window.show()
    window.show_batch_mode()
    window.set_batch_folder_path(tmp_path)

    window.start_batch_button.click()
    assert window.cancel_batch_button.isVisible()
    assert not window.start_batch_button.isVisible()

    process_events_until(app, lambda: engine.restore_count == 1)
    window.cancel_batch_button.click()
    process_events_until(app, lambda: window.status_text().startswith("Batch complete:"))

    assert "Batch complete: 1 restored, 0 failed, 0 skipped, 2 cancelled." in window.status_text()
    assert engine.restore_count == 1
    assert any("b_second.tif - Cancelled: Not processed" in text for text in window.batch_status_texts())
    assert any("c_third.tif - Cancelled: Not processed" in text for text in window.batch_status_texts())
    assert window.start_batch_button.isVisible()
    assert not window.cancel_batch_button.isVisible()
