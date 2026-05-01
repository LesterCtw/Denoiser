$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
if ($pythonVersion -ne "3.12.8") {
  throw "Windows release build requires Python 3.12.8. Found Python $pythonVersion."
}

$iconPath = Join-Path $repoRoot "assets\icons\denoiser_icon.ico"
if (-not (Test-Path $iconPath)) {
  throw "Windows release build requires app icon at $iconPath."
}

python -m pip install --upgrade pip
python -m pip install "numpy>=1.26"
python -m pip install "onnxruntime>=1.21"
python -m pip install "Pillow>=10"
python -m pip install "PySide6>=6.7"
python -m pip install "rosettasciio>=0.13"
python -m pip install "tifffile>=2024.8.10"
python -m pip install "pyinstaller>=6.10"
python -m pip install -e . --no-deps

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name Denoiser `
  --icon "$iconPath" `
  --add-data "assets;assets" `
  --paths src `
  --add-data "models;models" `
  --add-data "licenses;licenses" `
  src\denoiser\app.py

Write-Host "Build finished: $repoRoot\dist\Denoiser\Denoiser.exe"
