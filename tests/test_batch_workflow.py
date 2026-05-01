from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

from denoiser.engine import DenoiseMode
from denoiser.workflow import (
    BatchFileStatus,
    BatchRestoreRun,
    batch_input_paths,
    restore_batch_folder,
)


def test_batch_input_paths_scans_selected_folder_non_recursively(tmp_path: Path) -> None:
    direct = tmp_path / "wafer.tif"
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested = nested_dir / "nested.tif"
    tifffile.imwrite(direct, np.zeros((2, 2), dtype=np.uint8))
    tifffile.imwrite(nested, np.ones((2, 2), dtype=np.uint8))

    assert batch_input_paths(tmp_path) == [direct]


def test_batch_restore_run_exposes_each_file_result_as_it_advances(
    tmp_path: Path,
) -> None:
    supported = tmp_path / "wafer.tif"
    unsupported = tmp_path / "notes.txt"
    tifffile.imwrite(supported, np.array([[10, 20], [30, 40]], dtype=np.uint8))
    unsupported.write_text("skip me")

    class FakeEngine:
        def restore(self, pixels, mode):
            assert mode is DenoiseMode.LRSEM
            return pixels + 3

    run = BatchRestoreRun(tmp_path, DenoiseMode.LRSEM, FakeEngine())

    first_step = run.next_step()
    second_step = run.next_step()

    assert len(first_step.file_results) == 1
    first_result = first_step.file_results[0]
    assert first_result.status is BatchFileStatus.SKIPPED
    assert first_result.source_path == unsupported
    assert first_step.completed_count == 1
    assert first_step.total_count == 2
    assert first_step.final_result is None

    assert len(second_step.file_results) == 1
    second_result = second_step.file_results[0]
    assert second_result.status is BatchFileStatus.RESTORED
    assert second_result.source_path == supported
    assert second_step.completed_count == 2
    assert second_step.total_count == 2
    assert second_step.final_result is not None

    final_result = second_step.final_result
    assert final_result.total_count == 2
    assert final_result.restored_count == 1
    assert final_result.skipped_count == 1


def test_batch_restore_run_exposes_progress_counts(tmp_path: Path) -> None:
    first = tmp_path / "a_first.tif"
    second = tmp_path / "b_second.tif"
    for source in (first, second):
        tifffile.imwrite(source, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):
            return pixels + 1

    run = BatchRestoreRun(tmp_path, DenoiseMode.LRSEM, FakeEngine())

    assert run.total_count == 2
    assert run.completed_count == 0

    step = run.next_step()

    assert step.total_count == 2
    assert step.completed_count == 1


def test_batch_restore_run_cancels_remaining_files_without_processing_them(
    tmp_path: Path,
) -> None:
    for filename in ("a_first.tif", "b_second.tif", "c_third.tif"):
        tifffile.imwrite(tmp_path / filename, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class FakeEngine:
        restore_count = 0

        def restore(self, pixels, mode):
            self.restore_count += 1
            return pixels + self.restore_count

    engine = FakeEngine()
    run = BatchRestoreRun(tmp_path, DenoiseMode.LRSEM, engine)

    first_step = run.next_step()
    run.cancel()
    cancelled_step = run.next_step()

    first_result = first_step.file_results[0]
    assert first_result is not None
    assert first_result.status is BatchFileStatus.RESTORED
    cancelled_results = cancelled_step.file_results
    assert [result.status for result in cancelled_results] == [
        BatchFileStatus.CANCELLED,
        BatchFileStatus.CANCELLED,
    ]
    assert cancelled_step.completed_count == 3
    assert cancelled_step.total_count == 3
    assert cancelled_step.final_result is not None
    assert engine.restore_count == 1
    assert cancelled_step.final_result.cancelled_count == 2
    assert not (tmp_path / "denoised_LRSEM" / "b_second.tif").exists()


def test_batch_restore_run_isolates_file_failures_and_keeps_advancing(
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

    run = BatchRestoreRun(tmp_path, DenoiseMode.HRSTEM, PartlyFailingEngine())

    failed_step = run.next_step()
    restored_step = run.next_step()

    failed_result = failed_step.file_results[0]
    assert failed_result is not None
    assert failed_result.status is BatchFileStatus.FAILED
    assert "model crashed" in failed_result.message
    restored_result = restored_step.file_results[0]
    assert restored_result is not None
    assert restored_result.status is BatchFileStatus.RESTORED
    assert restored_step.final_result is not None
    assert restored_step.final_result.failed_count == 1
    assert restored_step.final_result.restored_count == 1


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
