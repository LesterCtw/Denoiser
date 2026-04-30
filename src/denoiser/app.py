"""Application entry point."""

from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from denoiser.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Denoiser")
    app.setOrganizationName("Denoiser")

    window = MainWindow()
    window.show()

    return app.exec()
