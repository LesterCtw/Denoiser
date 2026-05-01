from __future__ import annotations

import os
from threading import Event
from time import monotonic

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from denoiser.ui.restore_task_runner import RestoreTaskRunner


def process_events_until(app: QApplication, condition) -> None:
    deadline = monotonic() + 2
    while not condition():
        app.processEvents()
        if monotonic() > deadline:
            raise AssertionError("Timed out waiting for task runner")


def test_restore_task_runner_reports_success_on_qt_loop() -> None:
    app = QApplication.instance() or QApplication([])
    runner = RestoreTaskRunner(poll_interval_ms=1)
    received: list[tuple[object | None, Exception | None]] = []

    runner.run(lambda: "done", lambda result, exc: received.append((result, exc)))

    process_events_until(app, lambda: bool(received))

    assert received == [("done", None)]


def test_restore_task_runner_reports_exceptions_on_qt_loop() -> None:
    app = QApplication.instance() or QApplication([])
    runner = RestoreTaskRunner(poll_interval_ms=1)
    received: list[tuple[object | None, Exception | None]] = []

    def fail() -> object:
        raise RuntimeError("restore failed")

    runner.run(fail, lambda result, exc: received.append((result, exc)))

    process_events_until(app, lambda: bool(received))

    result, exc = received[0]
    assert result is None
    assert isinstance(exc, RuntimeError)
    assert str(exc) == "restore failed"


def test_restore_task_runner_ignores_stale_task_completion() -> None:
    app = QApplication.instance() or QApplication([])
    runner = RestoreTaskRunner(poll_interval_ms=1)
    release_first_task = Event()
    received: list[tuple[object | None, Exception | None]] = []

    def first_task() -> object:
        release_first_task.wait(timeout=2)
        return "first"

    runner.run(first_task, lambda result, exc: received.append((result, exc)))
    runner.run(lambda: "second", lambda result, exc: received.append((result, exc)))

    process_events_until(app, lambda: bool(received))
    release_first_task.set()

    assert received == [("second", None)]
