"""Qt-loop runner for Batch restore runs."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QTimer

from denoiser.ui.restore_task_runner import RestoreTaskRunner
from denoiser.workflow import (
    BatchFileResult,
    BatchRestoreResult,
    BatchRestoreRun,
    BatchRestoreStep,
)


BatchFileReported = Callable[[BatchFileResult], None]
BatchProgressChanged = Callable[[int, int], None]
BatchFinished = Callable[[BatchRestoreResult], None]
BatchFailed = Callable[[Exception], None]


class BatchRestoreRunner:
    """Run a Batch restore run one file at a time on the Qt loop."""

    def __init__(self, task_runner: RestoreTaskRunner | None = None) -> None:
        self._task_runner = task_runner or RestoreTaskRunner()
        self._run: BatchRestoreRun | None = None
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
        self._on_file_result = on_file_result
        self._on_progress_changed = on_progress_changed
        self._on_finished = on_finished
        self._on_failed = on_failed
        QTimer.singleShot(0, self._restore_next_file)

    def cancel(self) -> None:
        if self._run is not None:
            self._run.cancel()

    def _restore_next_file(self) -> None:
        assert self._run is not None
        self._task_runner.run(
            self._run.next_step,
            self._finish_step,
        )

    def _finish_step(
        self,
        step: object | None,
        exc: Exception | None,
    ) -> None:
        if exc is not None:
            self._fail_run(exc)
            return

        assert step is not None
        assert isinstance(step, BatchRestoreStep)
        assert self._on_file_result is not None
        assert self._on_progress_changed is not None
        for file_result in step.file_results:
            self._on_file_result(file_result)
        self._on_progress_changed(step.completed_count, step.total_count)
        if step.final_result is not None:
            self._finish_run(step.final_result)
            return
        QTimer.singleShot(0, self._restore_next_file)

    def _finish_run(self, result: BatchRestoreResult) -> None:
        assert self._on_finished is not None
        self._clear_run_state()
        self._on_finished(result)

    def _fail_run(self, exc: Exception) -> None:
        assert self._on_failed is not None
        self._clear_run_state()
        self._on_failed(exc)

    def _clear_run_state(self) -> None:
        self._run = None
