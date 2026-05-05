# ADR 0004: Use NiceGUI native window for the desktop UI

## Status

Accepted

Supersedes ADR 0001.

## Context

Denoiser already has a first MVS for FA engineers restoring 2D grayscale
SEM/STEM images with bundled `tk_r_em` ONNX models. The product remains a
local Windows desktop tool with Single restore, Batch restore run, offline CPU
inference, bundled model inventory, and English UI.

ADR 0001 selected PySide6 for the first desktop UI. That produced a working
functional desktop frontend, but the next frontend direction needs a more
modern, polished inspection-tool interface while preserving the same local
Windows workflow.

The repo now has `DESIGN.md` as the visual source of truth. The frontend
contract should point future work at that design system before implementation
starts.

## Decision

Use a NiceGUI native window as the desktop frontend direction for Denoiser.
Keep the standard Windows title bar instead of building a custom frameless
window. Use the repo `DESIGN.md` as the visual source of truth.

After the NiceGUI frontend reaches parity with the current MVS behavior,
Denoiser should have no PySide6 fallback and should not maintain two public
frontend stacks. Windows releases should remain folder-style PyInstaller
packages.

This decision is a documentation and architecture contract. It does not
implement the NiceGUI migration by itself.

## Consequences

Positive:

- Gives the frontend migration one clear target instead of two competing UI
  stacks.
- Aligns product documentation with the repo visual design contract.
- Keeps the app as a local Windows desktop tool rather than a browser-hosted
  or web-deployed workflow.
- Preserves the existing PyInstaller release path.

Trade-offs:

- NiceGUI native window introduces browser-view, local server lifecycle,
  WebSocket, and native-window packaging concerns that PySide6 did not have.
- Native file and folder selection must be kept behind a small testable
  boundary so NiceGUI-specific details do not leak into restore workflow code.
- PySide6 code and dependencies can only be removed after NiceGUI parity is
  reached, so there may be temporary migration overlap.

## Alternatives Considered

- Continue with PySide6: rejected because the next frontend direction needs a
  more modern UI and should follow the repo `DESIGN.md` contract.
- Keep PySide6 as a fallback after migration: rejected because maintaining two
  frontend stacks would add long-term complexity without improving the MVS
  restore behavior.
- Build a custom frameless Windows window: rejected for this migration because
  the standard Windows title bar keeps the desktop shell simpler and lower
  risk.
- Browser-hosted web deployment: rejected because offline Windows desktop use
  remains a core requirement.
