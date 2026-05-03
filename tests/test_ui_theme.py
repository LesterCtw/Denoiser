from __future__ import annotations

import os

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QFrame, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from denoiser.ui.compare_view import CompareView
from denoiser.ui.main_window import MainWindow
from denoiser.ui.theme import main_window_stylesheet


def _rendered_average_lightness(widget: QWidget) -> float:
    image = QImage(widget.size(), QImage.Format.Format_RGB32)
    widget.render(image)
    step = max(1, min(image.width(), image.height()) // 12)
    samples = [
        QColor(image.pixel(x, y)).lightness()
        for y in range(step // 2, image.height(), step)
        for x in range(step // 2, image.width(), step)
    ]
    return sum(samples) / len(samples)


def test_main_ui_surfaces_launch_with_dark_theme() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(engine=object())
    window.show()
    app.processEvents()

    sidebar = window.findChild(QFrame, "Sidebar")
    preview = window.findChild(QFrame, "PreviewArea")
    compare_view = window.findChild(CompareView, "CompareView")

    assert sidebar is not None
    assert preview is not None
    assert compare_view is not None
    assert _rendered_average_lightness(sidebar) < 95
    assert _rendered_average_lightness(preview) < 75
    assert _rendered_average_lightness(compare_view) < 95


def test_batch_theme_and_disabled_controls_remain_readable_in_dark_theme() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(engine=object())
    window.show()
    window.show_batch_mode()
    window.start_batch_button.setEnabled(False)
    app.processEvents()

    batch_panel = window.findChild(QFrame, "BatchPanel")

    assert batch_panel is not None
    assert _rendered_average_lightness(batch_panel) < 75
    assert 25 < _rendered_average_lightness(window.start_batch_button) < 140


def test_main_window_stylesheet_contains_batch_result_selectors() -> None:
    stylesheet = main_window_stylesheet()

    assert "#BatchResultItem" in stylesheet
    assert "#BatchStatusRestored" in stylesheet
    assert "#BatchStatusFailed" in stylesheet
