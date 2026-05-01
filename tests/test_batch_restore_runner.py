from __future__ import annotations

import os
from pathlib import Path
from time import monotonic

import numpy as np
import tifffile
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from denoiser.engine import DenoiseMode
from denoiser.ui.batch_restore_runner import BatchRestoreRunner
from denoiser.workflow import BatchFileResult, BatchFileStatus, BatchRestoreRun


def process_events_until(app: QApplication, condition) -> None:
    deadline = monotonic() + 2
    while not condition():
        app.processEvents()
        if monotonic() > deadline:
            raise AssertionError("Timed out waiting for batch restore runner")


def test_batch_restore_runner_reports_file_results_progress_and_finish(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    unsupported = tmp_path / "notes.txt"
    supported = tmp_path / "wafer.tif"
    unsupported.write_text("skip me")
    tifffile.imwrite(supported, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):
            return pixels + 1

    runner = BatchRestoreRunner()
    run = BatchRestoreRun(tmp_path, DenoiseMode.HRSTEM, FakeEngine())
    file_results: list[BatchFileResult] = []
    progress_updates: list[tuple[int, int]] = []
    finished = []
    failures: list[Exception] = []

    runner.start(
        run,
        file_results.append,
        lambda completed, total: progress_updates.append((completed, total)),
        finished.append,
        failures.append,
    )

    process_events_until(app, lambda: bool(finished))

    assert failures == []
    assert [result.status for result in file_results] == [
        BatchFileStatus.SKIPPED,
        BatchFileStatus.RESTORED,
    ]
    assert progress_updates == [(1, 2), (2, 2)]
    assert finished[0].restored_count == 1
    assert finished[0].skipped_count == 1


def test_batch_restore_runner_cancels_remaining_files_after_current_file(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    for filename in ("a_first.tif", "b_second.tif", "c_third.tif"):
        tifffile.imwrite(tmp_path / filename, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):
            return pixels + 1

    runner = BatchRestoreRunner()
    run = BatchRestoreRun(tmp_path, DenoiseMode.LRSEM, FakeEngine())
    file_results: list[BatchFileResult] = []
    progress_updates: list[tuple[int, int]] = []
    finished = []

    def collect_and_cancel(file_result: BatchFileResult) -> None:
        file_results.append(file_result)
        if file_result.status is BatchFileStatus.RESTORED:
            runner.cancel()

    runner.start(
        run,
        collect_and_cancel,
        lambda completed, total: progress_updates.append((completed, total)),
        finished.append,
        lambda exc: None,
    )

    process_events_until(app, lambda: bool(finished))

    assert [result.status for result in file_results] == [
        BatchFileStatus.RESTORED,
        BatchFileStatus.CANCELLED,
        BatchFileStatus.CANCELLED,
    ]
    assert progress_updates == [(1, 3), (3, 3)]
    assert finished[0].restored_count == 1
    assert finished[0].cancelled_count == 2


def test_batch_restore_runner_reports_unexpected_runner_failure() -> None:
    app = QApplication.instance() or QApplication([])

    class ExplodingRun:
        def next_step(self):
            raise RuntimeError("runner failed")

        def cancel(self):
            pass

    runner = BatchRestoreRunner()
    failures: list[Exception] = []

    runner.start(
        ExplodingRun(),  # type: ignore[arg-type]
        lambda file_result: None,
        lambda completed, total: None,
        lambda result: None,
        failures.append,
    )

    process_events_until(app, lambda: bool(failures))

    assert isinstance(failures[0], RuntimeError)
    assert str(failures[0]) == "runner failed"
