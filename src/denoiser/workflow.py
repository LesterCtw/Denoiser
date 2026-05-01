"""User-facing restore workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from denoiser.engine import DenoiseMode
from denoiser.image_io import ImageFormatError, load_image, save_restored_image


class RestoreEngine(Protocol):
    def restore(self, pixels: np.ndarray, mode: DenoiseMode) -> np.ndarray: ...


@dataclass(frozen=True)
class SingleRestoreResult:
    source_path: Path
    output_path: Path
    mode: DenoiseMode
    raw_pixels: np.ndarray
    restored_pixels: np.ndarray


class BatchFileStatus(str, Enum):
    RESTORED = "restored"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class BatchFileResult:
    source_path: Path
    status: BatchFileStatus
    message: str
    output_path: Path | None = None


@dataclass(frozen=True)
class BatchRestoreResult:
    folder_path: Path
    mode: DenoiseMode
    file_results: list[BatchFileResult]

    @property
    def total_count(self) -> int:
        return len(self.file_results)

    @property
    def restored_count(self) -> int:
        return sum(
            result.status is BatchFileStatus.RESTORED for result in self.file_results
        )

    @property
    def skipped_count(self) -> int:
        return sum(
            result.status is BatchFileStatus.SKIPPED for result in self.file_results
        )

    @property
    def failed_count(self) -> int:
        return sum(
            result.status is BatchFileStatus.FAILED for result in self.file_results
        )

    @property
    def cancelled_count(self) -> int:
        return sum(
            result.status is BatchFileStatus.CANCELLED for result in self.file_results
        )


@dataclass(frozen=True)
class BatchRestoreStep:
    file_results: list[BatchFileResult]
    completed_count: int
    total_count: int
    final_result: BatchRestoreResult | None = None


def batch_input_paths(folder: Path) -> list[Path]:
    return sorted(path for path in Path(folder).iterdir() if path.is_file())


class BatchRestoreRun:
    """A single Batch mode execution with per-file progress."""

    def __init__(
        self,
        folder: Path,
        mode: DenoiseMode,
        engine: RestoreEngine,
    ) -> None:
        self.folder_path = Path(folder)
        self.mode = mode
        self._engine = engine
        self._paths = batch_input_paths(self.folder_path)
        self._index = 0
        self._file_results: list[BatchFileResult] = []
        self._cancel_requested = False

    @property
    def total_count(self) -> int:
        return len(self._paths)

    @property
    def completed_count(self) -> int:
        return len(self._file_results)

    def cancel(self) -> None:
        self._cancel_requested = True

    def next_step(self) -> BatchRestoreStep:
        if self._cancel_requested:
            return self._finish_cancelled_step()

        file_result = self._next_file_result()
        if file_result is None:
            return self._finished_step([])

        if self._index >= len(self._paths):
            return self._finished_step([file_result])

        return self._step([file_result])

    def _next_file_result(self) -> BatchFileResult | None:
        if self._index >= len(self._paths):
            return None

        path = self._paths[self._index]
        result = restore_batch_file(path, self.mode, self._engine)
        self._file_results.append(result)
        self._index += 1
        return result

    def result(self) -> BatchRestoreResult:
        return BatchRestoreResult(
            folder_path=self.folder_path,
            mode=self.mode,
            file_results=list(self._file_results),
        )

    def _finish_cancelled_step(self) -> BatchRestoreStep:
        return self._finished_step(self._cancel_remaining())

    def _cancel_remaining(self) -> list[BatchFileResult]:
        cancelled_results = [
            BatchFileResult(
                source_path=path,
                status=BatchFileStatus.CANCELLED,
                message="Not processed",
            )
            for path in self._paths[self._index :]
        ]
        self._file_results.extend(cancelled_results)
        self._index = len(self._paths)
        return cancelled_results

    def _finished_step(self, file_results: list[BatchFileResult]) -> BatchRestoreStep:
        return self._step(file_results, final_result=self.result())

    def _step(
        self,
        file_results: list[BatchFileResult],
        final_result: BatchRestoreResult | None = None,
    ) -> BatchRestoreStep:
        return BatchRestoreStep(
            file_results=file_results,
            completed_count=self.completed_count,
            total_count=self.total_count,
            final_result=final_result,
        )


def restore_batch_folder(
    folder: Path,
    mode: DenoiseMode,
    engine: RestoreEngine,
    cancel_requested: Callable[[], bool] | None = None,
) -> BatchRestoreResult:
    run = BatchRestoreRun(folder, mode, engine)
    while True:
        if cancel_requested is not None and cancel_requested():
            run.cancel()

        step = run.next_step()
        if step.final_result is not None:
            return step.final_result

    return run.result()


def restore_batch_file(
    path: Path,
    mode: DenoiseMode,
    engine: RestoreEngine,
) -> BatchFileResult:
    try:
        result = restore_single_image(path, mode, engine)
    except ImageFormatError as exc:
        return BatchFileResult(
            source_path=path,
            status=BatchFileStatus.SKIPPED,
            message=str(exc),
        )
    except Exception as exc:
        return failed_batch_file(path, exc)

    return BatchFileResult(
        source_path=result.source_path,
        status=BatchFileStatus.RESTORED,
        message="Restored",
        output_path=result.output_path,
    )


def failed_batch_file(path: Path, exc: Exception) -> BatchFileResult:
    return BatchFileResult(
        source_path=path,
        status=BatchFileStatus.FAILED,
        message=str(exc),
    )


def restore_single_image(path: Path, mode: DenoiseMode, engine: RestoreEngine) -> SingleRestoreResult:
    image = load_image(path)
    restored_pixels = engine.restore(image.pixels, mode)
    output_path = save_restored_image(image, restored_pixels, mode)

    return SingleRestoreResult(
        source_path=image.source_path,
        output_path=output_path,
        mode=mode,
        raw_pixels=image.pixels,
        restored_pixels=restored_pixels,
    )
