# Denoiser

Project status: product scope defined for the first Minimum Viable Solution
(MVS). This README is the source of truth for current project status.

Denoiser is a simple Windows desktop tool for FA engineers to restore
grayscale SEM/STEM images using the `tk_r_em` ONNX models as the denoising
engine.

## Current setup

- GitHub repo: `LesterCtw/Denoiser`
- Issue tracker: GitHub Issues
- Agent instructions: `AGENTS.md`
- Domain context: `CONTEXT.md`
- Architecture decisions: `docs/adr/`
- Pre-commit hooks: Husky runs lint-staged Prettier and `uv run pytest`.

## Current implementation status

Implemented:

- Project skeleton with `src/denoiser` package layout.
- PySide6 application entry point and placeholder main window.
- Four required ONNX model files committed under `models/`.
- Third-party notices and upstream `tk_r_em` GPL license copy.
- Minimal CPU ONNX inference wrapper for whole-image inference.
- Single-image restore workflow for small images using the bundled ONNX models.
- Single mode UI wiring for image selection, mode buttons, Restore, automatic
  saving, and success/failure status.
- Before/after compare view for Single mode with fit-to-window drawing, a 50%
  starting divider, drag interaction, and click-to-jump interaction.
- Image I/O boundary for the first supported formats.
- Output path rules using `denoised_MODE` folders.
- Output dtype/range preparation that clips to the original image min/max and
  avoids automatic contrast stretching.
- Focused tests for model mapping, missing model handling, whole-image
  inference, Single restore workflow, Single UI restore behavior, output naming,
  before/after compare view interaction, denoised-folder rejection,
  unsupported-input rejection, multi-page TIFF rejection, JPEG-to-TIFF output,
  PNG/TIFF output preservation, RGB/RGBA-to-grayscale conversion, overwrite
  behavior, and uint16 TIFF clipping.

Not implemented yet:

- Patch-based inference for large images.
- Full Batch UI behavior.
- Batch progress list and cancellation.
- TIFF metadata preservation beyond safe basic image writing.
- Windows release build verification.

## First MVS scope

- Desktop frontend: PySide6
- Target platform: Windows 10/11 laptop PCs
- Runtime: CPU only
- Distribution: folder-style Windows release with `Denoiser.exe`
- Offline use: required; model files are committed to this repo and bundled with
  the release
- Product name / brand: `Denoiser`
- UI language: English
- Development dependency manager: `uv`
- Windows build/deployment dependency install path: `pip install`
- Release build platform: Windows builds the Windows release

## Engine integration

Denoiser will use a minimal local engine wrapper derived from the required
`tk_r_em` inference behavior, rather than depending on the full upstream package
at runtime.

The first release includes only the four required ONNX models:

- `sfr_hrstem`
- `sfr_lrstem`
- `sfr_hrsem`
- `sfr_lrsem`

The full `tk_r_em` Streamlit app, tutorials, sample datasets, and TEM models are
not part of the runtime app.

Because `tk_r_em` is GPL-3.0-only, Denoiser must keep the relevant license and
attribution notices with the source and release package.

The four required ONNX model files are tracked in this repository so that a
developer can clone the repo and build the release without a separate model
download step.

## Packaging workflow

The intended build flow is:

1. Developer clones/downloads this repository from GitHub on a Windows machine.
2. Developer installs dependencies with standard `pip install` commands.
3. Developer runs the Windows build script.
4. The build script creates a folder-style release containing `Denoiser.exe`,
   dependencies, licenses, and bundled model files.
5. FA engineers receive only the release folder and run `Denoiser.exe`.

End users do not need Python, `uv`, or `pip`.

## Repository layout

```text
Denoiser/
  pyproject.toml
  uv.lock
  requirements.txt
  README.md
  CONTEXT.md
  licenses/
    THIRD_PARTY_NOTICES.md
    tk_r_em_LICENSE.txt
  models/
    sfr_hrsem.onnx
    sfr_hrstem.onnx
    sfr_lrsem.onnx
    sfr_lrstem.onnx
  scripts/
    build_windows.ps1
  src/
    denoiser/
      __init__.py
      __main__.py
      app.py
      engine.py
      image_io.py
      models.py
      workflow.py
      ui/
        __init__.py
        compare_view.py
        main_window.py
  tests/
    test_engine.py
    test_image_io.py
    test_single_ui.py
    test_single_workflow.py
```

## Denoising modes

Only SEM and STEM modes are included in the first release. TEM is intentionally
excluded.

| UI label | tk_r_em model tag | Output folder     |
| -------- | ----------------- | ----------------- |
| `HRSTEM` | `sfr_hrstem`      | `denoised_HRSTEM` |
| `LRSTEM` | `sfr_lrstem`      | `denoised_LRSTEM` |
| `HRSEM`  | `sfr_hrsem`       | `denoised_HRSEM`  |
| `LRSEM`  | `sfr_lrsem`       | `denoised_LRSEM`  |

The UI shows these four modes as buttons, not as a dropdown.

## Workflow

The app has two modes, switched by buttons:

- `Single`
  - Open one image.
  - Select one denoising mode.
  - Click `Restore`.
  - The result is saved automatically.
  - The right side shows a fit-to-window before/after slider.
