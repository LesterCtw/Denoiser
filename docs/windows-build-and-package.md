# Windows Build and Package Guide

這份文件說明如何在 Windows 10/11 使用 Python 3.12.8 建置與打包 Denoiser。

## Goal

產生一個 folder-style release：

```text
dist\Denoiser\
  Denoiser.exe
  ...
  assets\
  models\
  licenses\
```

FA engineer 只需要收到整個 `dist\Denoiser` folder，不需要安裝 Python、`uv`、`pip`，
也不需要 internet connection。

## Build Machine Requirements

- Windows 10 或 Windows 11。
- Python 3.12.8 64-bit。
- PowerShell。
- Internet connection，用於安裝 build dependencies。
- Fresh checkout of this repository。
- App icon exists at `assets\icons\denoiser_icon.ico`。

確認 Python version：

```powershell
py -3.12 --version
```

Expected:

```text
Python 3.12.8
```

## Clean Checkout

Clone repository：

```powershell
git clone https://github.com/LesterCtw/Denoiser.git
cd Denoiser
```

確認 repository 沒有 local artifacts：

```powershell
git status --short
```

Expected: no output.

The clean source checkout should not contain local-only folders such as:

- `.venv`
- `build`
- `dist`
- `release`
- `sample_inputs`
- `node_modules`
- `.pytest_cache`

The clean source checkout should contain the app icon:

```powershell
Test-Path .\assets\icons\denoiser_icon.ico
```

Expected:

```text
True
```

## Build Setup

Create and activate a virtual environment with Python 3.12.8:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

Expected:

```text
Python 3.12.8
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Run Tests

```powershell
python -m pytest
```

Expected:

```text
74 passed
```

The exact runtime may vary by machine. The important result is that all tests pass.
The exact test count may change as coverage grows. If it differs, confirm that every
test passed.

## Build the Windows App

From the repository root, run:

```powershell
.\scripts\build_windows.ps1
```

Expected output:

```text
Build finished: <repo>\dist\Denoiser\Denoiser.exe
```

## Inspect the Build Output

Confirm these files exist:

```powershell
Test-Path .\dist\Denoiser\Denoiser.exe
Test-Path .\dist\Denoiser\assets\icons\denoiser_icon.ico
Test-Path .\dist\Denoiser\models\sfr_hrstem.onnx
Test-Path .\dist\Denoiser\models\sfr_lrstem.onnx
Test-Path .\dist\Denoiser\models\sfr_hrsem.onnx
Test-Path .\dist\Denoiser\models\sfr_lrsem.onnx
Test-Path .\dist\Denoiser\licenses\THIRD_PARTY_NOTICES.md
Test-Path .\dist\Denoiser\licenses\tk_r_em_LICENSE.txt
```

Each command should print:

```text
True
```

## Package the Release Folder

Create a distributable zip file:

```powershell
New-Item -ItemType Directory -Force .\release
Compress-Archive -Path .\dist\Denoiser -DestinationPath .\release\Denoiser-windows-python-3.12.8.zip -Force
```

The zip should contain the `Denoiser` folder, including `Denoiser.exe`, app icon asset,
model files, runtime dependencies, and license notices.

Do not commit `dist`, `build`, `release`, `.venv`, or generated zip files. They are local
build artifacts.

## Smoke Test the Package

1. Copy `release\Denoiser-windows-python-3.12.8.zip` to a clean Windows 10/11 machine or folder.
2. Extract the zip.
3. Run `Denoiser\Denoiser.exe`.
4. Use Single mode to restore a safe, non-sensitive 2D grayscale image.
5. Confirm output appears beside the input under the selected `denoised_MODE` folder.

For the full release checklist, use `docs/windows-release-verification.md`.
