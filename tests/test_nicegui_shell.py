from __future__ import annotations

from pathlib import Path


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
        return RecordingElement()

    def html(self, html: str) -> RecordingElement:
        self.labels.append(html)
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
    assert "NiceGUI restore parity 尚未完成" in readme
