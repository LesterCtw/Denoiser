"""Background restore task execution for the PySide6 UI."""

from __future__ import annotations

from queue import Empty, Queue
from threading import Thread
from typing import Callable

from PySide6.QtCore import QTimer


Task = Callable[[], object]
TaskFinished = Callable[[object | None, Exception | None], None]


class RestoreTaskRunner:
    """Run one restore task in a background thread and report back on the Qt loop."""

    def __init__(self, poll_interval_ms: int = 10) -> None:
        self._poll_interval_ms = poll_interval_ms
        self._active_thread: Thread | None = None

    def run(self, task: Task, on_finished: TaskFinished) -> None:
        result_queue: Queue[tuple[object | None, Exception | None]] = Queue(maxsize=1)

        def run_task() -> None:
            try:
                result_queue.put((task(), None))
            except Exception as exc:
                result_queue.put((None, exc))

        thread = Thread(target=run_task, daemon=True)
        self._active_thread = thread
        thread.start()
        QTimer.singleShot(
            self._poll_interval_ms,
            lambda: self._poll(result_queue, on_finished, thread),
        )

    def _poll(
        self,
        result_queue: Queue[tuple[object | None, Exception | None]],
        on_finished: TaskFinished,
        thread: Thread,
    ) -> None:
        try:
            result, exc = result_queue.get_nowait()
        except Empty:
            QTimer.singleShot(
                self._poll_interval_ms,
                lambda: self._poll(result_queue, on_finished, thread),
            )
            return

        if self._active_thread is not thread:
            return

        self._active_thread = None
        on_finished(result, exc)
