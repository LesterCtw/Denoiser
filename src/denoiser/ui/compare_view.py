"""Before/after image comparison widget."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
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
        self._divider_position = 0.5
        self.update()

    def set_raw_image(self, raw_pixels: np.ndarray) -> None:
        raw = np.asarray(raw_pixels)
        if raw.ndim != 2:
            raise ValueError("CompareView only supports 2D images.")

        self._raw_image = _to_display_image(raw)
        self._restored_image = None
        self._divider_position = 0.5
        self.update()

    def clear(self, message: str | None = None) -> None:
        self._raw_image = None
        self._restored_image = None
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

        painter.drawImage(QRectF(image_rect), self._raw_image)

        if not self.is_comparing():
            return

        assert self._restored_image is not None
        divider_x = image_rect.left() + image_rect.width() * self._divider_position
        restored_clip = QRectF(image_rect)
        restored_clip.setLeft(divider_x)
        painter.save()
        painter.setClipRect(restored_clip)
        painter.drawImage(QRectF(image_rect), self._restored_image)
        painter.restore()

        pen = QPen(QColor("#ffffff"))
        pen.setWidth(7)
        painter.setPen(pen)
        painter.drawLine(int(divider_x), image_rect.top(), int(divider_x), image_rect.bottom())

        pen = QPen(QColor("#0066cc"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(int(divider_x), image_rect.top(), int(divider_x), image_rect.bottom())

        handle_radius = 10
        handle_center_y = image_rect.center().y()
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#0066cc"), 2))
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
