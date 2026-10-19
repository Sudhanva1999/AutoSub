"""parakeet-mlx on the Apple Silicon GPU."""

from __future__ import annotations

from pathlib import Path

from autosub.transcript import Token

MODEL_ID = "mlx-community/parakeet-tdt-0.6b-v2"
CHUNK_SECONDS = 120.0
OVERLAP_SECONDS = 15.0


class MlxBackend:
    model_id = MODEL_ID
    label = "MLX (Apple GPU)"

    def __init__(self) -> None:
        from parakeet_mlx import from_pretrained

        self._model = from_pretrained(MODEL_ID)

    def transcribe(self, wav: Path) -> list[list[Token]]:
        result = self._model.transcribe(str(wav), chunk_duration=CHUNK_SECONDS, overlap_duration=OVERLAP_SECONDS)
        return [
            [Token(t.text, t.start, t.end, getattr(t, "confidence", None)) for t in sentence.tokens]
            for sentence in result.sentences
        ]
