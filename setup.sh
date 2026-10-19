#!/usr/bin/env bash
# One-time setup for macOS and Linux: FFmpeg, uv, and a local Python env in .venv.
#   Apple Silicon Mac  -> parakeet-mlx (Apple GPU)
#   Linux / Intel Mac  -> onnx-asr on ONNX Runtime (NVIDIA GPU if nvidia-smi is found, else CPU)
set -euo pipefail
cd "$(dirname "$0")"

os="$(uname -s)"
arch="$(uname -m)"

if [[ "$os" == "Darwin" ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "error: Homebrew not found. Install it from https://brew.sh and re-run." >&2
    exit 1
  fi
  for pkg in ffmpeg uv; do
    if ! command -v "$pkg" >/dev/null 2>&1; then
      echo "Installing $pkg ..."
      brew install "$pkg"
    fi
  done
elif [[ "$os" == "Linux" ]]; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "error: FFmpeg not found. Install it with your package manager, then re-run:" >&2
    echo "  Debian/Ubuntu: sudo apt install ffmpeg" >&2
    echo "  Fedora:        sudo dnf install ffmpeg   (needs RPM Fusion)" >&2
    echo "  Arch:          sudo pacman -S ffmpeg" >&2
    exit 1
  fi
  if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
else
  echo "error: unsupported OS '$os'. On Windows, run setup_windows.bat instead." >&2
  exit 1
fi

echo "Creating Python environment in .venv ..."
uv venv --allow-existing --python 3.12 .venv

if [[ "$os" == "Darwin" && "$arch" == "arm64" ]]; then
  echo "Apple Silicon detected: installing the MLX backend."
  uv pip install --python .venv/bin/python -e ".[mlx]"
elif [[ "$os" == "Linux" ]] && command -v nvidia-smi >/dev/null 2>&1; then
  echo "NVIDIA GPU detected: installing the ONNX Runtime backend with CUDA."
  uv pip install --python .venv/bin/python -e ".[cuda]"
else
  echo "Installing the ONNX Runtime backend (CPU)."
  uv pip install --python .venv/bin/python -e ".[cpu]"
fi

mkdir -p input output
chmod +x run_batch.sh run_batch.command run_ui.sh run_ui.command

echo
echo "Setup complete. Start the UI with ./run_ui.sh (or ./run_batch.sh for the command line)."
