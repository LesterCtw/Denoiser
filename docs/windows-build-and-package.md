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
- Source code from GitHub ZIP download, or a fresh `git clone` if `git` is available.
- App icon exists at `assets\icons\denoiser_icon.ico`。

確認 Python version：

```powershell
py -3.12 --version
```

Expected:

```text
Python 3.12.8
```

## Get Source Code

### Company Environment Without Git

如果公司電腦不能使用 `git`，請用 GitHub 網頁下載 source ZIP：

1. 開啟 `https://github.com/LesterCtw/Denoiser`。
2. 點 `Code`。
3. 點 `Download ZIP`。
4. 解壓縮 ZIP。
5. 進入解壓縮後的資料夾，例如 `Denoiser-main`。

PowerShell example：

```powershell
cd path\to\Denoiser-main
```

GitHub ZIP 不會包含 `.git` folder，所以 `git status`、`git log` 這類 commands 不會
運作。這是正常狀況，不是 build failure。

請記錄 ZIP 來源，方便之後追蹤版本：

- GitHub branch 或 PR。
- ZIP filename。
- Download date。

### Optional Git Clone

如果你的環境可以使用 `git`，也可以 clone repository：

```powershell
git clone https://github.com/LesterCtw/Denoiser.git
cd Denoiser
```

確認 repository 沒有 local artifacts：

```powershell
git status --short
```

Expected: no output.

ZIP workflow 沒有 `.git` metadata，請跳過這個 `git status` check。

The clean source folder should not contain local-only folders such as:

- `.venv`
- `build`
- `dist`
- `release`
- `sample_inputs`
- `node_modules`
- `.pytest_cache`

The clean source folder should contain the app icon:

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

Upgrade `pip`:

```powershell
python -m pip install --upgrade pip
```

Install top-level dependencies one by one:

```powershell
python -m pip install "numpy>=1.26"
python -m pip install "onnxruntime>=1.21"
python -m pip install "Pillow>=10"
python -m pip install "PySide6>=6.7"
python -m pip install "rosettasciio>=0.13"
python -m pip install "tifffile>=2024.8.10"
python -m pip install "pyinstaller>=6.10"
python -m pip install "pytest>=8"
python -m pip install -e . --no-deps
```

為什麼逐一安裝：

- 如果公司網路或 proxy 導致安裝失敗，可以直接知道是哪個 package 失敗。
- `requirements.txt` 仍保留作為 dependency reference 和批次安裝 fallback。
- `python -m pip install -e . --no-deps` 會安裝本地 Denoiser package，但不再重複解析
  dependencies。

如果你想快速批次安裝，也可以使用：

```powershell
python -m pip install -r requirements.txt
python -m pip install "pytest>=8"
python -m pip install -e .
```

但如果批次安裝失敗，請回到上面的逐一安裝方式。

## Run Tests

```powershell
python -m pytest
```

Expected: all tests pass.

```text
77 passed
```

The exact runtime and test count may vary as coverage grows. The important result is
that every test passed and there are no failures or errors.

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
