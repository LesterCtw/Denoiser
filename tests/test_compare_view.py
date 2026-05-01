from __future__ import annotations

import os
import time

import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
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


def test_compare_view_sets_raw_preview_without_comparison_divider() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)

    view.set_raw_image(np.full((100, 200), 120, dtype=np.float32))

    assert view.has_images()
    assert not view.is_comparing()


def test_compare_view_clears_stale_tooltip_when_showing_raw_preview() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.clear("Batch mode")

    view.set_raw_image(np.full((100, 200), 120, dtype=np.float32))

    assert view.toolTip() == ""


def test_compare_view_clears_stale_tooltip_when_showing_comparison() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.clear("Batch mode")

    view.set_images(
        np.zeros((100, 200), dtype=np.float32),
        np.ones((100, 200), dtype=np.float32),
    )

    assert view.toolTip() == ""


def test_compare_view_renders_raw_on_left_and_restored_on_right_after_restore() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)
    raw = np.zeros((100, 200), dtype=np.float32)
    raw[-1, -1] = 1
    restored = np.tile(np.linspace(0, 255, 200, dtype=np.float32), (100, 1))
    target = QImage(view.size(), QImage.Format.Format_RGB32)

    view.set_images(raw, restored)
    view.render(target)

    left_pixel = QColor(target.pixel(100, 300))
    right_pixel = QColor(target.pixel(700, 300))
    assert left_pixel.lightness() < 20
    assert right_pixel.lightness() > 200


def test_compare_view_divider_does_not_render_wide_white_rail() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)
    pixels = np.full((100, 200), 127, dtype=np.float32)
    pixels[0, 0] = 0
    pixels[-1, -1] = 255
    target = QImage(view.size(), QImage.Format.Format_RGB32)

    view.set_images(pixels, pixels)
    view.render(target)

    divider_x = 400
    sample_y = 180
    near_white_pixels = [
        QColor(target.pixel(x, sample_y)).lightness()
        for x in range(divider_x - 4, divider_x + 5)
        if QColor(target.pixel(x, sample_y)).lightness() > 245
    ]
    assert len(near_white_pixels) <= 1


def test_compare_view_divider_stays_visible_on_dark_light_and_mid_gray_regions() -> None:
    app = QApplication.instance() or QApplication([])
    for background_value in (0, 127, 255):
        view = CompareView()
        view.resize(800, 600)
        pixels = np.full((100, 200), background_value, dtype=np.float32)
        pixels[0, 0] = 0
        pixels[-1, -1] = 255
        target = QImage(view.size(), QImage.Format.Format_RGB32)

        view.set_images(pixels, pixels)
        view.render(target)

        divider_x = 400
        sample_y = 180
        background_lightness = QColor(target.pixel(divider_x - 20, sample_y)).lightness()
        divider_lightnesses = [
            QColor(target.pixel(x, sample_y)).lightness()
            for x in range(divider_x - 3, divider_x + 4)
        ]
        assert max(abs(value - background_lightness) for value in divider_lightnesses) >= 50


def test_compare_view_handle_is_not_filled_with_white() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)
    pixels = np.full((100, 200), 127, dtype=np.float32)
    pixels[0, 0] = 0
    pixels[-1, -1] = 255
    target = QImage(view.size(), QImage.Format.Format_RGB32)

    view.set_images(pixels, pixels)
    view.render(target)

    handle_center = QColor(target.pixel(400, 300))
    assert handle_center.lightness() < 220


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


def test_compare_view_first_drag_rendering_stays_responsive_for_1024_image() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)
    raw = np.zeros((1024, 1024), dtype=np.float32)
    restored = np.tile(np.linspace(0, 255, 1024, dtype=np.float32), (1024, 1))
    target = QImage(view.size(), QImage.Format.Format_RGB32)

    view.set_images(raw, restored)
    start = time.perf_counter()
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(200, 300))
    for x in range(208, 550, 8):
        QTest.mouseMove(view, QPoint(x, 300))
        view.render(target)
    QTest.mouseMove(view, QPoint(550, 300))
    view.render(target)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(600, 300))
    elapsed = time.perf_counter() - start

    assert view.divider_position() == 0.75
    assert elapsed < 0.02


def test_compare_view_renders_loaded_images() -> None:
    app = QApplication.instance() or QApplication([])
    view = CompareView()
    view.resize(800, 600)
    view.set_images(np.zeros((100, 200), dtype=np.float32), np.ones((100, 200), dtype=np.float32))
    target = QPixmap(view.size())

    view.render(target)

    assert not target.isNull()
