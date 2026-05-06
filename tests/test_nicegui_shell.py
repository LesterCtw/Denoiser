from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

import numpy as np
import pytest
import tifffile

from denoiser.image_io import ImageFormatError
from denoiser.single_image_inspection import SingleImageInspection


class RecordingElement:
    def __init__(self, props_sink: list[str] | None = None) -> None:
        self._props_sink = props_sink
        self.styles: list[str] = []

    def __enter__(self) -> "RecordingElement":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def classes(self, value: str) -> "RecordingElement":
        return self

    def props(self, value: str) -> "RecordingElement":
        if self._props_sink is not None:
            self._props_sink.append(value)
        return self

    def style(self, value: str) -> "RecordingElement":
        self.styles.append(value)
        return self


class RecordingUi:
    def __init__(self) -> None:
        self.head_html: list[str] = []
        self.labels: list[str] = []
        self.buttons: list[str] = []
        self.button_actions: dict[str, object] = {}
        self.button_props: dict[str, list[str]] = {}
        self.button_styles: dict[str, list[str]] = {}
        self.images: list[str] = []
        self.run_kwargs: dict[str, object] | None = None

    def add_head_html(self, html: str) -> None:
        self.head_html.append(html)

    def column(self) -> RecordingElement:
        return RecordingElement()

    def row(self) -> RecordingElement:
        return RecordingElement()

    def label(self, text: str) -> RecordingElement:
        self.labels.append(text)
        return RecordingElement()

    def button(self, text: str, *, on_click=None) -> RecordingElement:  # noqa: ANN001
        self.buttons.append(text)
        self.button_actions[text] = on_click
        self.button_props[text] = []
        element = RecordingElement(self.button_props[text])
        self.button_styles[text] = element.styles
        return element

    def html(self, html: str) -> RecordingElement:
        self.labels.append(html)
        return RecordingElement()

    def image(self, source: str) -> RecordingElement:
        self.images.append(source)
        return RecordingElement()

    def run(self, **kwargs: object) -> None:
        self.run_kwargs = kwargs


def test_nicegui_shell_snapshot_has_core_inspector_controls() -> None:
    from denoiser.nicegui_shell import build_inspector_shell_snapshot

    snapshot = build_inspector_shell_snapshot()

    assert snapshot.title == "Denoiser"
    assert snapshot.regions == ("left control rail", "right work area")
    assert snapshot.workflows == ("Single", "Batch")
    assert snapshot.selected_workflow == "Single"
    assert snapshot.denoising_modes == ("HRSTEM", "LRSTEM", "HRSEM", "LRSEM")
    assert snapshot.selected_denoising_mode == "HRSTEM"
    assert snapshot.primary_action == "Restore"
    assert snapshot.status == "Ready"
    assert snapshot.design_tokens["canvas"] == "#010102"
    assert snapshot.design_tokens["primary"] == "#5e6ad2"


def test_nicegui_shell_workflow_switch_updates_right_work_area_state() -> None:
    from denoiser.nicegui_shell import InspectorShellState

    state = InspectorShellState()
    assert state.snapshot().right_work_area_title == ""

    state.select_workflow("Batch")

    assert state.snapshot().selected_workflow == "Batch"
    assert state.snapshot().right_work_area_title == "Batch Restore"


def test_nicegui_shell_mode_selection_updates_selected_state() -> None:
    from denoiser.nicegui_shell import InspectorShellState

    state = InspectorShellState()
    state.select_denoising_mode("LRSEM")

    snapshot = state.snapshot()
    assert snapshot.selected_denoising_mode == "LRSEM"
    assert snapshot.mode_button_states == {
        "HRSTEM": "idle",
        "LRSTEM": "idle",
        "HRSEM": "idle",
        "LRSEM": "selected",
    }


