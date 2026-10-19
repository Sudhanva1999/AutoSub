"""Per-episode processing shared by the CLI and the web UI."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from autosub.backends import Backend
from autosub.config import PIPELINE_VERSION, PLEX_DIR_NAME, SUBTITLE_LANG
from autosub.media import extract_audio, probe_audio_offset
from autosub.subtitles import build_cues, to_srt, to_vtt
from autosub.transcript import join_words, tokens_to_words

STATE_FILE = "state.json"


class Outcome(str, Enum):
    DONE = "done"
    SKIPPED = "skipped"


def episode_dir(output: Path, video: Path) -> Path:
    return output / video.name


def plex_dir(output: Path) -> Path:
    return output / PLEX_DIR_NAME


def srt_name(video: Path) -> str:
    return f"{video.stem}.{SUBTITLE_LANG}.srt"


def fingerprint(video: Path, model_id: str) -> dict:
    st = video.stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "model": model_id, "pipeline_version": PIPELINE_VERSION}


def is_done(video: Path, out_dir: Path, model_id: str) -> bool:
    try:
        state = json.loads((out_dir / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return state.get("fingerprint") == fingerprint(video, model_id)


def transcribe_video(backend: Backend, video: Path, out_dir: Path) -> None:
    offset = probe_audio_offset(video)
    with tempfile.TemporaryDirectory(prefix="autosub-") as tmp:
        wav = Path(tmp) / "audio.wav"
        extract_audio(video, wav)
        tokens = backend.transcribe(wav)

    sentences = tokens_to_words(tokens, offset)
    cues = build_cues(sentences)
    stem, lang = video.stem, SUBTITLE_LANG

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.{lang}.srt").write_text(to_srt(cues), encoding="utf-8")
    (out_dir / f"{stem}.{lang}.vtt").write_text(to_vtt(cues), encoding="utf-8")
    (out_dir / f"{stem}.{lang}.txt").write_text("".join(join_words(s) + "\n" for s in sentences), encoding="utf-8")
    words = {
        "source": video.name,
        "model": backend.model_id,
        "audio_offset_seconds": offset,
        "sentences": [[asdict(w) for w in s] for s in sentences],
    }
    (out_dir / f"{stem}.words.json").write_text(json.dumps(words, indent=2, ensure_ascii=False), encoding="utf-8")
    state = {"fingerprint": fingerprint(video, backend.model_id), "completed_at": time.time()}
    (out_dir / STATE_FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")


def publish_srt(video: Path, output: Path, *, sidecar: bool = False) -> None:
    """Copy the SRT into the flat Plex folder and, optionally, next to the video."""
    srt = episode_dir(output, video) / srt_name(video)
    if not srt.exists():
        return
    targets = [plex_dir(output)] + ([video.parent] if sidecar else [])
    for folder in targets:
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(srt, folder / srt.name)


def run_episode(
    get_backend: Callable[[], Backend],
    video: Path,
    output: Path,
    *,
    model_id: str,
    force: bool = False,
    sidecar: bool = False,
) -> Outcome:
    """Transcribe one video unless it's already done. The backend is only requested when needed."""
    if not force and is_done(video, episode_dir(output, video), model_id):
        outcome = Outcome.SKIPPED
    else:
        transcribe_video(get_backend(), video, episode_dir(output, video))
        outcome = Outcome.DONE
    publish_srt(video, output, sidecar=sidecar)
    return outcome
