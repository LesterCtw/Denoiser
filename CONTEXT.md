# Denoiser Context

## Project status

Denoiser has a first Minimum Viable Solution (MVS) scope. It will be a simple
Windows desktop app for FA engineers to restore 2D grayscale SEM/STEM images
using `tk_r_em` ONNX models.

The repo now has a Python project skeleton, bundled ONNX models, third-party
license notices, a tested image I/O boundary for first-release output naming
and dtype/range preservation rules, a minimal ONNX inference wrapper with
whole-image and patch-based restore paths, a working Single-image restore flow,
the first Batch folder restore flow with cancellation and per-file failure
isolation, and a Single mode before/after compare view.

## Glossary

- **Denoiser**: The project and product name.
- **FA engineer**: Failure analysis engineer using SEM/STEM images for
  inspection and analysis.
- **HRSTEM / LRSTEM / HRSEM / LRSEM**: The four supported first-release
  denoising modes.
- **MVS**: Minimum Viable Solution; the smallest useful first implementation.
- **Batch restore run**: A single Batch mode execution over the selected folder.
  It should preserve per-file progress so the UI can show each restored,
  skipped, failed, or cancelled file as the run advances.
- **Bundled model inventory**: The first-release ONNX model set that must ship
  with Denoiser, including the mapping from each denoising mode to its required
  model filename and the missing-model checks used before release or runtime
  inference.

## Current assumptions

- This is a single-context repo.
- Issues are tracked in GitHub Issues for `LesterCtw/Denoiser`.
- Initial architectural decisions are recorded under `docs/adr/`.
- First release targets Windows 10/11 laptops with CPU inference only.
- The frontend will use PySide6.
- The app will commit and bundle four `tk_r_em` ONNX models and run offline.
- The app will use a minimal local engine wrapper instead of the full upstream
  `tk_r_em` package at runtime.
- Development can use `uv`, but Windows release building must work with
  standard `pip install` commands.
- UI text will be English.
- README.md is the source of truth for the current product scope.
- MVS metadata preservation is conservative: keep safe standard metadata where
  possible, but do not risk corrupting image output to force full metadata
  round-tripping.
- Multi-page TIFF and stack-like inputs are rejected in the first release.
- No company FA image data is available for development; validation starts with
  synthetic data and safe upstream samples.

## Open questions

- Real FA image regression test set, once representative non-sensitive data is
  available.
