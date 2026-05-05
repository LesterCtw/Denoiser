from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from denoiser.models import DenoiseMode
from denoiser.output_paths import output_path_for_input
from denoiser.single_image_inspection import SingleImageInspection, inspect_single_image
from denoiser.workflow import SingleRestoreResult, restore_single_image


DENOISING_MODES = ("HRSTEM", "LRSTEM", "HRSEM", "LRSEM")
WORKFLOWS = ("Single", "Batch")
SUPPORTED_IMAGE_FILE_DIALOG_FILTER = (
    "Supported images (*.tif;*.tiff;*.png;*.jpg;*.jpeg;*.dm3;*.dm4)",
)


@dataclass(frozen=True)
class InspectorShellSnapshot:
    title: str
    regions: tuple[str, str]
    workflows: tuple[str, str]
    selected_workflow: str
    denoising_modes: tuple[str, str, str, str]
    selected_denoising_mode: str
    mode_button_states: dict[str, str]
    right_work_area_title: str
    primary_action: str
    status: str
    single_controls_enabled: bool
    single_preview_state: str
    selected_single_image_path: Path | None
    overwrite_output_path: Path | None
    warnings: tuple[str, ...]
    raw_preview: RawPreview | None
    comparison_preview: ComparisonPreview | None
    design_tokens: dict[str, str]


@dataclass(frozen=True)
class RawPreview:
    data_url: str
    is_comparing: bool = False


@dataclass(frozen=True)
class ComparisonPreview:
    raw_data_url: str
    restored_data_url: str
    divider_position: float = 0.5
    raw_side: str = "left"
    restored_side: str = "right"
    supports_click_to_jump: bool = True
    supports_drag: bool = True


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


@dataclass
class InspectorShellState:
    selected_workflow: str = "Single"
    selected_denoising_mode: str = "HRSTEM"
    single_preview_state: str = "idle"
    selected_single_image_path: Path | None = None
    status: str = "Ready"
    overwrite_output_path: Path | None = None
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
        self.raw_preview = RawPreview(data_url=_raw_preview_data_url(inspection.preview_pixels))
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
            f"Saved: {result.output_path.name}\n"
            f"Folder: {result.output_path.parent.name}"
        )
        self.warnings = ()
        self.raw_preview = None
        self.comparison_preview = _comparison_preview(
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
            overwrite_output_path=self.overwrite_output_path,
            status=self.status,
            warnings=self.warnings,
            raw_preview=self.raw_preview,
            comparison_preview=self.comparison_preview,
        )


def build_inspector_shell_snapshot(
    *,
    selected_workflow: str = "Single",
    selected_denoising_mode: str = "HRSTEM",
    single_preview_state: str = "idle",
    selected_single_image_path: Path | None = None,
    overwrite_output_path: Path | None = None,
    status: str = "Ready",
    warnings: tuple[str, ...] = (),
    raw_preview: RawPreview | None = None,
    comparison_preview: ComparisonPreview | None = None,
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
        overwrite_output_path=overwrite_output_path,
        warnings=warnings,
        raw_preview=raw_preview,
        comparison_preview=comparison_preview,
        design_tokens=_load_design_tokens(),
    )


