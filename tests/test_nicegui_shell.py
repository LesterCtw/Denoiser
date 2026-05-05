from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile

from denoiser.image_io import ImageFormatError
from denoiser.single_image_inspection import SingleImageInspection


class RecordingElement:
    def __init__(self, props_sink: list[str] | None = None) -> None:
        self._props_sink = props_sink

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
        return self


class RecordingUi:
    def __init__(self) -> None:
        self.head_html: list[str] = []
        self.labels: list[str] = []
        self.buttons: list[str] = []
        self.button_actions: dict[str, object] = {}
        self.button_props: dict[str, list[str]] = {}
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
        return RecordingElement(self.button_props[text])

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
    assert state.snapshot().right_work_area_title == "Single image inspection"

    state.select_workflow("Batch")

    assert state.snapshot().selected_workflow == "Batch"
    assert state.snapshot().right_work_area_title == "Batch restore run"


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


def test_nicegui_shell_render_outputs_core_controls_and_dark_style() -> None:
    from denoiser.nicegui_shell import InspectorShellState, render_nicegui_shell

    recording_ui = RecordingUi()
    render_nicegui_shell(ui_module=recording_ui, state=InspectorShellState())

    assert "Denoiser" in recording_ui.labels
    assert "Single image inspection" in recording_ui.labels
    assert "Ready" in recording_ui.labels
    assert {"Single", "Batch", "HRSTEM", "LRSTEM", "HRSEM", "LRSEM", "Restore"} <= set(
        recording_ui.buttons
    )
    assert "#010102" in recording_ui.head_html[0]
    assert "#5e6ad2" in recording_ui.head_html[0]
    assert ".denoiser-shell" in recording_ui.head_html[0]


def test_nicegui_shell_runs_as_standard_native_window() -> None:
    from denoiser.nicegui_shell import run_nicegui_native_window

    recording_ui = RecordingUi()

    assert run_nicegui_native_window(ui_module=recording_ui) == 0

    assert recording_ui.run_kwargs == {
        "title": "Denoiser",
        "native": True,
        "window_size": (1280, 820),
        "fullscreen": False,
        "frameless": False,
        "reload": False,
        "show": False,
    }


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


def test_readme_documents_nicegui_single_restore_status() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "First runnable NiceGUI native-window inspector shell" in readme
    assert "NiceGUI Single image selection and raw-only preview" in readme
    assert "NiceGUI Single restore and before/after comparison" in readme
    assert "NiceGUI Batch restore parity 尚未完成" in readme


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
    assert f"Saved: {output.name}" in snapshot.status
    assert f"Folder: {output.parent.name}" in snapshot.status
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

    assert recording_ui.images == [state.snapshot().raw_preview.data_url]
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
    assert "denoiser-comparison" in comparison_html
    assert 'data-divider="0.5"' in comparison_html
    assert 'data-raw-side="left"' in comparison_html
    assert 'data-restored-side="right"' in comparison_html
    assert 'type="range"' in comparison_html
    assert "denoiser-comparison-control" in comparison_html
    assert "oninput" in comparison_html


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
