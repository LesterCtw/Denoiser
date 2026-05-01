$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
if ($pythonVersion -ne "3.12.8") {
  throw "Windows release build requires Python 3.12.8. Found Python $pythonVersion."
}

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name Denoiser `
  --paths src `
  --add-data "models;models" `
  --add-data "licenses;licenses" `
  src\denoiser\app.py

Write-Host "Build finished: $repoRoot\dist\Denoiser\Denoiser.exe"
