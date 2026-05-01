"""Application entry point."""

from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from denoiser.app_icon import load_application_icon
    from denoiser.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Denoiser")
    app.setOrganizationName("Denoiser")
    icon = load_application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    window.show()

    return app.exec()
