from __future__ import annotations

import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from denoiser.app_icon import (
    application_icon_path,
    application_icon_source_path,
    application_macos_icon_path,
)
from denoiser.batch_presentation import BatchResultRow, batch_result_row
from denoiser.image_io import ImageFormatError
from denoiser.models import DenoiseMode, supported_denoise_modes
from denoiser.output_paths import output_path_for_input
from denoiser.preview_presentation import (
    ComparisonPreview,
    RawPreview,
    comparison_html,
    comparison_preview,
    raw_preview,
    raw_preview_html,
)
from denoiser.single_image_inspection import SingleImageInspection, inspect_single_image
from denoiser.workflow import (
    BatchRestoreResult,
    BatchRestoreRun,
    SingleRestoreResult,
    restore_single_image,
)


DENOISING_MODES = tuple(mode.value for mode in supported_denoise_modes())
WORKFLOWS = ("Single", "Batch")
ACTIVE_BATCH_RESTORE_STATES = {"restoring", "cancelling"}
SUPPORTED_IMAGE_FILE_DIALOG_FILTER = (
    "Supported images (*.tif;*.tiff;*.png;*.jpg;*.jpeg;*.dm3;*.dm4)",
)


@dataclass(frozen=True)
class InspectorShellSnapshot:
    title: str
    regions: tuple[str, str]
    workflows: tuple[str, str]
    selected_workflow: str
    denoising_modes: tuple[str, ...]
    selected_denoising_mode: str
    mode_button_states: dict[str, str]
    right_work_area_title: str
    primary_action: str
    status: str
    single_controls_enabled: bool
    single_preview_state: str
    selected_single_image_path: Path | None
    selected_batch_folder_path: Path | None
    overwrite_output_path: Path | None
    warnings: tuple[str, ...]
    raw_preview: RawPreview | None
    comparison_preview: ComparisonPreview | None
    batch_restore_state: str
    batch_progress_text: str
    batch_file_results: tuple[BatchResultRow, ...]
    design_tokens: dict[str, str]


class NativePathSelector(Protocol):
    async def select_single_image_path(self) -> Path | None: ...

    async def select_batch_folder_path(self) -> Path | None: ...


class NiceGuiNativePathSelector:
    def __init__(self, *, native_app: Any | None = None) -> None:
        if native_app is None:
            from nicegui import app as native_app

        self._native_app = getattr(native_app, "native", native_app)

    async def select_single_image_path(self) -> Path | None:
        selected = await self._native_app.main_window.create_file_dialog(
            allow_multiple=False,
            file_types=SUPPORTED_IMAGE_FILE_DIALOG_FILTER,
        )
        if not selected:
            return None
        if isinstance(selected, str):
            return Path(selected)
        return Path(selected[0])

    async def select_batch_folder_path(self) -> Path | None:
        selected = await self._native_app.main_window.create_file_dialog(
            allow_multiple=False,
            dialog_type=_native_folder_dialog_type(),
        )
        if not selected:
            return None
        if isinstance(selected, str):
            return Path(selected)
        return Path(selected[0])


