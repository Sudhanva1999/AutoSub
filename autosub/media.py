"""FFmpeg helpers and video discovery."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from autosub.config import SAMPLE_RATE, VIDEO_EXTS

REQUIRED_TOOLS = ("ffmpeg", "ffprobe")


class MediaError(RuntimeError):
    """A video could not be read or decoded."""


def missing_tools() -> list[str]:
    return [tool for tool in REQUIRED_TOOLS if not shutil.which(tool)]


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS and not path.name.startswith(".")


def find_videos(folder: Path) -> list[Path]:
    return sorted((p for p in folder.iterdir() if p.is_file() and is_video(p)), key=lambda p: p.name.lower())


def _run(cmd: list[str], video: Path) -> str:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as exc:
        lines = (exc.stderr or "").strip().splitlines()
        reason = lines[-1].replace(f"{video}: ", "") if lines else f"exit code {exc.returncode}"
        raise MediaError(f"{cmd[0]} couldn't read this file: {reason}") from exc


def probe_audio_offset(video: Path) -> float:
    """Seconds between the start of the playback timeline and the first audio sample."""
    out = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=start_time:stream=codec_type,start_time",
            "-of",
            "json",
            str(video),
        ],
        video,
    )
    info = json.loads(out)
    audio = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio:
        raise MediaError("no audio stream found")
    audio_start = float(audio[0].get("start_time") or 0.0)
    container_start = float(info.get("format", {}).get("start_time") or 0.0)
    return audio_start - container_start


def extract_audio(video: Path, wav: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(wav),
        ],
        video,
    )
