from __future__ import annotations

from pathlib import Path
from typing import Protocol

from autosub.transcript import Token


class Backend(Protocol):
    """A speech-to-text engine. `transcribe` returns sentences of tokens timed from the start of the audio."""

    model_id: str
    label: str

    def transcribe(self, wav: Path) -> list[list[Token]]: ...
