$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

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
