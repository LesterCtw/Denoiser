# Codex Instruction

## Communication

- Use Traditional Chinese for all user-facing responses by default.
- English is allowed and preferred for technical terms, code, comments, and tool usage.
- Keep explanations simple, concrete, and easy to follow.
- When explaining code or technical decisions, include why the approach is used and what impact or trade-offs it introduces.
- Keep `README.md` up to date. It is the source of truth for current project status.

## Workflow

- First, clarify the actual requirement.
- Then, propose a Minimum Viable Solution (MVS).
- Only after that, consider adding complexity if needed.
- Clearly state known constraints, current assumptions, and unverified or unclear parts.
- If critical requirements or assumptions are unclear, ask for clarification instead of making decisions.
- Avoid adding features, abstractions, or flexibility that were not explicitly requested.
- If modifying existing code, make the smallest possible change that solves the problem.

## Python Development

- Prefer using `uv` for Python projects to manage dependencies, virtual environments, lockfiles, and command execution.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for `LesterCtw/Denoiser`. See `docs/agents/issue-tracker.md`.

### Triage labels

Triage uses the default five-label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This repo uses a single-context domain documentation layout. See `docs/agents/domain.md`.
