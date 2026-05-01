from __future__ import annotations

import os
from pathlib import Path
from time import monotonic

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


def test_single_ui_shows_processing_state_before_restore_work_starts(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    class RecordingEngine:
        called = False

        def restore(self, pixels, mode):
            self.called = True
            return pixels + 2

    engine = RecordingEngine()
    window = MainWindow(engine=engine)
    window.set_single_image_path(source)
    window.mode_button(DenoiseMode.LRSEM).click()

    window.restore_button.click()

    assert window.status_text() == "Restoring..."
    assert window.processing_indicator_visible()
    assert not window.restore_button.isEnabled()
    assert not window.mode_button(DenoiseMode.LRSEM).isEnabled()
    assert not engine.called

    process_events_until(app, lambda: engine.called)

    assert engine.called
    process_events_until(app, lambda: not window.processing_indicator_visible())
    assert not window.processing_indicator_visible()


def test_single_ui_restore_button_saves_output_and_updates_status(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):
            assert mode is DenoiseMode.LRSEM
            return pixels + 2

    window = MainWindow(engine=FakeEngine())
    window.set_single_image_path(source)
    window.mode_button(DenoiseMode.LRSEM).click()

    window.restore_button.click()
    process_events_until(app, lambda: window.status_text().startswith("Saved:"))

    output_path = tmp_path / "denoised_LRSEM" / "wafer.tif"
    assert output_path.is_file()
    assert window.status_text() == "Saved: wafer.tif\nFolder: denoised_LRSEM"
    assert window.status_tooltip() == str(output_path)
    assert window.restore_button.isEnabled()
    assert window.mode_button(DenoiseMode.LRSEM).isEnabled()
    compare_view = window.findChild(CompareView, "CompareView")
    assert compare_view is not None
    assert compare_view.has_images()
    assert compare_view.is_comparing()
    assert compare_view.divider_position() == 0.5


def test_single_ui_shows_overwrite_message_before_restore(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    window = MainWindow(engine=object())
    window.set_single_image_path(source)

    assert "Existing outputs will be overwritten." in window.status_text()
    assert window.status_tooltip() == str(source)
    assert window.status_text().startswith("Loading preview:")


def test_single_ui_previews_raw_image_after_selection(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    window = MainWindow(engine=object())
    window.set_single_image_path(source)

    compare_view = window.findChild(CompareView, "CompareView")
    assert compare_view is not None
    assert not compare_view.has_images()
    process_events_until(app, compare_view.has_images)
    assert compare_view.has_images()
    assert not compare_view.is_comparing()


def test_single_ui_warns_when_selected_image_is_large(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "large.tif"
    tifffile.imwrite(source, np.zeros((1537, 1), dtype=np.uint8))

    window = MainWindow(engine=object())
    window.set_single_image_path(source)

    assert window.status_text().startswith("Loading preview:")
    process_events_until(
        app,
        lambda: "Large images may take several minutes." in window.status_text(),
    )
    assert "Large images may take several minutes." in window.status_text()


def test_single_ui_rejects_unsupported_input_without_running_engine(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "wafer.bmp"
    source.write_bytes(b"not used")

    class EngineShouldNotRun:
        called = False

        def restore(self, pixels, mode):
            self.called = True
            return pixels

    engine = EngineShouldNotRun()
    window = MainWindow(engine=engine)
    window.set_single_image_path(source)

    window.restore_button.click()
    process_events_until(app, lambda: window.status_text().startswith("Cannot restore:"))

    assert not engine.called
    assert window.status_text().startswith("Cannot restore: Unsupported file format")
    assert not window.processing_indicator_visible()
    assert window.restore_button.isEnabled()
