from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


DENOISING_MODES = ("HRSTEM", "LRSTEM", "HRSEM", "LRSEM")
WORKFLOWS = ("Single", "Batch")


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
    design_tokens: dict[str, str]


@dataclass
class InspectorShellState:
    selected_workflow: str = "Single"
    selected_denoising_mode: str = "HRSTEM"

    def select_workflow(self, workflow: str) -> None:
        if workflow not in WORKFLOWS:
            raise ValueError(f"Unsupported workflow: {workflow}")
        self.selected_workflow = workflow

    def select_denoising_mode(self, denoising_mode: str) -> None:
        if denoising_mode not in DENOISING_MODES:
            raise ValueError(f"Unsupported denoising mode: {denoising_mode}")
        self.selected_denoising_mode = denoising_mode

    def snapshot(self) -> InspectorShellSnapshot:
        return build_inspector_shell_snapshot(
            selected_workflow=self.selected_workflow,
            selected_denoising_mode=self.selected_denoising_mode,
        )


def build_inspector_shell_snapshot(
    *,
    selected_workflow: str = "Single",
    selected_denoising_mode: str = "HRSTEM",
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
        status="Ready",
        design_tokens=_load_design_tokens(),
    )


def render_nicegui_shell(
    *,
    state: InspectorShellState | None = None,
    ui_module: Any | None = None,
) -> InspectorShellState:
    if state is None:
        state = InspectorShellState()
    if ui_module is None:
        from nicegui import ui as ui_module

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
                ui_module.button(
                    workflow,
                    on_click=lambda workflow=workflow: (
                        state.select_workflow(workflow),
                        refresh_shell(),
                    ),
                ).classes(
                    "denoiser-pill denoiser-pill-selected"
                    if workflow == current.selected_workflow
                    else "denoiser-pill"
                )

    def render_mode_controls() -> None:
        current = state.snapshot()
        with ui_module.column().classes("denoiser-mode-list"):
            for mode in current.denoising_modes:
                ui_module.button(
                    mode,
                    on_click=lambda mode=mode: (
                        state.select_denoising_mode(mode),
                        refresh_shell(),
                    ),
                ).classes(
                    "denoiser-mode-button denoiser-mode-button-selected"
                    if current.mode_button_states[mode] == "selected"
                    else "denoiser-mode-button"
                )

    def render_work_area() -> None:
        current = state.snapshot()
        with ui_module.column().classes("denoiser-work-area"):
            ui_module.label(current.right_work_area_title).classes(
                "denoiser-work-title"
            )
            ui_module.html("<div class=\"denoiser-preview-placeholder\"></div>").classes(
                "denoiser-preview"
            )

    workflow_controls = _refreshable(ui_module, render_workflow_controls)
    mode_controls = _refreshable(ui_module, render_mode_controls)
    work_area = _refreshable(ui_module, render_work_area)
    refreshables.extend([workflow_controls, mode_controls, work_area])

    with ui_module.column().classes("denoiser-shell"):
        with ui_module.row().classes("denoiser-inspector"):
            with ui_module.column().classes("denoiser-control-rail"):
                ui_module.label(snapshot.title).classes("denoiser-product-title")

                workflow_controls()

                ui_module.label("Denoising mode").classes("denoiser-section-label")
                mode_controls()

                ui_module.button(snapshot.primary_action).classes(
                    "denoiser-primary-action"
                )
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
      .denoiser-pill,
      .denoiser-mode-button {{
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
    </style>
    """


def _right_work_area_title(selected_workflow: str) -> str:
    if selected_workflow == "Batch":
        return "Batch restore run"
    return "Single image inspection"


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
