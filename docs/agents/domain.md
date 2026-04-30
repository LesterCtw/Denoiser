# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Layout

This repo uses a single-context layout:

- `CONTEXT.md` at the repo root
- `docs/adr/` for Architecture Decision Records

## Before exploring, read these

- **`CONTEXT.md`** at the repo root.
- **`docs/adr/`** for ADRs that touch the area you're about to work in.

If any of these files don't exist or don't contain relevant information yet, proceed silently. The files can be expanded as the project becomes clearer.

## Use the glossary's vocabulary

When your output names a domain concept in an issue title, refactor proposal, hypothesis, or test name, use the term as defined in `CONTEXT.md`.

If the concept you need is not in the glossary yet, either reconsider the wording or note the gap for future documentation.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding it.
