"""Before/after image comparison widget."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class CompareView(QWidget):
    """Fit-to-window raw/restored image comparison view."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(640, 480)
        self.setObjectName("CompareView")
        self.setMouseTracking(True)

        self._raw_image: QImage | None = None
        self._restored_image: QImage | None = None
        self._scaled_raw: QPixmap | None = None
        self._scaled_restored: QPixmap | None = None
        self._scaled_rect = QRect()
        self._divider_position = 0.5
        self._dragging = False

    def set_images(self, raw_pixels: np.ndarray, restored_pixels: np.ndarray) -> None:
        raw = np.asarray(raw_pixels)
        restored = np.asarray(restored_pixels)
        if raw.ndim != 2 or restored.ndim != 2:
            raise ValueError("CompareView only supports 2D images.")
        if raw.shape != restored.shape:
            raise ValueError("Raw and restored images must have the same shape.")

        self._raw_image = _to_display_image(raw)
        self._restored_image = _to_display_image(restored)
        self.setToolTip("")
        self._divider_position = 0.5
        self._rebuild_scaled_images()
        self.update()

    def set_raw_image(self, raw_pixels: np.ndarray) -> None:
        raw = np.asarray(raw_pixels)
        if raw.ndim != 2:
            raise ValueError("CompareView only supports 2D images.")

        self._raw_image = _to_display_image(raw)
        self._restored_image = None
        self.setToolTip("")
        self._divider_position = 0.5
        self._rebuild_scaled_images()
        self.update()

    def clear(self, message: str | None = None) -> None:
        self._raw_image = None
        self._restored_image = None
        self._clear_scaled_images()
        self._divider_position = 0.5
        self.setToolTip(message or "")
        self.update()

    def has_images(self) -> bool:
        return self._raw_image is not None

    def is_comparing(self) -> bool:
        return self._raw_image is not None and self._restored_image is not None

    def divider_position(self) -> float:
        return self._divider_position

    def set_divider_position(self, value: float) -> None:
        self._divider_position = max(0.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        if not self.has_images():
            painter.setPen(Qt.GlobalColor.darkGray)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Open an image to preview it here.")
            return

        image_rect = self._image_rect()
        assert self._raw_image is not None
        self._ensure_scaled_images(image_rect)
        assert self._scaled_raw is not None

        painter.drawPixmap(image_rect.topLeft(), self._scaled_raw)

        if not self.is_comparing():
            return

        assert self._restored_image is not None
        assert self._scaled_restored is not None
        divider_x = image_rect.left() + image_rect.width() * self._divider_position
        restored_clip = QRectF(image_rect)
        restored_clip.setLeft(divider_x)
        painter.save()
        painter.setClipRect(restored_clip)
        painter.drawPixmap(image_rect.topLeft(), self._scaled_restored)
        painter.restore()

        pen = QPen(QColor("#202020"))
        pen.setWidth(5)
        painter.setPen(pen)
        painter.drawLine(int(divider_x), image_rect.top(), int(divider_x), image_rect.bottom())

        pen = QPen(QColor("#2f80ed"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(int(divider_x), image_rect.top(), int(divider_x), image_rect.bottom())

        handle_radius = 10
        handle_center_y = image_rect.center().y()
        painter.setBrush(QColor("#2f80ed"))
        painter.setPen(QPen(QColor("#202020"), 3))
        painter.drawEllipse(
            int(divider_x) - handle_radius,
            handle_center_y - handle_radius,
            handle_radius * 2,
            handle_radius * 2,
        )

    def _image_rect(self) -> QRect:
        if self._raw_image is None:
            return self.rect()

        available = self.rect()
        image_size = self._raw_image.size()
        image_size.scale(available.size(), Qt.AspectRatioMode.KeepAspectRatio)
        top_left = QPoint(
            available.left() + (available.width() - image_size.width()) // 2,
            available.top() + (available.height() - image_size.height()) // 2,
        )
        return QRect(top_left, image_size)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._clear_scaled_images()
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.is_comparing():
            self._dragging = True
            self._set_divider_from_point(event.position().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._set_divider_from_point(event.position().toPoint())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def _set_divider_from_point(self, point: QPoint) -> None:
        image_rect = self._image_rect()
        if image_rect.width() <= 0:
            return
        self.set_divider_position((point.x() - image_rect.left()) / image_rect.width())

    def _ensure_scaled_images(self, image_rect: QRect) -> None:
        needs_restored = self._restored_image is not None and self._scaled_restored is None
        if self._scaled_rect != image_rect or self._scaled_raw is None or needs_restored:
            self._rebuild_scaled_images()

    def _rebuild_scaled_images(self) -> None:
        if self._raw_image is None:
            self._clear_scaled_images()
            return

        image_rect = self._image_rect()
        if image_rect.width() <= 0 or image_rect.height() <= 0:
            self._clear_scaled_images()
            return

        self._scaled_rect = image_rect
        self._scaled_raw = QPixmap.fromImage(_scaled_image(self._raw_image, image_rect))
        self._scaled_restored = (
            QPixmap.fromImage(_scaled_image(self._restored_image, image_rect))
            if self._restored_image is not None
            else None
        )

    def _clear_scaled_images(self) -> None:
        self._scaled_raw = None
        self._scaled_restored = None
        self._scaled_rect = QRect()


def _to_display_image(pixels: np.ndarray) -> QImage:
    source = np.asarray(pixels, dtype=np.float32)
    display = np.nan_to_num(source, copy=True)
    minimum = float(display.min())
    maximum = float(display.max())
    if maximum > minimum:
        display = (display - minimum) * (255.0 / (maximum - minimum))
    else:
        display = np.zeros(display.shape, dtype=np.float32)

    grayscale = np.ascontiguousarray(np.clip(display, 0, 255).astype(np.uint8))
    height, width = grayscale.shape
    return QImage(grayscale.data, width, height, width, QImage.Format.Format_Grayscale8).copy()


def _scaled_image(image: QImage, image_rect: QRect) -> QImage:
    return image.scaled(
        image_rect.size(),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