@dataclass
class InspectorShellState:
    selected_workflow: str = "Single"
    selected_denoising_mode: str = "HRSTEM"
    single_preview_state: str = "idle"
    selected_single_image_path: Path | None = None
    status: str = "Ready"
    overwrite_output_path: Path | None = None
    selected_batch_folder_path: Path | None = None
    batch_restore_state: str = "idle"
    batch_progress_text: str = "0 of 0 files"
    batch_file_results: tuple[BatchResultRow, ...] = ()
    warnings: tuple[str, ...] = ()
    raw_preview: RawPreview | None = None
    comparison_preview: ComparisonPreview | None = None

    def select_workflow(self, workflow: str) -> None:
        if workflow not in WORKFLOWS:
            raise ValueError(f"Unsupported workflow: {workflow}")
        self.selected_workflow = workflow

    def select_denoising_mode(self, denoising_mode: str) -> None:
        if denoising_mode not in DENOISING_MODES:
            raise ValueError(f"Unsupported denoising mode: {denoising_mode}")
        self.selected_denoising_mode = denoising_mode
        if self.selected_single_image_path is not None:
            self.overwrite_output_path = _overwrite_output_path(
                self.selected_single_image_path,
                self.selected_denoising_mode,
            )

    def select_batch_folder_path(self, path: Path) -> None:
        self.selected_workflow = "Batch"
        self.selected_batch_folder_path = Path(path)
        self.batch_restore_state = "folder-selected"
        self.batch_progress_text = "0 of 0 files"
        self.batch_file_results = ()
        self.status = f"Batch folder: {Path(path).name}"

    def restore_selected_batch_folder(
        self,
        engine: Any,
        *,
        batch_restore_run_factory: Any = BatchRestoreRun,
    ) -> None:
        if self.selected_batch_folder_path is None:
            self.status = "Add a folder before starting Batch."
            self.batch_restore_state = "idle"
            return

        try:
            run = batch_restore_run_factory(
                self.selected_batch_folder_path,
                DenoiseMode(self.selected_denoising_mode),
                engine,
            )
        except ImageFormatError as exc:
            self.fail_batch_restore_start(exc)
            return
        self.begin_batch_restore_run(run)

        while True:
            step = run.next_step()
            self.apply_batch_restore_step(step)
            if step.final_result is not None:
                return

    def begin_batch_restore_run(self, run: BatchRestoreRun) -> None:
        self.batch_restore_state = "restoring"
        self.batch_file_results = ()
        self.batch_progress_text = f"{run.completed_count} of {run.total_count} files"
        self.status = "Batch restoring..."

    def request_batch_cancellation(self) -> None:
        if self.batch_restore_state == "restoring":
            self.batch_restore_state = "cancelling"
            self.status = "Cancelling batch..."

    def fail_batch_restore_start(self, exc: Exception) -> None:
        self.batch_restore_state = "folder-selected"
        self.batch_progress_text = "0 of 0 files"
        self.batch_file_results = ()
        self.status = f"Cannot start Batch: {exc}"

    def apply_batch_restore_step(self, step: Any) -> None:
        self.batch_file_results += tuple(
            batch_result_row(file_result) for file_result in step.file_results
        )
        self.batch_progress_text = f"{step.completed_count} of {step.total_count} files"
        if step.final_result is not None:
            self.finish_batch_restore(step.final_result)

    def finish_batch_restore(self, result: BatchRestoreResult) -> None:
        self.batch_restore_state = "complete"
        self.status = (
            "Batch complete: "
            f"{result.restored_count} restored, "
            f"{result.failed_count} failed, "
            f"{result.skipped_count} skipped, "
            f"{result.cancelled_count} cancelled."
        )

    def begin_single_image_selection(self, path: Path) -> None:
        self.selected_workflow = "Single"
        self.selected_single_image_path = Path(path)
        self.single_preview_state = "loading"
        self.status = f"Loading preview: {Path(path).name}"
        self.overwrite_output_path = _overwrite_output_path(
            Path(path),
            self.selected_denoising_mode,
        )
        self.warnings = ("Existing outputs will be overwritten.",)
        self.raw_preview = None
        self.comparison_preview = None

    def select_single_image_path(
        self,
        path: Path,
        *,
        inspect_single_image: Any = inspect_single_image,
    ) -> None:
        self.begin_single_image_selection(path)
        try:
            inspection = inspect_single_image(Path(path))
        except Exception as exc:
            self.fail_single_image_selection(Path(path), exc)
            return
        self.finish_single_image_selection(inspection)

    def fail_single_image_selection(self, path: Path, exc: Exception) -> None:
        self.selected_workflow = "Single"
        self.selected_single_image_path = Path(path)
        self.single_preview_state = "error"
        self.status = f"Cannot preview: {exc}"
        self.overwrite_output_path = None
        self.warnings = ()
        self.raw_preview = None
        self.comparison_preview = None

    def finish_single_image_selection(
        self,
        inspection: SingleImageInspection,
    ) -> None:
        self.selected_single_image_path = inspection.source_path
        self.single_preview_state = "selected"
        self.status = f"Selected image: {inspection.source_path.name}"
        self.overwrite_output_path = _overwrite_output_path(
            inspection.source_path,
            self.selected_denoising_mode,
        )
        warnings = ["Existing outputs will be overwritten."]
        if inspection.requires_patch_based_restore:
            warnings.append("Large images may take several minutes.")
        self.warnings = tuple(warnings)
        self.raw_preview = raw_preview(inspection.preview_pixels)
        self.comparison_preview = None

    def begin_single_restore(self) -> None:
        if not self._has_restorable_single_image():
            self.status = "Open an image before restoring."
            return None
        self.single_preview_state = "restoring"
        self.status = "Restoring..."
        return None

    def restore_selected_single_image(
        self,
        engine: Any,
        *,
        restore_single_image: Any = restore_single_image,
    ) -> None:
        if not self._has_restorable_single_image():
            self.begin_single_restore()
            return

        assert self.selected_single_image_path is not None
        path = self.selected_single_image_path
        mode = DenoiseMode(self.selected_denoising_mode)
        self.begin_single_restore()
        try:
            result = restore_single_image(path, mode, engine)
        except Exception as exc:
            self.fail_single_restore(exc)
            return
        self.finish_single_restore(result)

    def finish_single_restore(self, result: SingleRestoreResult) -> None:
        self.single_preview_state = "restored"
        self.selected_single_image_path = result.source_path
        self.overwrite_output_path = result.output_path
        self.status = (
            f"Saved image: {result.output_path.name}\n"
            f"Output folder: {result.output_path.parent.name}"
        )
        self.warnings = ()
        self.raw_preview = None
        self.comparison_preview = comparison_preview(
            result.raw_pixels,
            result.restored_pixels,
        )

    def fail_single_restore(self, exc: Exception) -> None:
        self.single_preview_state = "selected"
        self.status = f"Cannot restore: {exc}"

    def _has_restorable_single_image(self) -> bool:
        return (
            self.selected_single_image_path is not None
            and self.single_preview_state in {"selected", "restored"}
        )

    def snapshot(self) -> InspectorShellSnapshot:
        return build_inspector_shell_snapshot(
            selected_workflow=self.selected_workflow,
            selected_denoising_mode=self.selected_denoising_mode,
            single_preview_state=self.single_preview_state,
            selected_single_image_path=self.selected_single_image_path,
            selected_batch_folder_path=self.selected_batch_folder_path,
            overwrite_output_path=self.overwrite_output_path,
            status=self.status,
            warnings=self.warnings,
            raw_preview=self.raw_preview,
            comparison_preview=self.comparison_preview,
            batch_restore_state=self.batch_restore_state,
            batch_progress_text=self.batch_progress_text,
            batch_file_results=self.batch_file_results,
        )


