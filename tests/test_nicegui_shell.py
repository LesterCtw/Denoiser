from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from denoiser.image_io import ImageFormatError
from denoiser.single_image_inspection import SingleImageInspection


class RecordingElement:
    def __enter__(self) -> "RecordingElement":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def classes(self, value: str) -> "RecordingElement":
        return self

    def props(self, value: str) -> "RecordingElement":
        return self

    def style(self, value: str) -> "RecordingElement":
        return self


class RecordingUi:
    def __init__(self) -> None:
        self.head_html: list[str] = []
        self.labels: list[str] = []
        self.buttons: list[str] = []
        self.button_actions: dict[str, object] = {}
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
        return RecordingElement()

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


def test_readme_documents_first_nicegui_shell_without_restore_parity() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "First runnable NiceGUI native-window inspector shell" in readme
    assert "NiceGUI Single image selection and raw-only preview" in readme
    assert "NiceGUI restore parity 尚未完成" in readme


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
