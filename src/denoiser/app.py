"""Application entry point."""

from __future__ import annotations

from denoiser.nicegui_shell import run_nicegui_native_window


def main() -> int:
    return run_nicegui_native_window()


if __name__ == "__main__":
    raise SystemExit(main())
