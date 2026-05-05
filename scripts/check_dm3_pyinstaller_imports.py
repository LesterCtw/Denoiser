from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


REQUIRED_IMPORTS = [
    "rsciio.digitalmicrograph",
    "rsciio.digitalmicrograph._api",
    "rsciio.utils.file",
    "rsciio.utils._distributed",
    "dask.array",
    "box",
    "dateutil.parser",
    "pint",
    "yaml",
]

PYINSTALLER_HIDDEN_IMPORTS = [
    "rsciio.utils._distributed",
    "pint",
    "yaml",
]


PROBE_SOURCE = """
from importlib import import_module

from rsciio.digitalmicrograph import file_reader
from rsciio.utils.file import memmap_distributed

for module_name in {required_imports!r}:
    import_module(module_name)

print(f"file_reader={{file_reader.__module__}}.{{file_reader.__name__}}")
print(
    "memmap_distributed="
    f"{{memmap_distributed.__module__}}.{{memmap_distributed.__name__}}"
)
""".format(required_imports=REQUIRED_IMPORTS)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="denoiser-dm3-pyinstaller-") as temp_dir:
        temp_path = Path(temp_dir)
        probe_path = temp_path / "dm3_pyinstaller_probe.py"
        probe_path.write_text(PROBE_SOURCE, encoding="utf-8")

        dist_path = temp_path / "dist"
        build_path = temp_path / "build"

        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--console",
            "--name",
            "Dm3PyInstallerProbe",
            "--distpath",
            str(dist_path),
            "--workpath",
            str(build_path),
            "--specpath",
            str(temp_path),
            str(probe_path),
        ]
        for hidden_import in PYINSTALLER_HIDDEN_IMPORTS:
            command[-1:-1] = ["--hidden-import", hidden_import]
        subprocess.run(command, cwd=repo_root, check=True)

        executable = dist_path / "Dm3PyInstallerProbe" / executable_name()
        result = subprocess.run(
            [str(executable)],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(result.stdout, end="")
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                [str(executable)],
                output=result.stdout,
            )

    return 0


def executable_name() -> str:
    if os.name == "nt":
        return "Dm3PyInstallerProbe.exe"
    return "Dm3PyInstallerProbe"


if __name__ == "__main__":
    raise SystemExit(main())
