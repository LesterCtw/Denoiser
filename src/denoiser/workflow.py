"""User-facing restore workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

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


def batch_input_paths(folder: Path) -> list[Path]:
    return sorted(path for path in Path(folder).iterdir() if path.is_file())


def restore_batch_folder(
    folder: Path,
    mode: DenoiseMode,
    engine: RestoreEngine,
) -> BatchRestoreResult:
    folder_path = Path(folder)
    file_results: list[BatchFileResult] = []
    for path in batch_input_paths(folder_path):
        try:
            result = restore_single_image(path, mode, engine)
        except ImageFormatError as exc:
            file_results.append(
                BatchFileResult(
                    source_path=path,
                    status=BatchFileStatus.SKIPPED,
                    message=str(exc),
                )
            )
        else:
            file_results.append(
                BatchFileResult(
                    source_path=result.source_path,
                    status=BatchFileStatus.RESTORED,
                    message="Restored",
                    output_path=result.output_path,
                )
            )

    return BatchRestoreResult(
        folder_path=folder_path,
        mode=mode,
        file_results=file_results,
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
