# ADR 0001: Use PySide6 for the Windows desktop UI

## Status

Superseded by ADR 0004

## Context

Denoiser is a first-release MVS for FA engineers restoring 2D grayscale
SEM/STEM images. The first release targets Windows 10/11 laptops and must run
as a simple desktop app.

The UI needs file and folder pickers, mode buttons, progress/status display,
and a before/after image comparison view. End users should run `Denoiser.exe`
without installing Python, `uv`, or `pip`.

## Decision

Use PySide6 as the desktop frontend for the first release.

## Consequences

Positive:

- Keeps the app local and offline-friendly.
- Provides native file/folder dialogs and standard desktop widgets.
- Can be packaged into a folder-style Windows release with PyInstaller.
- Gives enough drawing support for the before/after compare view.

Trade-offs:

- UI tests need Qt event-loop handling and offscreen rendering setup.
- Windows packaging must include Qt/PySide6 runtime files.
- The app is a desktop tool, not a browser-based or web-deployed workflow.

## Alternatives Considered

- Web app: rejected for the first release because offline desktop use is a core
  requirement.
- CLI-only tool: rejected because FA engineers need image selection, progress,
  and visual before/after comparison.