def build_inspector_shell_snapshot(
    *,
    selected_workflow: str = "Single",
    selected_denoising_mode: str = "HRSTEM",
    single_preview_state: str = "idle",
    selected_single_image_path: Path | None = None,
    selected_batch_folder_path: Path | None = None,
    overwrite_output_path: Path | None = None,
    status: str = "Ready",
    warnings: tuple[str, ...] = (),
    raw_preview: RawPreview | None = None,
    comparison_preview: ComparisonPreview | None = None,
    batch_restore_state: str = "idle",
    batch_progress_text: str = "0 of 0 files",
    batch_file_results: tuple[BatchResultRow, ...] = (),
) -> InspectorShellSnapshot:
    if selected_workflow not in WORKFLOWS:
        raise ValueError(f"Unsupported workflow: {selected_workflow}")
    if selected_denoising_mode not in DENOISING_MODES:
        raise ValueError(f"Unsupported denoising mode: {selected_denoising_mode}")

    return InspectorShellSnapshot(
        title="Denoiser",
        regions=("left control rail", "right work area"),
        workflows=WORKFLOWS,
        selected_workflow=selected_workflow,
        denoising_modes=DENOISING_MODES,
        selected_denoising_mode=selected_denoising_mode,
        mode_button_states={
            mode: "selected" if mode == selected_denoising_mode else "idle"
            for mode in DENOISING_MODES
        },
        right_work_area_title=_right_work_area_title(selected_workflow),
        primary_action="Restore",
        status=status,
        single_controls_enabled=single_preview_state != "restoring",
        single_preview_state=single_preview_state,
        selected_single_image_path=selected_single_image_path,
        selected_batch_folder_path=selected_batch_folder_path,
        overwrite_output_path=overwrite_output_path,
        warnings=warnings,
        raw_preview=raw_preview,
        comparison_preview=comparison_preview,
        batch_restore_state=batch_restore_state,
        batch_progress_text=batch_progress_text,
        batch_file_results=batch_file_results,
        design_tokens=_load_design_tokens(),
    )


