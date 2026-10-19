from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from autosub.transcript import Token


class FakeBackend:
    model_id = "fake/model"
    label = "Fake"

    def __init__(self) -> None:
        self.calls = 0

    def transcribe(self, wav: Path) -> list[list[Token]]:
        self.calls += 1
        return [[Token(" Hello", 0.2, 0.5), Token(" world", 0.5, 0.8), Token(".", 0.8, 0.9)]]


@pytest.fixture
def fake_backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def make_video(tmp_path: Path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")

    def _make(name: str = "Show - S01E01.mkv", folder: Path | None = None) -> Path:
        folder = folder or tmp_path / "videos"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=64x64:d=1",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1",
                "-shortest",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(path),
            ],
            check=True,
        )
        return path

    return _make
