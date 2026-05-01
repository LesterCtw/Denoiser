# ADR 0003: Use a minimal local ONNX wrapper instead of upstream tk_r_em runtime

## Status

Accepted

## Context

Denoiser needs the required `tk_r_em` ONNX inference behavior, but the first
release is a small Windows desktop app. The upstream `tk_r_em` project includes
more than the Denoiser runtime needs, such as the Streamlit app, tutorials,
sample datasets, and model families outside the first-release SEM/STEM scope.

The app must package cleanly for Windows, run offline, and keep the runtime
surface small.

## Decision

Implement a minimal local ONNX inference wrapper for Denoiser instead of
depending on the full upstream `tk_r_em` package at runtime.

## Consequences

Positive:

- Keeps the runtime dependency surface smaller.
- Avoids packaging unused upstream app code into the Windows release.
- Makes the Denoiser engine behavior directly testable in this repository.
- Allows whole-image and patch-based restore paths to be tuned for the MVS.

Trade-offs:

- Denoiser must maintain the local wrapper and verify it stays compatible with
  the required model behavior.
- Useful upstream improvements do not arrive automatically.
- License and attribution obligations for `tk_r_em` still need to be preserved
  in source and release artifacts.

## Alternatives Considered

- Depend on the full upstream `tk_r_em` runtime package: rejected for the first
  release because it adds unnecessary runtime and packaging surface.
- Reimplement the model behavior without ONNX Runtime: rejected because ONNX
  Runtime is the proven inference path for the bundled models.