def test_single_mode_change_updates_selected_image_overwrite_target(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    source = tmp_path / "wafer.tif"
    state = InspectorShellState()
    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.array([[0, 255]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )
    )

    state.select_denoising_mode("LRSEM")

    snapshot = state.snapshot()
    assert snapshot.selected_denoising_mode == "LRSEM"
    assert snapshot.overwrite_output_path == tmp_path / "denoised_LRSEM" / "wafer.tif"


def test_nicegui_shell_render_outputs_core_controls_and_dark_style() -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    recording_ui = RecordingUi()
    render_nicegui_shell(ui_module=recording_ui, state=InspectorShellState())

    assert "Denoiser" in recording_ui.labels
    assert "Single image inspection" not in recording_ui.labels
    assert "Ready" in recording_ui.labels
    assert {"Single", "Batch", "HRSTEM", "LRSTEM", "HRSEM", "LRSEM", "Restore"} <= set(
        recording_ui.buttons
    )
    assert "#010102" in recording_ui.head_html[0]
    assert "#5e6ad2" in recording_ui.head_html[0]
    assert ".denoiser-shell" in recording_ui.head_html[0]
    assert ".denoiser-preview-frame" in recording_ui.head_html[0]
    assert ".denoiser-status-panel" in recording_ui.head_html[0]
    assert "align-items: stretch" in recording_ui.head_html[0]
    assert "height: calc(100vh - 170px)" not in recording_ui.head_html[0]
    assert "width: calc(100vw - 360px)" in recording_ui.head_html[0]
    assert "height: calc(100vh - 54px)" in recording_ui.head_html[0]
    assert "window.denoiserSetComparisonDivider" in recording_ui.head_html[0]
    assert "document.addEventListener('mousedown'" in recording_ui.head_html[0]
    assert "#141516" in recording_ui.button_styles["Batch"][0]
    assert "#18191a" in recording_ui.button_styles["Single"][0]
    assert "#5e6ad2" in recording_ui.button_styles["Restore"][0]


def test_nicegui_shell_runs_as_standard_native_window(monkeypatch) -> None:
    from denoiser.nicegui_shell import run_nicegui_native_window
    from nicegui import app

    monkeypatch.setattr(sys, "platform", "darwin")
    recording_ui = RecordingUi()

    assert run_nicegui_native_window(ui_module=recording_ui) == 0

    assert app.native.start_args["icon"] == str(
        Path("assets/icons/denoiser_icon.icns").resolve()
    )
    assert recording_ui.run_kwargs is not None
    root = recording_ui.run_kwargs.pop("root")
    assert callable(root)
    assert recording_ui.run_kwargs == {
        "title": "Denoiser",
        "favicon": Path("assets/icons/denoiser_icon.ico").resolve(),
        "native": True,
        "window_size": (1280, 820),
        "fullscreen": False,
        "frameless": False,
        "reload": False,
        "show": False,
    }
    assert recording_ui.labels == []

    root()

    assert "Denoiser" in recording_ui.labels
    assert "Single image inspection" not in recording_ui.labels


def test_nicegui_shell_uses_windows_runtime_icon_for_native_window(
    monkeypatch,
) -> None:
    from denoiser.nicegui_shell import run_nicegui_native_window
    from nicegui import app

    monkeypatch.setattr(sys, "platform", "win32")
    app.native.start_args["icon"] = "stale-icon-from-previous-run"

    recording_ui = RecordingUi()

    assert run_nicegui_native_window(ui_module=recording_ui) == 0
    assert "icon" not in app.native.start_args
    assert recording_ui.run_kwargs is not None
    assert recording_ui.run_kwargs["favicon"] == Path(
        "assets/icons/denoiser_icon.ico"
    ).resolve()


def test_nicegui_shell_uses_macos_native_icon_for_local_dev(monkeypatch) -> None:
    from denoiser.nicegui_shell import _pywebview_start_icon_path

    monkeypatch.setattr(sys, "platform", "darwin")

    assert _pywebview_start_icon_path() == Path(
        "assets/icons/denoiser_icon.icns"
    ).resolve()


def test_denoiser_main_launches_nicegui_native_shell(monkeypatch) -> None:
    import denoiser.app as app_module

    calls: list[str] = []
    monkeypatch.setattr(
        app_module,
        "run_nicegui_native_window",
        lambda: calls.append("launched") or 0,
    )

    assert app_module.main() == 0
    assert calls == ["launched"]


def test_project_dependencies_include_nicegui_native_window_stack() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    for dependency in ["nicegui", "pywebview"]:
        assert dependency in pyproject
        assert dependency in requirements


def test_readme_documents_nicegui_restore_status() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "NiceGUI native-window inspector frontend" in readme
    assert "NiceGUI Single image selection and raw-only preview" in readme
    assert "NiceGUI Single restore and before/after comparison" in readme
    assert "NiceGUI Batch folder selection and restore run" in readme
    assert "NiceGUI restore parity 已完成" in readme


def test_single_image_selection_shows_loading_then_raw_preview(tmp_path: Path) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    source = tmp_path / "wafer.tif"
    state = InspectorShellState()

    state.begin_single_image_selection(source)

    loading = state.snapshot()
    assert loading.single_preview_state == "loading"
    assert loading.status == "Loading preview: wafer.tif"
    assert "Existing outputs will be overwritten." in loading.warnings

    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.array([[0, 255]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )
    )

    selected = state.snapshot()
    assert selected.single_preview_state == "selected"
    assert selected.status == "Selected image: wafer.tif"
    assert selected.selected_single_image_path == source
    assert selected.raw_preview is not None
    assert selected.raw_preview.is_comparing is False
    assert selected.raw_preview.data_url.startswith("data:image/png;base64,")


def test_single_image_selection_runs_inspection_and_exposes_overwrite_target(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    source = tmp_path / "wafer.tif"
    inspected_paths: list[Path] = []

    def inspect(path: Path) -> SingleImageInspection:
        inspected_paths.append(path)
        return SingleImageInspection(
            source_path=path,
            preview_pixels=np.array([[1, 2]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )

    state = InspectorShellState(selected_denoising_mode="LRSEM")
    state.select_single_image_path(source, inspect_single_image=inspect)

    snapshot = state.snapshot()
    assert inspected_paths == [source]
    assert snapshot.single_preview_state == "selected"
    assert snapshot.overwrite_output_path == tmp_path / "denoised_LRSEM" / "wafer.tif"


def test_single_image_selection_shows_large_image_warning(tmp_path: Path) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    source = tmp_path / "large.tif"
    state = InspectorShellState()

    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.zeros((1537, 1), dtype=np.uint8),
            requires_patch_based_restore=True,
        )
    )

    assert "Large images may take several minutes." in state.snapshot().warnings


def test_single_image_selection_rejects_unsupported_input_readably(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    source = tmp_path / "wafer.bmp"

    def reject(path: Path) -> SingleImageInspection:
        raise ImageFormatError(f"Unsupported file format: {path.suffix}")

    state = InspectorShellState()
    state.select_single_image_path(source, inspect_single_image=reject)

    snapshot = state.snapshot()
    assert snapshot.single_preview_state == "error"
    assert snapshot.status == "Cannot preview: Unsupported file format: .bmp"
    assert snapshot.raw_preview is None


def test_single_restore_prompts_for_image_before_running_restore() -> None:
    from denoiser.nicegui_shell import InspectorShellState

    state = InspectorShellState()

    assert state.begin_single_restore() is None
    assert state.snapshot().status == "Open an image before restoring."


def test_single_restore_writes_output_and_shows_before_after_comparison(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):  # noqa: ANN001
            return pixels + 5

    state = InspectorShellState(selected_denoising_mode="LRSEM")
    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.array([[10, 40]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )
    )

    state.restore_selected_single_image(FakeEngine())

    snapshot = state.snapshot()
    output = tmp_path / "denoised_LRSEM" / "wafer.tif"
    assert output.is_file()
    assert f"Saved image: {output.name}" in snapshot.status
    assert f"Output folder: {output.parent.name}" in snapshot.status
    assert snapshot.raw_preview is None
    assert snapshot.comparison_preview is not None
    assert snapshot.comparison_preview.divider_position == 0.5
    assert snapshot.comparison_preview.raw_side == "left"
    assert snapshot.comparison_preview.restored_side == "right"
    assert snapshot.comparison_preview.supports_click_to_jump
    assert snapshot.comparison_preview.supports_drag


def test_single_restore_processing_state_disables_conflicting_controls(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState
    from denoiser.models import DenoiseMode
    from denoiser.workflow import SingleRestoreResult

    source = tmp_path / "wafer.tif"
    state = InspectorShellState()
    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.array([[0, 255]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )
    )

    state.begin_single_restore()

    restoring = state.snapshot()
    assert restoring.single_preview_state == "restoring"
    assert restoring.status == "Restoring..."
    assert restoring.single_controls_enabled is False

    state.finish_single_restore(
        SingleRestoreResult(
            source_path=source,
            output_path=tmp_path / "denoised_HRSTEM" / "wafer.tif",
            mode=DenoiseMode.HRSTEM,
            raw_pixels=np.array([[0, 1]], dtype=np.float32),
            restored_pixels=np.array([[1, 2]], dtype=np.float32),
        )
    )

    assert state.snapshot().single_controls_enabled is True


def test_nicegui_shell_render_disables_single_controls_while_restoring(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    source = tmp_path / "wafer.tif"
    state = InspectorShellState()
    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.array([[0, 255]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )
    )
    state.begin_single_restore()

    recording_ui = RecordingUi()
    render_nicegui_shell(ui_module=recording_ui, state=state, engine=object())

    for button in ("Single", "Batch", "Open Image", "HRSTEM", "LRSTEM", "HRSEM", "LRSEM", "Restore"):
        assert "disable" in recording_ui.button_props[button]
    assert "denoiser-status-progress" in "\n".join(recording_ui.labels)


def test_single_restore_failure_returns_controls_to_usable_state(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    source = tmp_path / "wafer.tif"
    state = InspectorShellState()
    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.array([[0, 255]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )
    )

    def fail_restore(*args):  # noqa: ANN002
        raise RuntimeError("model failed")

    state.restore_selected_single_image(object(), restore_single_image=fail_restore)

    snapshot = state.snapshot()
    assert snapshot.single_preview_state == "selected"
    assert snapshot.status == "Cannot restore: model failed"
    assert snapshot.single_controls_enabled is True
    assert snapshot.raw_preview is not None


def test_nicegui_shell_render_hides_status_progress_when_idle() -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    recording_ui = RecordingUi()
    render_nicegui_shell(ui_module=recording_ui, state=InspectorShellState())

    assert "denoiser-status-progress" not in "\n".join(recording_ui.labels)


def test_nicegui_shell_processing_status_fills_left_rail_width() -> None:
    from denoiser.nicegui_shell import build_inspector_shell_snapshot
    from denoiser.nicegui_shell import _shell_css

    css = _shell_css(build_inspector_shell_snapshot().design_tokens)

    assert (
        ".denoiser-status-panel {\n"
        "        align-self: stretch;\n"
        "        width: 100%;\n"
        "        box-sizing: border-box;"
    ) in css
    assert (
        ".denoiser-status-progress-host {\n"
        "        display: block;\n"
        "        align-self: stretch;\n"
        "        width: 100%;"
    ) in css
    assert "nicegui-html.denoiser-status-progress-host" in css


def test_batch_folder_selection_stores_selected_folder_path(tmp_path: Path) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    state = InspectorShellState()
    state.select_batch_folder_path(tmp_path)

    snapshot = state.snapshot()
    assert snapshot.selected_workflow == "Batch"
    assert snapshot.selected_batch_folder_path == tmp_path
    assert snapshot.batch_restore_state == "folder-selected"
    assert snapshot.status == f"Batch folder: {tmp_path.name}"
    assert snapshot.batch_progress_text == "0 of 0 files"


def test_batch_restore_prompts_for_folder_before_running_engine() -> None:
    from denoiser.nicegui_shell import InspectorShellState

    class EngineShouldNotRun:
        def restore(self, pixels, mode):  # noqa: ANN001
            raise AssertionError("Engine should not run without a Batch folder")

    state = InspectorShellState(selected_workflow="Batch")
    state.restore_selected_batch_folder(EngineShouldNotRun())

    snapshot = state.snapshot()
    assert snapshot.status == "Add a folder before starting Batch."
    assert snapshot.batch_restore_state == "idle"


def test_batch_restore_blocks_denoised_folder_before_running_engine(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState

    folder = tmp_path / "denoised_HRSTEM"
    folder.mkdir()
    tifffile.imwrite(folder / "wafer.tif", np.zeros((2, 2), dtype=np.uint8))

    class EngineShouldNotRun:
        def restore(self, pixels, mode):  # noqa: ANN001
            raise AssertionError("Engine should not run for denoised_* Batch folder")

    state = InspectorShellState(selected_workflow="Batch")
    state.select_batch_folder_path(folder)
    state.restore_selected_batch_folder(EngineShouldNotRun())

    snapshot = state.snapshot()
    assert snapshot.status == "Cannot start Batch: Refusing to process denoised_* folders."
    assert snapshot.batch_restore_state == "folder-selected"
    assert snapshot.batch_progress_text == "0 of 0 files"
    assert snapshot.batch_file_results == ()


def test_batch_restore_writes_output_and_lists_restored_and_skipped_files(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState
    from denoiser.workflow import BatchFileStatus

    supported = tmp_path / "wafer.tif"
    unsupported = tmp_path / "notes.txt"
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested = nested_dir / "nested.tif"
    tifffile.imwrite(supported, np.array([[10, 20], [30, 40]], dtype=np.uint8))
    unsupported.write_text("skip me")
    tifffile.imwrite(nested, np.array([[99]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):  # noqa: ANN001
            from denoiser.models import DenoiseMode

            assert mode is DenoiseMode.HRSEM
            return pixels + 4

    state = InspectorShellState(selected_denoising_mode="HRSEM")
    state.select_batch_folder_path(tmp_path)
    state.restore_selected_batch_folder(FakeEngine())

    output = tmp_path / "denoised_HRSEM" / "wafer.tif"
    snapshot = state.snapshot()
    assert output.is_file()
    assert not (tmp_path / "nested" / "denoised_HRSEM" / "nested.tif").exists()
    assert snapshot.batch_restore_state == "complete"
    assert snapshot.batch_progress_text == "2 of 2 files"
    assert "Batch complete: 1 restored, 0 failed, 1 skipped, 0 cancelled." in snapshot.status
    assert [row.status for row in snapshot.batch_file_results] == [
        BatchFileStatus.SKIPPED,
        BatchFileStatus.RESTORED,
    ]
    assert [row.filename for row in snapshot.batch_file_results] == [
        "notes.txt",
        "wafer.tif",
    ]


def test_batch_restore_marks_failed_files_and_keeps_advancing(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState
    from denoiser.workflow import BatchFileStatus

    failing = tmp_path / "a_fails.tif"
    later = tmp_path / "b_later.tif"
    tifffile.imwrite(failing, np.array([[10, 20], [30, 40]], dtype=np.uint8))
    tifffile.imwrite(later, np.array([[1, 2], [3, 4]], dtype=np.uint8))

    class PartlyFailingEngine:
        def restore(self, pixels, mode):  # noqa: ANN001
            if pixels[0, 0] == 10:
                raise RuntimeError("model crashed")
            return pixels + 1

    state = InspectorShellState(selected_denoising_mode="HRSTEM")
    state.select_batch_folder_path(tmp_path)
    state.restore_selected_batch_folder(PartlyFailingEngine())

    snapshot = state.snapshot()
    assert "Batch complete: 1 restored, 1 failed, 0 skipped, 0 cancelled." in snapshot.status
    assert [row.status for row in snapshot.batch_file_results] == [
        BatchFileStatus.FAILED,
        BatchFileStatus.RESTORED,
    ]
    assert "model crashed" in snapshot.batch_file_results[0].detail
    assert (tmp_path / "denoised_HRSTEM" / "b_later.tif").is_file()


def test_nicegui_shell_render_shows_batch_progress_rows_and_readable_badges() -> None:
    from denoiser.nicegui_shell import (
        BatchResultRow,
        InspectorShellState,
        render_nicegui_shell,
    )
    from denoiser.workflow import BatchFileStatus

    state = InspectorShellState(selected_workflow="Batch")
    state.batch_progress_text = "2 of 2 files"
    state.batch_file_results = (
        BatchResultRow(
            filename="launch_phase4_overlay_uat_with_a_very_long_name.tif",
            status=BatchFileStatus.RESTORED,
            status_label="Restored",
            detail="Saved to denoised_HRSEM/launch_phase4_overlay_uat_with_a_very_long_name.tif",
        ),
        BatchResultRow(
            filename="notes.txt",
            status=BatchFileStatus.SKIPPED,
            status_label="Skipped",
            detail="Unsupported file format: .txt",
        ),
    )

    recording_ui = RecordingUi()
    render_nicegui_shell(ui_module=recording_ui, state=state, engine=object())

    batch_html = "\n".join(recording_ui.labels)
    assert "2 of 2 files" in batch_html
    assert "launch_phase4_overlay_uat_with_a_very_long_name.tif" in batch_html
    assert "notes.txt" in batch_html
    assert "denoiser-batch-status-restored" in batch_html
    assert "denoiser-batch-status-skipped" in batch_html
    assert "text-overflow: ellipsis" in recording_ui.head_html[0]
    assert "min-height: 42px" in recording_ui.head_html[0]


def test_nicegui_shell_render_shows_unframed_empty_batch_state() -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    recording_ui = RecordingUi()
    render_nicegui_shell(
        ui_module=recording_ui,
        state=InspectorShellState(selected_workflow="Batch"),
        engine=object(),
    )

    batch_html = "\n".join(recording_ui.labels)
    assert "0 of 0 files" in batch_html
    assert "No files processed yet." in batch_html
    assert "denoiser-batch-empty" in batch_html
    assert "denoiser-batch-list" not in batch_html
    assert "No Batch results yet." not in batch_html


@pytest.mark.anyio
async def test_restore_button_runs_selected_single_restore(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    class FakeEngine:
        def restore(self, pixels, mode):  # noqa: ANN001
            return pixels + 3

    async def restore_runner(callback, *args):  # noqa: ANN001, ANN002
        return callback(*args)

    state = InspectorShellState(selected_denoising_mode="HRSEM")
    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.array([[10, 40]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )
    )
    recording_ui = RecordingUi()
    render_nicegui_shell(
        ui_module=recording_ui,
        state=state,
        engine=FakeEngine(),
        restore_runner=restore_runner,
    )

    await recording_ui.button_actions["Restore"]()

    output = tmp_path / "denoised_HRSEM" / "wafer.tif"
    assert output.is_file()
    assert state.snapshot().comparison_preview is not None


@pytest.mark.anyio
async def test_batch_buttons_select_folder_and_start_batch_restore(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    source = tmp_path / "wafer.tif"
    tifffile.imwrite(source, np.array([[10, 20], [30, 40]], dtype=np.uint8))

    class PathSelector:
        async def select_batch_folder_path(self) -> Path:
            return tmp_path

    class FakeEngine:
        def restore(self, pixels, mode):  # noqa: ANN001
            return pixels + 2

    async def restore_runner(callback, *args):  # noqa: ANN001, ANN002
        return callback(*args)

    state = InspectorShellState(selected_workflow="Batch", selected_denoising_mode="LRSEM")
    recording_ui = RecordingUi()
    render_nicegui_shell(
        ui_module=recording_ui,
        state=state,
        path_selector=PathSelector(),
        engine=FakeEngine(),
        restore_runner=restore_runner,
    )

    assert {"Add Folder", "Start Batch"} <= set(recording_ui.buttons)
    await recording_ui.button_actions["Add Folder"]()
    await recording_ui.button_actions["Start Batch"]()

    output = tmp_path / "denoised_LRSEM" / "wafer.tif"
    snapshot = state.snapshot()
    assert output.is_file()
    assert snapshot.selected_batch_folder_path == tmp_path
    assert snapshot.batch_restore_state == "complete"
    assert snapshot.batch_progress_text == "1 of 1 files"


@pytest.mark.anyio
async def test_batch_cancel_button_cancels_remaining_files_between_restores(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell
    from denoiser.workflow import BatchFileStatus

    for filename in ("a_first.tif", "b_second.tif", "c_third.tif"):
        tifffile.imwrite(
            tmp_path / filename,
            np.array([[1, 2], [3, 4]], dtype=np.uint8),
        )

    restore_started = threading.Event()
    finish_restore = threading.Event()

    class FakeEngine:
        restore_count = 0

        def restore(self, pixels, mode):  # noqa: ANN001
            self.restore_count += 1
            restore_started.set()
            finish_restore.wait(timeout=5)
            return pixels + self.restore_count

    async def restore_runner(callback, *args):  # noqa: ANN001, ANN002
        return await asyncio.to_thread(callback, *args)

    state = InspectorShellState(selected_workflow="Batch")
    state.select_batch_folder_path(tmp_path)
    recording_ui = RecordingUi()
    engine = FakeEngine()
    render_nicegui_shell(
        ui_module=recording_ui,
        state=state,
        engine=engine,
        restore_runner=restore_runner,
    )

    batch_task = asyncio.create_task(recording_ui.button_actions["Start Batch"]())
    assert await asyncio.to_thread(restore_started.wait, 5)

    assert state.snapshot().batch_restore_state == "restoring"
    assert "Cancel" in recording_ui.buttons

    await recording_ui.button_actions["Cancel"]()
    finish_restore.set()
    await batch_task

    output = tmp_path / "denoised_HRSTEM" / "a_first.tif"
    snapshot = state.snapshot()
    assert output.is_file()
    assert engine.restore_count == 1
    assert snapshot.batch_restore_state == "complete"
    assert snapshot.batch_progress_text == "3 of 3 files"
    assert (
        "Batch complete: 1 restored, 0 failed, 0 skipped, 2 cancelled."
        in snapshot.status
    )
    assert [row.status for row in snapshot.batch_file_results] == [
        BatchFileStatus.RESTORED,
        BatchFileStatus.CANCELLED,
        BatchFileStatus.CANCELLED,
    ]
    assert [row.detail for row in snapshot.batch_file_results[1:]] == [
        "Not processed",
        "Not processed",
    ]
    assert "Start Batch" in recording_ui.buttons
    assert "disable" not in recording_ui.button_props["Start Batch"]
    assert "disable" not in recording_ui.button_props["Add Folder"]


@pytest.mark.anyio
async def test_start_batch_button_prompts_when_no_folder_selected() -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    class EngineShouldNotRun:
        def restore(self, pixels, mode):  # noqa: ANN001
            raise AssertionError("Engine should not run without a Batch folder")

    state = InspectorShellState(selected_workflow="Batch")
    recording_ui = RecordingUi()
    render_nicegui_shell(ui_module=recording_ui, state=state, engine=EngineShouldNotRun())

    await recording_ui.button_actions["Start Batch"]()

    assert state.snapshot().status == "Add a folder before starting Batch."


def test_nicegui_shell_render_shows_raw_preview_without_comparison_divider(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    source = tmp_path / "wafer.tif"
    state = InspectorShellState()
    state.finish_single_image_selection(
        SingleImageInspection(
            source_path=source,
            preview_pixels=np.array([[0, 255]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )
    )

    recording_ui = RecordingUi()
    render_nicegui_shell(ui_module=recording_ui, state=state)

    preview_html = "\n".join(recording_ui.labels)
    assert "denoiser-preview-frame-active denoiser-raw-preview" in preview_html
    assert "denoiser-preview-image" in preview_html
    assert state.snapshot().raw_preview.data_url in preview_html
    assert "Selected image: wafer.tif" in recording_ui.labels
    assert "Existing outputs will be overwritten." in recording_ui.labels
    assert not any("divider" in label.lower() for label in recording_ui.labels)


def test_nicegui_shell_render_shows_comparison_with_divider_interactions(
    tmp_path: Path,
) -> None:
    from denoiser.models import DenoiseMode
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell
    from denoiser.workflow import SingleRestoreResult

    source = tmp_path / "wafer.tif"
    state = InspectorShellState()
    state.finish_single_restore(
        SingleRestoreResult(
            source_path=source,
            output_path=tmp_path / "denoised_HRSTEM" / "wafer.tif",
            mode=DenoiseMode.HRSTEM,
            raw_pixels=np.array([[0, 1]], dtype=np.float32),
            restored_pixels=np.array([[1, 2]], dtype=np.float32),
        )
    )

    recording_ui = RecordingUi()
    render_nicegui_shell(ui_module=recording_ui, state=state, engine=object())

    comparison_html = "\n".join(recording_ui.labels)
    assert "denoiser-preview-frame-active denoiser-comparison" in comparison_html
    assert "denoiser-comparison" in comparison_html
    assert 'data-divider="0.5"' in comparison_html
    assert 'data-raw-side="left"' in comparison_html
    assert 'data-restored-side="right"' in comparison_html
    assert 'role="slider"' in comparison_html
    assert "denoiser-comparison-hit-target" in comparison_html
    assert "onpointerdown" in comparison_html
    assert "onpointermove" in comparison_html


def test_nicegui_shell_comparison_divider_is_bound_to_fitted_image_area() -> None:
    from denoiser.nicegui_shell import build_inspector_shell_snapshot
    from denoiser.nicegui_shell import _shell_css

    css = _shell_css(build_inspector_shell_snapshot().design_tokens)

    assert "window.denoiserComparisonImageBounds" in css
    assert "naturalWidth" in css
    assert "naturalHeight" in css
    assert "relativeLeft" in css
    assert "relativeWidth" in css
    assert "--divider-frame-position" in css
    assert "--comparison-image-top" in css
    assert "--comparison-image-height" in css
    assert "event.clientX - bounds.left" in css


@pytest.mark.anyio
async def test_open_image_button_uses_mockable_path_selector_and_inspection(
    tmp_path: Path,
) -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    source = tmp_path / "wafer.tif"
    inspected_paths: list[Path] = []

    class PathSelector:
        async def select_single_image_path(self) -> Path:
            return source

    def inspect(path: Path) -> SingleImageInspection:
        inspected_paths.append(path)
        return SingleImageInspection(
            source_path=path,
            preview_pixels=np.array([[0, 255]], dtype=np.uint8),
            requires_patch_based_restore=False,
        )

    recording_ui = RecordingUi()
    state = InspectorShellState()
    render_nicegui_shell(
        ui_module=recording_ui,
        state=state,
        path_selector=PathSelector(),
        inspect_single_image=inspect,
    )

    assert "Open Image" in recording_ui.buttons
    await recording_ui.button_actions["Open Image"]()

    assert inspected_paths == [source]
    assert state.snapshot().single_preview_state == "selected"


@pytest.mark.anyio
async def test_native_path_selector_uses_native_file_dialog() -> None:
    from denoiser.nicegui_shell import NiceGuiNativePathSelector

    class NativeWindow:
        def __init__(self) -> None:
            self.dialog_kwargs: dict[str, object] | None = None

        async def create_file_dialog(self, **kwargs: object) -> list[str]:
            self.dialog_kwargs = kwargs
            return ["/case/wafer.tif"]

    class NativeApp:
        def __init__(self) -> None:
            self.main_window = NativeWindow()

    native_app = NativeApp()
    selector = NiceGuiNativePathSelector(native_app=native_app)

    assert await selector.select_single_image_path() == Path("/case/wafer.tif")
    assert native_app.main_window.dialog_kwargs == {
        "allow_multiple": False,
        "file_types": (
            "Supported images (*.tif;*.tiff;*.png;*.jpg;*.jpeg;*.dm3;*.dm4)",
        ),
    }


@pytest.mark.anyio
async def test_native_path_selector_uses_native_folder_dialog() -> None:
    from denoiser.nicegui_shell import NiceGuiNativePathSelector
    from denoiser.nicegui_shell import _native_folder_dialog_type

    class NativeWindow:
        def __init__(self) -> None:
            self.dialog_kwargs: dict[str, object] | None = None

        async def create_file_dialog(self, **kwargs: object) -> list[str]:
            self.dialog_kwargs = kwargs
            return ["/case"]

    class NativeApp:
        def __init__(self) -> None:
            self.main_window = NativeWindow()

    native_app = NativeApp()
    selector = NiceGuiNativePathSelector(native_app=native_app)

    assert await selector.select_batch_folder_path() == Path("/case")
    assert native_app.main_window.dialog_kwargs == {
        "allow_multiple": False,
        "dialog_type": _native_folder_dialog_type(),
    }