def render_nicegui_shell(
    *,
    state: InspectorShellState | None = None,
    ui_module: Any | None = None,
    path_selector: NativePathSelector | None = None,
    engine: Any | None = None,
    inspect_single_image: Any = inspect_single_image,
    restore_single_image: Any = restore_single_image,
    restore_runner: Any | None = None,
) -> InspectorShellState:
    if state is None:
        state = InspectorShellState()
    if ui_module is None:
        from nicegui import ui as ui_module
    if path_selector is None:
        path_selector = NiceGuiNativePathSelector()
    if engine is None:
        from denoiser.engine import OnnxDenoiser

        engine = OnnxDenoiser()
    if restore_runner is None:
        restore_runner = _run_restore_in_thread

    snapshot = state.snapshot()
    ui_module.add_head_html(_shell_css(snapshot.design_tokens))
    refreshables: list[Any] = []
    active_batch_run: BatchRestoreRun | None = None

    def refresh_shell() -> None:
        for refreshable in refreshables:
            refreshable.refresh()

    def render_workflow_controls() -> None:
        current = state.snapshot()
        with ui_module.row().classes("denoiser-segmented-control"):
            for workflow in current.workflows:
                button = ui_module.button(
                    workflow,
                    on_click=lambda workflow=workflow: (
                        state.select_workflow(workflow),
                        refresh_shell(),
                    ),
                )
                button.classes(
                    "denoiser-pill denoiser-pill-selected"
                    if workflow == current.selected_workflow
                    else "denoiser-pill"
                )
                button.style(
                    _button_style(
                        current.design_tokens,
                        selected=workflow == current.selected_workflow,
                    )
                )
                _disable_when_restoring(button, current)

    def render_mode_controls() -> None:
        current = state.snapshot()
        with ui_module.column().classes("denoiser-mode-list"):
            for mode in current.denoising_modes:
                button = ui_module.button(
                    mode,
                    on_click=lambda mode=mode: (
                        state.select_denoising_mode(mode),
                        refresh_shell(),
                    ),
                )
                button.classes(
                    "denoiser-mode-button denoiser-mode-button-selected"
                    if current.mode_button_states[mode] == "selected"
                    else "denoiser-mode-button"
                )
                button.style(
                    _button_style(
                        current.design_tokens,
                        selected=current.mode_button_states[mode] == "selected",
                    )
                )
                _disable_when_restoring(button, current)

    def render_path_controls() -> None:
        current = state.snapshot()
        if current.selected_workflow == "Batch":
            folder_button = ui_module.button("Add Folder", on_click=choose_batch_folder)
            folder_button.classes("denoiser-secondary-action")
            folder_button.style(_button_style(current.design_tokens))
            _disable_when_restoring(folder_button, current)
            return

        open_button = ui_module.button("Open Image", on_click=choose_single_image)
        open_button.classes("denoiser-secondary-action")
        open_button.style(_button_style(current.design_tokens))
        _disable_when_restoring(open_button, current)

    def render_action_controls() -> None:
        current = state.snapshot()
        if current.selected_workflow == "Batch":
            if current.batch_restore_state in ACTIVE_BATCH_RESTORE_STATES:
                cancel_button = ui_module.button("Cancel", on_click=cancel_selected_batch)
                cancel_button.classes("denoiser-secondary-action")
                cancel_button.style(_button_style(current.design_tokens))
                if current.batch_restore_state == "cancelling":
                    cancel_button.props("disable")
                return

            action_label = "Start Batch"
            action_handler = restore_selected_batch
        else:
            action_label = current.primary_action
            action_handler = restore_selected_image

        action_button = ui_module.button(action_label, on_click=action_handler)
        action_button.classes("denoiser-primary-action")
        action_button.style(_button_style(current.design_tokens, primary=True))
        _disable_when_restoring(action_button, current)

    def render_status_panel() -> None:
        current = state.snapshot()
        with ui_module.column().classes("denoiser-status-panel"):
            if _is_processing(current):
                ui_module.html(
                    '<div class="denoiser-status-progress" aria-label="Processing"></div>'
                ).classes("denoiser-status-progress-host")
            ui_module.label(current.status).classes("denoiser-status")
            for warning in current.warnings:
                ui_module.label(warning).classes("denoiser-warning")

    async def choose_single_image() -> None:
        path = await path_selector.select_single_image_path()
        if path is None:
            return

        state.begin_single_image_selection(Path(path))
        refresh_shell()
        try:
            inspection = inspect_single_image(Path(path))
        except Exception as exc:
            state.fail_single_image_selection(Path(path), exc)
        else:
            state.finish_single_image_selection(inspection)
        refresh_shell()

    async def choose_batch_folder() -> None:
        path = await path_selector.select_batch_folder_path()
        if path is None:
            return
        state.select_batch_folder_path(Path(path))
        refresh_shell()

    async def restore_selected_image() -> None:
        if not state._has_restorable_single_image():
            state.begin_single_restore()
            refresh_shell()
            return

        assert state.selected_single_image_path is not None
        path = state.selected_single_image_path
        mode = DenoiseMode(state.selected_denoising_mode)
        state.begin_single_restore()
        refresh_shell()
        try:
            result = await restore_runner(restore_single_image, path, mode, engine)
        except Exception as exc:
            state.fail_single_restore(exc)
        else:
            state.finish_single_restore(result)
        refresh_shell()

    async def cancel_selected_batch() -> None:
        if active_batch_run is None:
            return
        active_batch_run.cancel()
        state.request_batch_cancellation()
        refresh_shell()

    async def restore_selected_batch() -> None:
        nonlocal active_batch_run
        if state.selected_batch_folder_path is None:
            state.restore_selected_batch_folder(engine)
            refresh_shell()
            return

        try:
            run = BatchRestoreRun(
                state.selected_batch_folder_path,
                DenoiseMode(state.selected_denoising_mode),
                engine,
            )
        except ImageFormatError as exc:
            state.fail_batch_restore_start(exc)
            refresh_shell()
            return
        active_batch_run = run
        state.begin_batch_restore_run(run)
        refresh_shell()
        try:
            while True:
                step = await restore_runner(run.next_step)
                state.apply_batch_restore_step(step)
                refresh_shell()
                if step.final_result is not None:
                    return
        finally:
            active_batch_run = None

    def render_work_area() -> None:
        current = state.snapshot()
        with ui_module.column().classes("denoiser-work-area"):
            if current.right_work_area_title:
                ui_module.label(current.right_work_area_title).classes(
                    "denoiser-work-title"
                )

            if current.selected_workflow == "Batch":
                ui_module.html(_batch_results_html(current)).classes(
                    "denoiser-batch-results"
                )
            elif current.comparison_preview is not None:
                ui_module.html(comparison_html(current.comparison_preview)).classes(
                    "denoiser-preview"
                )
            elif current.raw_preview is not None:
                ui_module.html(raw_preview_html(current.raw_preview)).classes(
                    "denoiser-preview"
                )
            else:
                ui_module.html(
                    '<div class="denoiser-preview-frame denoiser-preview-placeholder"></div>'
                ).classes("denoiser-preview")

    workflow_controls = _refreshable(ui_module, render_workflow_controls)
    path_controls = _refreshable(ui_module, render_path_controls)
    mode_controls = _refreshable(ui_module, render_mode_controls)
    action_controls = _refreshable(ui_module, render_action_controls)
    status_panel = _refreshable(ui_module, render_status_panel)
    work_area = _refreshable(ui_module, render_work_area)
    refreshables.extend(
        [
            workflow_controls,
            path_controls,
            mode_controls,
            action_controls,
            status_panel,
            work_area,
        ]
    )

    with ui_module.column().classes("denoiser-shell"):
        with ui_module.row().classes("denoiser-inspector"):
            with ui_module.column().classes("denoiser-control-rail"):
                ui_module.label(snapshot.title).classes("denoiser-product-title")

                workflow_controls()

                path_controls()

                ui_module.label("Denoising mode").classes("denoiser-section-label")
                mode_controls()

                action_controls()
                status_panel()

            work_area()

    return state


