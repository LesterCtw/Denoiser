"""Qt-loop runner for Batch restore runs."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QTimer

from denoiser.ui.restore_task_runner import RestoreTaskRunner
from denoiser.workflow import BatchFileResult, BatchRestoreResult, BatchRestoreRun


BatchFileReported = Callable[[BatchFileResult], None]
BatchProgressChanged = Callable[[int, int], None]
BatchFinished = Callable[[BatchRestoreResult], None]
BatchFailed = Callable[[Exception], None]


class BatchRestoreRunner:
    """Run a Batch restore run one file at a time on the Qt loop."""

    def __init__(self, task_runner: RestoreTaskRunner | None = None) -> None:
        self._task_runner = task_runner or RestoreTaskRunner()
        self._run: BatchRestoreRun | None = None
        self._cancel_requested = False
        self._on_file_result: BatchFileReported | None = None
        self._on_progress_changed: BatchProgressChanged | None = None
        self._on_finished: BatchFinished | None = None
        self._on_failed: BatchFailed | None = None

    def start(
        self,
        run: BatchRestoreRun,
        on_file_result: BatchFileReported,
        on_progress_changed: BatchProgressChanged,
        on_finished: BatchFinished,
        on_failed: BatchFailed,
    ) -> None:
        self._run = run
        self._cancel_requested = False
        self._on_file_result = on_file_result
        self._on_progress_changed = on_progress_changed
        self._on_finished = on_finished
        self._on_failed = on_failed
        QTimer.singleShot(0, self._restore_next_file)

    def cancel(self) -> None:
        self._cancel_requested = True

    def _restore_next_file(self) -> None:
        assert self._run is not None
        if self._cancel_requested:
            self._finish_cancelled_run()
            return

        if self._run.completed_count >= self._run.total_count:
            self._finish_run()
            return

        self._task_runner.run(
            self._run.next_file_result,
            self._finish_file_restore,
        )

    def _finish_file_restore(
        self,
        file_result: object | None,
        exc: Exception | None,
    ) -> None:
        if exc is not None:
            self._fail_run(exc)
            return

        assert file_result is not None
        assert isinstance(file_result, BatchFileResult)
        assert self._on_file_result is not None
        self._on_file_result(file_result)
        self._notify_progress_changed()
        QTimer.singleShot(0, self._restore_next_file)

    def _finish_cancelled_run(self) -> None:
        assert self._run is not None
        assert self._on_file_result is not None
        for file_result in self._run.cancel_remaining():
            self._on_file_result(file_result)
        self._notify_progress_changed()
        self._finish_run()

    def _finish_run(self) -> None:
        assert self._run is not None
        assert self._on_finished is not None
        result = self._run.result()
        self._clear_run_state()
        self._on_finished(result)

    def _fail_run(self, exc: Exception) -> None:
        assert self._on_failed is not None
        self._clear_run_state()
        self._on_failed(exc)

    def _notify_progress_changed(self) -> None:
        assert self._run is not None
        assert self._on_progress_changed is not None
        self._on_progress_changed(self._run.completed_count, self._run.total_count)

    def _clear_run_state(self) -> None:
        self._run = None
        self._cancel_requested = False
