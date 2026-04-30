from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

from denoiser.engine import DenoiseMode
from denoiser.workflow import BatchFileStatus, batch_input_paths, restore_batch_folder


def test_batch_input_paths_scans_selected_folder_non_recursively(tmp_path: Path) -> None:
    direct = tmp_path / "wafer.tif"
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested = nested_dir / "nested.tif"
    tifffile.imwrite(direct, np.zeros((2, 2), dtype=np.uint8))
    tifffile.imwrite(nested, np.ones((2, 2), dtype=np.uint8))

    assert batch_input_paths(tmp_path) == [direct]


def test_restore_batch_folder_restores_supported_files_with_shared_saving_rules(
    tmp_path: Path,
) -> None:
    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):
            assert mode is DenoiseMode.LRSEM
            return pixels + 3

    result = restore_batch_folder(tmp_path, DenoiseMode.LRSEM, FakeEngine())

    output = tmp_path / "denoised_LRSEM" / "wafer.tif"
    assert result.total_count == 1
    assert result.restored_count == 1
    assert result.file_results[0].status is BatchFileStatus.RESTORED
    assert result.file_results[0].source_path == source
    assert result.file_results[0].output_path == output
    np.testing.assert_array_equal(
        tifffile.imread(output),
        np.array([[13, 23], [33, 40]], dtype=np.uint8),
    )


def test_restore_batch_folder_skips_unsupported_files_without_engine(
    tmp_path: Path,
) -> None:
    source = tmp_path / "wafer.bmp"
    source.write_bytes(b"not an accepted input")

    class EngineShouldNotRun:
        def restore(self, pixels, mode):
            raise AssertionError("Engine should not run for unsupported batch input")

    result = restore_batch_folder(tmp_path, DenoiseMode.HRSTEM, EngineShouldNotRun())

    assert result.total_count == 1
    assert result.restored_count == 0
    assert result.skipped_count == 1
    assert result.file_results[0].status is BatchFileStatus.SKIPPED
    assert result.file_results[0].source_path == source
    assert result.file_results[0].output_path is None
    assert "Unsupported file format" in result.file_results[0].message


def test_restore_batch_folder_isolates_file_failures_and_continues(
    tmp_path: Path,
) -> None:
    failing = tmp_path / "a_fails.tif"
    later = tmp_path / "b_later.tif"
    tifffile.imwrite(failing, np.array([[10, 20], [30, 40]], dtype=np.uint8))
    tifffile.imwrite(later, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class PartlyFailingEngine:
        def restore(self, pixels, mode):
            if pixels[0, 0] == 10:
                raise RuntimeError("model crashed")
            return pixels + 1

    result = restore_batch_folder(tmp_path, DenoiseMode.HRSTEM, PartlyFailingEngine())

    assert result.total_count == 2
    assert result.restored_count == 1
    assert result.failed_count == 1
    assert result.file_results[0].status is BatchFileStatus.FAILED
    assert result.file_results[0].output_path is None
    assert "model crashed" in result.file_results[0].message
    assert result.file_results[1].status is BatchFileStatus.RESTORED
    assert result.file_results[1].output_path == tmp_path / "denoised_HRSTEM" / "b_later.tif"


def test_restore_batch_folder_cancels_remaining_files_between_restores(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a_first.tif"
    second = tmp_path / "b_second.tif"
    third = tmp_path / "c_third.tif"
    for source in (first, second, third):
        tifffile.imwrite(source, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class FakeEngine:
        restore_count = 0

        def restore(self, pixels, mode):
            self.restore_count += 1
            return pixels + self.restore_count

    engine = FakeEngine()

    result = restore_batch_folder(
        tmp_path,
        DenoiseMode.LRSEM,
        engine,
        cancel_requested=lambda: engine.restore_count >= 1,
    )

    assert result.total_count == 3
    assert result.restored_count == 1
    assert result.cancelled_count == 2
    assert engine.restore_count == 1
    assert result.file_results[0].status is BatchFileStatus.RESTORED
    assert result.file_results[1].status is BatchFileStatus.CANCELLED
    assert result.file_results[2].status is BatchFileStatus.CANCELLED
    assert (tmp_path / "denoised_LRSEM" / "a_first.tif").is_file()
    assert not (tmp_path / "denoised_LRSEM" / "b_second.tif").exists()