- `Batch`
  - Select one folder with `Add Folder`.
  - Only files in the selected folder are scanned; subfolders are not scanned.
  - Select one denoising mode.
  - Click `Start Batch`.
  - The right side shows progress and a scrollable per-file status list.

Layout:

- Left side: controls, file/folder selection, mode buttons, progress/status.
- Right side:
  - Single mode: raw image before processing, then before/after comparison.
  - Batch mode: progress/status only; no image preview.

## Image comparison behavior

- The preview always fits the full image into the available right-side area.
- No zoom, pan, crop, rotate, brightness, contrast, histogram, or image-editing
  tools are included in the first release.
- The before/after slider starts at 50%.
- Dragging the divider moves the comparison position.
- Clicking anywhere on the image jumps the slider to that position.
- Preview display normalization is allowed only for screen display. It must not
  affect saved output files.

## Input and output formats

First release input formats:

- `.tif`
- `.tiff`
- `.png`
- `.jpg`
- `.jpeg`
- `.dm3`
- `.dm4`

Formats intentionally excluded from the first release:

- `.ser`
- `.emd`
- `.bmp`
- `.mrc`
- `.raw`

Output rules:

| Input            | Output              |
| ---------------- | ------------------- |
| `.tif` / `.tiff` | Same extension      |
| `.png`           | `.png`              |
| `.jpg` / `.jpeg` | `.tif`              |
| `.dm3` / `.dm4`  | 32-bit float `.tif` |

For normal image formats, output should preserve the original bit depth where
possible. Model processing can use `float32` internally, but saved output must
not use automatic contrast stretching, histogram equalization, or min/max
rescaling. If model output exceeds the original image's actual value range, it
is clipped to the original min/max before saving.

RGB/RGBA inputs are accepted but converted to grayscale for model processing.
Alpha channels are not preserved.

Metadata should be preserved where safely possible. For formats that cannot be
written back safely, especially `.dm3` and `.dm4`, output is written as TIFF and
available metadata should be carried into TIFF metadata or an adjacent sidecar
only if this can be done safely.

The MVS metadata policy is conservative: preserve safe standard metadata where
possible, but never risk corrupting the output image to force metadata
round-tripping. Full `.dm3` / `.dm4` metadata parity is not a first-release
requirement.

Multi-page TIFF and stack-like data are rejected in the first release. Only one
single 2D image is supported per input file.

## Saving behavior

Single and Batch use the same saving concept:

- Output is written into a mode-specific subfolder next to the original image.
- Output filename stays the same, except when the output format changes.
- Existing files are overwritten.
- Original raw files are not copied into the output folder.

Examples:

- `D:\caseA\wafer01.tif` with `HRSTEM` ->
  `D:\caseA\denoised_HRSTEM\wafer01.tif`
- `D:\caseA\wafer01.jpg` with `HRSEM` ->
  `D:\caseA\denoised_HRSEM\wafer01.tif`

If output filenames collide, the later output overwrites the earlier output.
The UI should make overwrite behavior clear.

The app must reject inputs located inside any `denoised_*` folder to avoid
accidentally denoising already processed output.

## Processing behavior

The app should automatically choose inference strategy:

- Longest image side `<= 1536 px`: whole-image inference
- Longest image side `> 1536 px`: patch-based inference
- Patch-based settings for Windows CPU laptops:
  - `patch_size=512`
  - `stride=256`
  - `batch_size=2`

Large images are not blocked, but the UI should warn that processing may take
several minutes.

Cancellation:

- Single mode: no cancel button; controls are disabled while processing.
- Batch mode: cancel is supported between files. The current file finishes,
  then the batch stops.

## Batch behavior

- Batch mode only supports `Add Folder`.
- The selected folder is scanned non-recursively.
- Unsupported files are skipped and shown in the on-screen status list.
- No CSV log is produced in the first release.
- If the selected folder name starts with `denoised_`, batch processing is
  blocked.

## Design direction

The UI should follow the Apple-style design reference at:

`/Users/lesterc/Project/design-md/apple/DESIGN.md`

Practical interpretation for this desktop tool:

- Clean light UI.
- Minimal chrome.
- Blue as the main action color.
- Rounded controls where appropriate.
- Avoid decorative effects that distract from image inspection.

## Known constraints and trade-offs

- `tk_r_em` is licensed under GPL-3.0-only, so the first target is internal
  company use.
- The app uses a local minimal engine wrapper instead of the full upstream
  `tk_r_em` package to keep the desktop release smaller and easier to control.
- `tk_r_em` works on 2D grayscale EM-style images. The first release does not
  support stacks, multi-page TIFF, 3D volume, or 4D STEM data.
- Some microscope-native formats are read-only in the available IO libraries,
  so `.dm3` and `.dm4` are exported as TIFF.
- CPU-only inference is slower than GPU inference but is simpler and more
  reliable for the first Windows laptop release.
- No image adjustment tools are included, to avoid changing engineering image
  interpretation.

## Test data strategy

No real company FA image data is available on the development machine. First
release validation uses synthetic images and any safe upstream sample data that
can be used without exposing company data. Real FA image regression cases should
be added later when representative data is available.
