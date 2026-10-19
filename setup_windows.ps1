# One-time setup for Windows: FFmpeg, uv, and a local Python env in .venv.
# Installs the ONNX Runtime backend (NVIDIA GPU if nvidia-smi is found, else CPU).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

if (-not (Have "ffmpeg")) {
    if (-not (Have "winget")) {
        Write-Error "FFmpeg not found and winget is unavailable. Install FFmpeg from https://www.gyan.dev/ffmpeg/builds/ and add its bin folder to PATH."
    }
    Write-Host "Installing FFmpeg ..."
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    Refresh-Path
}

if (-not (Have "uv")) {
    Write-Host "Installing uv ..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    Refresh-Path
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host "Creating Python environment in .venv ..."
uv venv --allow-existing --python 3.12 .venv
if ($LASTEXITCODE -ne 0) { exit 1 }

$py = ".venv\Scripts\python.exe"
if (Have "nvidia-smi") {
    Write-Host "NVIDIA GPU detected: installing the ONNX Runtime backend with CUDA."
    uv pip install --python $py -e ".[cuda]"
} else {
    Write-Host "Installing the ONNX Runtime backend (CPU)."
    uv pip install --python $py -e ".[cpu]"
}
if ($LASTEXITCODE -ne 0) { exit 1 }

New-Item -ItemType Directory -Force input, output | Out-Null

Write-Host ""
Write-Host "Setup complete. Start the UI with run_ui.bat (or run_batch.bat for the command line)."
