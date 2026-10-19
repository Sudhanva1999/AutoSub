"""Paths and tunable settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("AUTOSUB_HOME") or Path(__file__).resolve().parents[1])
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
MODELS_DIR = ROOT / "models"
QUEUE_FILE = ROOT / "ui_queue.json"

PLEX_DIR_NAME = "plex"
SUBTITLE_LANG = "en"
VIDEO_EXTS = frozenset({".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"})
PIPELINE_VERSION = 1
SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class CueRules:
    max_line_chars: int = 42
    max_lines: int = 2
    max_cue_seconds: float = 7.0
    min_cue_seconds: float = 0.8
    pause_split_seconds: float = 0.6
    min_gap_seconds: float = 0.05

    @property
    def max_cue_chars(self) -> int:
        return self.max_line_chars * self.max_lines