class _ImmediateRefreshable:
    def __init__(self, render: Any) -> None:
        self._render = render

    def __call__(self) -> None:
        self._render()

    def refresh(self) -> None:
        self._render()


def _refreshable(ui_module: Any, render: Any) -> Any:
    refreshable = getattr(ui_module, "refreshable", None)
    if refreshable is None:
        return _ImmediateRefreshable(render)
    return refreshable(render)


def _disable_when_restoring(element: Any, snapshot: InspectorShellSnapshot) -> None:
    if (
        not snapshot.single_controls_enabled
        or snapshot.batch_restore_state in ACTIVE_BATCH_RESTORE_STATES
    ):
        element.props("disable")


def _is_processing(snapshot: InspectorShellSnapshot) -> bool:
    return (
        snapshot.single_preview_state == "restoring"
        or snapshot.batch_restore_state in ACTIVE_BATCH_RESTORE_STATES
    )


async def _run_restore_in_thread(callback: Any, *args: Any) -> Any:
    from nicegui import run

    return await run.io_bound(callback, *args)


def run_nicegui_native_window(*, ui_module: Any | None = None) -> int:
    if ui_module is None:
        from nicegui import ui as ui_module
    from nicegui import app as native_app

    icon_source_path = _native_window_icon_path()
    if icon_source_path is not None:
        native_app.native.start_args["icon"] = str(icon_source_path)

    def render_root() -> None:
        render_nicegui_shell(ui_module=ui_module)

    ui_module.run(
        root=render_root,
        title="Denoiser",
        favicon=application_icon_path(),
        native=True,
        window_size=(1280, 820),
        fullscreen=False,
        frameless=False,
        reload=False,
        show=False,
    )
    return 0


def _native_folder_dialog_type() -> Any:
    try:
        import webview
    except ImportError:
        return "folder"

    file_dialog = getattr(webview, "FileDialog", None)
    if file_dialog is not None:
        return file_dialog.FOLDER
    return getattr(webview, "FOLDER_DIALOG", "folder")


def _native_window_icon_path() -> Path | None:
    if sys.platform == "darwin":
        macos_icon_path = application_macos_icon_path()
        if macos_icon_path is not None:
            return macos_icon_path
    return application_icon_source_path()