def render_nicegui_shell(
    *,
    state: InspectorShellState | None = None,
    ui_module: Any | None = None,
    path_selector: Any | None = None,
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
                _disable_when_restoring(button, current)

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

    def render_work_area() -> None:
        current = state.snapshot()
        with ui_module.column().classes("denoiser-work-area"):
            ui_module.label(current.right_work_area_title).classes(
                "denoiser-work-title"
            )
            ui_module.label(current.status).classes("denoiser-status")
            for warning in current.warnings:
                ui_module.label(warning).classes("denoiser-warning")

            if current.comparison_preview is not None:
                ui_module.html(_comparison_html(current.comparison_preview)).classes(
                    "denoiser-preview"
                )
            elif current.raw_preview is not None:
                ui_module.image(current.raw_preview.data_url).classes(
                    "denoiser-raw-preview"
                )
            else:
                ui_module.html(
                    "<div class=\"denoiser-preview-placeholder\"></div>"
                ).classes("denoiser-preview")

    workflow_controls = _refreshable(ui_module, render_workflow_controls)
    mode_controls = _refreshable(ui_module, render_mode_controls)
    work_area = _refreshable(ui_module, render_work_area)
    refreshables.extend([workflow_controls, mode_controls, work_area])

    with ui_module.column().classes("denoiser-shell"):
        with ui_module.row().classes("denoiser-inspector"):
            with ui_module.column().classes("denoiser-control-rail"):
                ui_module.label(snapshot.title).classes("denoiser-product-title")

                workflow_controls()

                open_button = ui_module.button("Open Image", on_click=choose_single_image)
                open_button.classes("denoiser-secondary-action")
                _disable_when_restoring(open_button, state.snapshot())

                ui_module.label("Denoising mode").classes("denoiser-section-label")
                mode_controls()

                restore_button = ui_module.button(
                    snapshot.primary_action,
                    on_click=restore_selected_image,
                )
                restore_button.classes("denoiser-primary-action")
                _disable_when_restoring(restore_button, state.snapshot())
                ui_module.label(snapshot.status).classes("denoiser-status")

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
    if not snapshot.single_controls_enabled:
        element.props("disable")


async def _run_restore_in_thread(callback: Any, *args: Any) -> Any:
    from nicegui import run

    return await run.io_bound(callback, *args)


def run_nicegui_native_window(*, ui_module: Any | None = None) -> int:
    if ui_module is None:
        from nicegui import ui as ui_module

    render_nicegui_shell(ui_module=ui_module)
    ui_module.run(
        title="Denoiser",
        native=True,
        window_size=(1280, 820),
        fullscreen=False,
        frameless=False,
        reload=False,
        show=False,
    )
    return 0


def _shell_css(tokens: dict[str, str]) -> str:
    return f"""
    <style>
      html, body {{
        background: {tokens["canvas"]};
      }}
      .denoiser-shell {{
        min-height: 100vh;
        background: {tokens["canvas"]};
        color: {tokens["ink"]};
        font-family: Inter, "SF Pro Display", "Segoe UI", sans-serif;
      }}
      .denoiser-inspector {{
        width: 100%;
        min-height: 100vh;
        gap: 0;
      }}
      .denoiser-control-rail {{
        width: 320px;
        min-height: 100vh;
        background: {tokens["surface-1"]};
        border-right: 1px solid {tokens["hairline"]};
        padding: 24px;
        gap: 18px;
      }}
      .denoiser-work-area {{
        flex: 1;
        min-height: 100vh;
        background: {tokens["canvas"]};
        padding: 28px;
        gap: 20px;
      }}
      .denoiser-product-title {{
        font-size: 22px;
        font-weight: 600;
      }}
      .denoiser-section-label,
      .denoiser-status {{
        color: {tokens["ink-muted"]};
        font-size: 13px;
      }}
      .denoiser-warning {{
        color: {tokens["primary"]};
        font-size: 13px;
      }}
      .denoiser-pill,
      .denoiser-mode-button,
      .denoiser-secondary-action {{
        background: {tokens["surface-2"]} !important;
        color: {tokens["ink"]} !important;
        border: 1px solid {tokens["hairline"]};
        border-radius: 8px;
      }}
      .denoiser-pill-selected,
      .denoiser-mode-button-selected,
      .denoiser-primary-action {{
        background: {tokens["primary"]} !important;
        color: white !important;
      }}
      .denoiser-work-title {{
        font-size: 28px;
        font-weight: 600;
      }}
      .denoiser-preview-placeholder {{
        min-height: 420px;
        border: 1px solid {tokens["hairline"]};
        border-radius: 8px;
        background: linear-gradient(135deg, {tokens["surface-1"]}, {tokens["surface-2"]});
      }}
      .denoiser-raw-preview {{
        width: 100%;
        max-height: calc(100vh - 160px);
        object-fit: contain;
        border: 1px solid {tokens["hairline"]};
        border-radius: 8px;
        background: {tokens["surface-1"]};
      }}
      .denoiser-comparison {{
        position: relative;
        width: 100%;
        min-height: 420px;
        max-height: calc(100vh - 160px);
        overflow: hidden;
        border: 1px solid {tokens["hairline"]};
        border-radius: 8px;
        background: {tokens["surface-1"]};
        user-select: none;
        touch-action: none;
      }}
      .denoiser-comparison img {{
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: contain;
      }}
      .denoiser-comparison-restored {{
        clip-path: inset(0 0 0 50%);
      }}
      .denoiser-comparison-divider {{
        position: absolute;
        top: 0;
        bottom: 0;
        left: 50%;
        width: 1px;
        background: white;
        box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.72);
      }}
      .denoiser-comparison-control {{
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        opacity: 0;
        cursor: ew-resize;
      }}
    </style>
    """


def _right_work_area_title(selected_workflow: str) -> str:
    if selected_workflow == "Batch":
        return "Batch restore run"
    return "Single image inspection"


def _overwrite_output_path(path: Path, denoising_mode: str) -> Path:
    return output_path_for_input(path, DenoiseMode(denoising_mode))


def _raw_preview_data_url(preview_pixels: np.ndarray) -> str:
    pixels = np.asarray(preview_pixels)
    if pixels.ndim != 2:
        raise ValueError(f"Raw preview expects 2D pixels, got shape {pixels.shape}.")

    display = pixels.astype(np.float32, copy=False)
    minimum = float(np.nanmin(display))
    maximum = float(np.nanmax(display))
    if maximum > minimum:
        display = (display - minimum) / (maximum - minimum)
    else:
        display = np.zeros_like(display, dtype=np.float32)
    display_uint8 = np.clip(np.rint(display * 255), 0, 255).astype(np.uint8)

    buffer = BytesIO()
    Image.fromarray(display_uint8).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _comparison_preview(raw_pixels: np.ndarray, restored_pixels: np.ndarray) -> ComparisonPreview:
    return ComparisonPreview(
        raw_data_url=_raw_preview_data_url(raw_pixels),
        restored_data_url=_raw_preview_data_url(restored_pixels),
    )


def _comparison_html(preview: ComparisonPreview) -> str:
    divider_percent = preview.divider_position * 100
    return f"""
    <div class="denoiser-comparison"
         data-divider="{preview.divider_position}"
         data-raw-side="{preview.raw_side}"
         data-restored-side="{preview.restored_side}">
      <img class="denoiser-comparison-raw" src="{preview.raw_data_url}" alt="Raw image">
      <img class="denoiser-comparison-restored" src="{preview.restored_data_url}" alt="Restored image">
      <div class="denoiser-comparison-divider"></div>
      <input class="denoiser-comparison-control"
             type="range"
             min="0"
             max="100"
             value="{divider_percent}"
             aria-label="Before after comparison divider"
             oninput="
               const root = this.closest('.denoiser-comparison');
               const percent = this.value + '%';
               root.dataset.divider = String(Number(this.value) / 100);
               root.querySelector('.denoiser-comparison-restored').style.clipPath =
                 'inset(0 0 0 ' + percent + ')';
               root.querySelector('.denoiser-comparison-divider').style.left = percent;
             ">
    </div>
    """


def _load_design_tokens() -> dict[str, str]:
    design_path = Path("DESIGN.md")
    fallback = {
        "canvas": "#010102",
        "surface-1": "#0f1011",
        "surface-2": "#141516",
        "primary": "#5e6ad2",
        "ink": "#f7f8f8",
        "ink-muted": "#d0d6e0",
        "hairline": "#23252a",
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
