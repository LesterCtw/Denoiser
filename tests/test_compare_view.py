from __future__ import annotations

import os

import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from denoiser.ui.compare_view import CompareView


def test_compare_view_sets_images_with_initial_half_divider_without_mutating_inputs() -> None:
    app = QApplication.instance() or QApplication([])
    raw = np.array([[0, 100], [200, 300]], dtype=np.float32)
    restored = raw + 10
    raw_before = raw.copy()
    restored_before = restored.copy()

    view = CompareView()
    view.set_images(raw, restored)

    assert view.has_images()
    assert view.divider_position() == 0.5
    np.testing.assert_array_equal(raw, raw_before)
    np.testing.assert_array_equal(restored, restored_before)


def test_compare_view_click_jumps_divider_to_clicked_position() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)
    view.set_images(np.zeros((100, 200), dtype=np.float32), np.ones((100, 200), dtype=np.float32))

    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(200, 300))

    assert view.divider_position() == 0.25


def test_compare_view_drag_updates_divider_position() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)
    view.set_images(np.zeros((100, 200), dtype=np.float32), np.ones((100, 200), dtype=np.float32))

    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(200, 300))
    QTest.mouseMove(view, QPoint(600, 300))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(600, 300))

    assert view.divider_position() == 0.75


def test_compare_view_renders_loaded_images() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)
    view.set_images(np.zeros((100, 200), dtype=np.float32), np.ones((100, 200), dtype=np.float32))
    target = QPixmap(view.size())

    view.render(target)

    assert not target.isNull()