def _shell_css(tokens: dict[str, str]) -> str:
    return f"""
    <style>
      html, body {{
        background: {tokens["canvas"]};
        margin: 0;
        overflow: hidden;
      }}
      .nicegui-content,
      .q-page {{
        padding: 0 !important;
        background: {tokens["canvas"]};
      }}
      .denoiser-shell {{
        height: 100vh;
        background: {tokens["canvas"]};
        color: {tokens["ink"]};
        font-family: Inter, "SF Pro Display", "Segoe UI", sans-serif;
        letter-spacing: 0;
        overflow: hidden;
      }}
      .denoiser-inspector {{
        display: flex;
        flex-wrap: nowrap;
        width: 100%;
        height: 100vh;
        gap: 0;
      }}
      .denoiser-control-rail {{
        flex: 0 0 304px;
        width: 304px;
        height: 100vh;
        background: {tokens["surface-1"]};
        border-right: 1px solid {tokens["hairline"]};
        padding: 22px;
        gap: 16px;
        overflow: hidden;
      }}
      .denoiser-work-area {{
        display: flex;
        flex-direction: column;
        align-items: stretch;
        flex: 1;
        min-width: 0;
        height: 100vh;
        background: {tokens["canvas"]};
        padding: 26px 28px 28px;
        gap: 14px;
        overflow: hidden;
      }}
      .denoiser-product-title {{
        color: {tokens["ink"]};
        font-size: 21px;
        font-weight: 600;
        line-height: 1.2;
      }}
      .denoiser-section-label,
      .denoiser-status {{
        color: {tokens["ink-muted"]};
        font-size: 13px;
        line-height: 1.45;
        white-space: pre-line;
      }}
      .denoiser-warning {{
        color: {tokens["primary"]};
        font-size: 13px;
        line-height: 1.45;
      }}
      .denoiser-status-panel {{
        margin-top: auto;
        gap: 6px;
        padding-top: 14px;
        border-top: 1px solid {tokens["hairline"]};
      }}
      .denoiser-status-progress-host {{
        width: 100%;
      }}
      .denoiser-status-progress {{
        position: relative;
        width: 100%;
        height: 3px;
        overflow: hidden;
        border-radius: 999px;
        background: {tokens["surface-3"]};
      }}
      .denoiser-status-progress::before {{
        content: "";
        position: absolute;
        top: 0;
        bottom: 0;
        width: 38%;
        border-radius: 999px;
        background: {tokens["primary"]};
        animation: denoiser-status-progress-slide 1.1s ease-in-out infinite;
      }}
      @keyframes denoiser-status-progress-slide {{
        0% {{
          transform: translateX(-110%);
        }}
        100% {{
          transform: translateX(275%);
        }}
      }}
      .denoiser-segmented-control {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        width: 100%;
      }}
      .denoiser-mode-list {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        width: 100%;
      }}
      .denoiser-control-rail .q-btn {{
        min-height: 38px;
        width: 100%;
        box-shadow: none !important;
        text-transform: none;
        font-size: 14px;
        font-weight: 500;
        line-height: 1.2;
      }}
      .denoiser-secondary-action,
      .denoiser-primary-action {{
        margin-top: 2px;
      }}
      .denoiser-pill,
      .denoiser-mode-button,
      .denoiser-secondary-action {{
        background: {tokens["surface-2"]} !important;
        color: {tokens["ink"]} !important;
        border: 1px solid {tokens["hairline"]};
        border-radius: 8px;
        padding: 8px 12px;
      }}
      .denoiser-pill-selected,
      .denoiser-mode-button-selected {{
        background: {tokens["surface-3"]} !important;
        color: {tokens["ink"]} !important;
        border: 1px solid {tokens["primary"]};
      }}
      .denoiser-primary-action {{
        background: {tokens["primary"]} !important;
        color: white !important;
        border: 1px solid {tokens["primary"]};
        border-radius: 8px;
        padding: 9px 14px;
      }}
      .q-btn.denoiser-pill,
      .q-btn.denoiser-mode-button,
      .q-btn.denoiser-secondary-action {{
        background: {tokens["surface-2"]} !important;
        color: {tokens["ink"]} !important;
        border: 1px solid {tokens["hairline"]} !important;
      }}
      .q-btn.denoiser-pill-selected,
      .q-btn.denoiser-mode-button-selected {{
        background: {tokens["surface-3"]} !important;
        color: {tokens["ink"]} !important;
        border: 1px solid {tokens["primary"]} !important;
      }}
      .q-btn.denoiser-primary-action {{
        background: {tokens["primary"]} !important;
        color: white !important;
        border: 1px solid {tokens["primary"]} !important;
      }}
      .q-btn.denoiser-pill .q-focus-helper,
      .q-btn.denoiser-mode-button .q-focus-helper,
      .q-btn.denoiser-secondary-action .q-focus-helper,
      .q-btn.denoiser-primary-action .q-focus-helper {{
        opacity: 0 !important;
        background: transparent !important;
        display: none !important;
      }}
      .q-btn.denoiser-pill .q-btn__content,
      .q-btn.denoiser-mode-button .q-btn__content,
      .q-btn.denoiser-secondary-action .q-btn__content {{
        background: {tokens["surface-2"]} !important;
        color: {tokens["ink"]} !important;
      }}
      .q-btn.denoiser-pill-selected .q-btn__content,
      .q-btn.denoiser-mode-button-selected .q-btn__content {{
        background: {tokens["surface-3"]} !important;
        color: {tokens["ink"]} !important;
      }}
      .q-btn.denoiser-primary-action .q-btn__content {{
        background: {tokens["primary"]} !important;
        color: white !important;
      }}
      .q-btn.denoiser-pill .q-btn__content,
      .q-btn.denoiser-mode-button .q-btn__content,
      .q-btn.denoiser-secondary-action .q-btn__content,
      .q-btn.denoiser-primary-action .q-btn__content {{
        position: absolute;
        inset: 0;
        border-radius: 7px;
      }}
      .q-btn.denoiser-pill::before,
      .q-btn.denoiser-mode-button::before,
      .q-btn.denoiser-secondary-action::before,
      .q-btn.denoiser-primary-action::before {{
        box-shadow: none !important;
      }}
      .denoiser-work-title {{
        color: {tokens["ink"]};
        font-size: 26px;
        font-weight: 600;
        line-height: 1.2;
      }}
      .denoiser-preview {{
        display: block;
        flex: 1 1 auto;
        align-self: stretch;
        min-height: 0;
        width: 100%;
      }}
      nicegui-html.denoiser-preview {{
        display: block !important;
        align-self: stretch !important;
        width: 100% !important;
      }}
      .denoiser-preview-frame {{
        position: relative;
        box-sizing: border-box;
        width: calc(100vw - 360px);
        height: calc(100vh - 54px);
        min-height: 0;
        overflow: hidden;
        border: 1px solid {tokens["hairline"]};
        border-radius: 8px;
        background: {tokens["surface-1"]};
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.015);
      }}
      .denoiser-preview-frame-active {{
        background: #050506;
      }}
      .denoiser-preview-placeholder {{
        background: {tokens["surface-1"]};
      }}
      .denoiser-raw-preview {{
        display: flex;
        align-items: center;
        justify-content: center;
      }}
      .denoiser-preview-image {{
        display: block;
        width: 100%;
        height: 100%;
        object-fit: contain;
        image-rendering: auto;
      }}
      .denoiser-comparison {{
        --divider-position: 0.5;
        --divider-frame-position: 50%;
        --comparison-image-top: 0px;
        --comparison-image-height: 100%;
        user-select: none;
        touch-action: none;
        cursor: ew-resize;
      }}
      .denoiser-comparison img {{
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: contain;
      }}
      .denoiser-comparison-restored {{
        clip-path: inset(0 0 0 var(--divider-frame-position));
      }}
      .denoiser-comparison-divider {{
        position: absolute;
        top: var(--comparison-image-top);
        left: var(--divider-frame-position);
        width: 2px;
        height: var(--comparison-image-height);
        background: white;
        box-shadow:
          0 0 0 1px rgba(0, 0, 0, 0.72),
          0 0 0 3px rgba(94, 106, 210, 0.28);
        pointer-events: none;
      }}
      .denoiser-comparison-hit-target {{
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        cursor: ew-resize;
        background: transparent;
      }}
      .denoiser-batch-results {{
        display: flex;
        flex-direction: column;
        gap: 10px;
        min-height: 0;
        overflow: hidden;
      }}
      .denoiser-batch-progress {{
        color: {tokens["ink-muted"]};
        font-size: 13px;
        line-height: 1.4;
      }}
      .denoiser-batch-list {{
        display: flex;
        flex-direction: column;
        gap: 0;
        min-height: 0;
        overflow: auto;
        border: 1px solid {tokens["hairline"]};
        border-radius: 8px;
        background: {tokens["surface-1"]};
      }}
      .denoiser-batch-empty {{
        color: {tokens["ink-subtle"]};
        font-size: 13px;
        line-height: 1.45;
        padding: 2px 0;
      }}
      .denoiser-batch-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 10px;
        align-items: center;
        min-height: 42px;
        padding: 8px 10px;
        border-bottom: 1px solid {tokens["hairline"]};
      }}
      .denoiser-batch-row:last-child {{
        border-bottom: 0;
      }}
      .denoiser-batch-file {{
        color: {tokens["ink"]};
        font-size: 13px;
        line-height: 1.35;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .denoiser-batch-detail {{
        color: {tokens["ink-muted"]};
        font-size: 12px;
        line-height: 1.35;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .denoiser-batch-badge {{
        border-radius: 999px;
        padding: 3px 7px;
        font-size: 12px;
        line-height: 1.4;
        white-space: nowrap;
      }}
      .denoiser-batch-status-restored {{
        color: #9ee6b7;
        background: rgba(58, 166, 94, 0.18);
      }}
      .denoiser-batch-status-skipped {{
        color: #e5d18b;
        background: rgba(174, 139, 43, 0.2);
      }}
      .denoiser-batch-status-failed {{
        color: #ffb4a8;
        background: rgba(207, 62, 62, 0.18);
      }}
      .denoiser-batch-status-cancelled {{
        color: #c7ceda;
        background: rgba(127, 139, 158, 0.18);
      }}
    </style>
    <script>
      window.denoiserComparisonImageBounds = root => {{
        const rect = root.getBoundingClientRect();
        const image = root.querySelector('img');
        const fallback = {{
          left: rect.left,
          width: rect.width,
          relativeLeft: 0,
          relativeTop: 0,
          relativeWidth: rect.width,
          relativeHeight: rect.height,
        }};
        if (!rect.width || !rect.height || !image?.naturalWidth || !image?.naturalHeight) {{
          return fallback;
        }}

        const frameRatio = rect.width / rect.height;
        const imageRatio = image.naturalWidth / image.naturalHeight;
        let relativeWidth = rect.width;
        let relativeHeight = rect.height;
        let relativeLeft = 0;
        let relativeTop = 0;
        if (imageRatio > frameRatio) {{
          relativeHeight = rect.width / imageRatio;
          relativeTop = (rect.height - relativeHeight) / 2;
        }} else {{
          relativeWidth = rect.height * imageRatio;
          relativeLeft = (rect.width - relativeWidth) / 2;
        }}

        return {{
          left: rect.left + relativeLeft,
          width: relativeWidth,
          relativeLeft,
          relativeTop,
          relativeWidth,
          relativeHeight,
        }};
      }};
      window.denoiserApplyComparisonDivider = (root, value) => {{
        const rect = root.getBoundingClientRect();
        const bounds = window.denoiserComparisonImageBounds(root);
        const next = Math.max(0, Math.min(1, value));
        const frameX = bounds.relativeLeft + bounds.relativeWidth * next;
        const framePercent = rect.width ? `${{(frameX / rect.width) * 100}}%` : `${{next * 100}}%`;
        root.dataset.divider = String(next);
        root.style.setProperty('--divider-position', String(next));
        root.style.setProperty('--divider-frame-position', framePercent);
        root.style.setProperty('--comparison-image-top', `${{bounds.relativeTop}}px`);
        root.style.setProperty('--comparison-image-height', `${{bounds.relativeHeight}}px`);
        root.setAttribute('aria-valuenow', String(Math.round(next * 100)));
      }};
      window.denoiserRefreshComparisonDivider = root => {{
        if (!root) return;
        const current = Number(root.dataset.divider || '0.5');
        window.denoiserApplyComparisonDivider(root, current);
      }};
      window.denoiserSetComparisonDivider = (root, event) => {{
        const bounds = window.denoiserComparisonImageBounds(root);
        if (!bounds.width) return;
        const value = (event.clientX - bounds.left) / bounds.width;
        window.denoiserApplyComparisonDivider(root, value);
      }};
      window.denoiserMoveComparisonDividerWithKey = (root, event) => {{
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const current = Number(root.dataset.divider || '0.5');
        let next = current;
        if (event.key === 'ArrowLeft') next = current - 0.05;
        if (event.key === 'ArrowRight') next = current + 0.05;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = 1;
        window.denoiserApplyComparisonDivider(root, next);
      }};
      if (!window.denoiserComparisonListenersInstalled) {{
        window.denoiserComparisonListenersInstalled = true;
        window.denoiserActiveComparison = null;
        document.addEventListener('mousedown', event => {{
          const root = event.target.closest?.('.denoiser-comparison');
          if (!root) return;
          window.denoiserActiveComparison = root;
          window.denoiserSetComparisonDivider(root, event);
        }});
        document.addEventListener('mousemove', event => {{
          if (!window.denoiserActiveComparison || !event.buttons) return;
          window.denoiserSetComparisonDivider(window.denoiserActiveComparison, event);
        }});
        document.addEventListener('mouseup', () => {{
          window.denoiserActiveComparison = null;
        }});
        document.addEventListener('pointerdown', event => {{
          const root = event.target.closest?.('.denoiser-comparison');
          if (!root) return;
          window.denoiserActiveComparison = root;
          window.denoiserSetComparisonDivider(root, event);
        }});
        document.addEventListener('pointermove', event => {{
          if (!window.denoiserActiveComparison || !event.buttons) return;
          window.denoiserSetComparisonDivider(window.denoiserActiveComparison, event);
        }});
        document.addEventListener('pointerup', () => {{
          window.denoiserActiveComparison = null;
        }});
        window.addEventListener('resize', () => {{
          document.querySelectorAll('.denoiser-comparison').forEach(root => {{
            window.denoiserRefreshComparisonDivider(root);
          }});
        }});
        document.addEventListener('keydown', event => {{
          const root = event.target.closest?.('.denoiser-comparison');
          if (!root) return;
          window.denoiserMoveComparisonDividerWithKey(root, event);
        }});
      }}
    </script>
    """


