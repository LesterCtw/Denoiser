# ADR 0002: Bundle ONNX models for offline CPU runtime

## Status

Accepted

## Context

Denoiser must run offline on Windows 10/11 laptops. The first release supports
four denoising modes:

- HRSTEM
- LRSTEM
- HRSEM
- LRSEM

Each mode maps to one required `tk_r_em` ONNX model file. End users should not
need to download models separately or configure model paths.

## Decision

Commit and bundle the four required ONNX model files in the repository and
release package. The runtime uses CPU inference only.

## Consequences

Positive:

- Developer clones and Windows release builds have the required model files by
  default.
- End users can run Denoiser offline.
- Missing-model checks can be deterministic and local.

Trade-offs:

- The repository and release package are larger.
- Model updates become repository changes, not external downloads.
- The first release is intentionally limited to the four SEM/STEM modes and
  excludes TEM models.

## Alternatives Considered

- Download models at runtime: rejected because offline use is required.
- Ask users to choose model files manually: rejected because it adds setup risk
  for the MVS.
- Include all upstream `tk_r_em` models: rejected because the first release only
  needs four SEM/STEM modes.