def _right_work_area_title(selected_workflow: str) -> str:
    if selected_workflow == "Batch":
        return "Batch Restore"
    return ""


def _button_style(
    tokens: dict[str, str],
    *,
    selected: bool = False,
    primary: bool = False,
) -> str:
    background = tokens["surface-2"]
    border = tokens["hairline"]
    if selected:
        background = tokens["surface-3"]
        border = tokens["primary"]
    if primary:
        background = tokens["primary"]
        border = tokens["primary"]

    return (
        f"background: {background}; "
        f"background-color: {background}; "
        f"color: {tokens['ink'] if not primary else '#ffffff'}; "
        f"border: 1px solid {border}; "
        "box-shadow: none; "
        "text-transform: none;"
    )


def _overwrite_output_path(path: Path, denoising_mode: str) -> Path:
    return output_path_for_input(path, DenoiseMode(denoising_mode))


def _batch_results_html(snapshot: InspectorShellSnapshot) -> str:
    rows = "\n".join(_batch_result_html(row) for row in snapshot.batch_file_results)
    if rows:
        body = f'<div class="denoiser-batch-list">{rows}</div>'
    else:
        body = '<div class="denoiser-batch-empty">No files processed yet.</div>'
    return f"""
    <div class="denoiser-batch-results">
      <div class="denoiser-batch-progress">{snapshot.batch_progress_text}</div>
      {body}
    </div>
    """


def _batch_result_html(row: BatchResultRow) -> str:
    status_class = row.status.value
    filename = html.escape(row.filename)
    detail = html.escape(row.detail)
    status_label = html.escape(row.status_label)
    return f"""
    <div class="denoiser-batch-row">
      <div>
        <div class="denoiser-batch-file">{filename}</div>
        <div class="denoiser-batch-detail">{detail}</div>
      </div>
      <div class="denoiser-batch-badge denoiser-batch-status-{status_class}">
        {status_label}
      </div>
    </div>
    """


def _load_design_tokens() -> dict[str, str]:
    design_path = Path("DESIGN.md")
    fallback = {
        "canvas": "#010102",
        "surface-1": "#0f1011",
        "surface-2": "#141516",
        "surface-3": "#18191a",
        "primary": "#5e6ad2",
        "ink": "#f7f8f8",
        "ink-muted": "#d0d6e0",
        "ink-subtle": "#8a8f98",
        "hairline": "#23252a",
        "hairline-strong": "#34343a",
    }
    if not design_path.exists():
        return fallback

    tokens: dict[str, str] = {}
    needed = set(fallback)
    for line in design_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        for name in needed - set(tokens):
            prefix = f"{name}: "
            if stripped.startswith(prefix):
                tokens[name] = stripped.removeprefix(prefix).strip('"')

    return fallback | tokens
