"""onnx-asr on ONNX Runtime (CUDA when available, otherwise CPU) with Silero VAD segmentation."""

from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from autosub.config import MODELS_DIR
from autosub.transcript import Token

MODEL_ID = "istupakov/parakeet-tdt-0.6b-v2-onnx"
MODEL_NAME = "nemo-parakeet-tdt-0.6b-v2"
MODEL_DIR = MODELS_DIR / "parakeet-tdt-0.6b-v2-onnx"
MODEL_FILES = [
    "config.json",
    "vocab.txt",
    "nemo128.onnx",
    "encoder-model.onnx",
    "encoder-model.onnx.data",
    "decoder_joint-model.onnx",
]
VAD_MAX_SPEECH_SECONDS = 30.0
SENTENCE_END = (".", "?", "!")


class Segment(Protocol):
    start: float
    end: float
    tokens: list[str] | None
    timestamps: list[float] | None
    logprobs: list[float] | None


def segments_to_sentences(segments: Iterable[Segment]) -> list[list[Token]]:
    """Convert VAD segments (token start times relative to the segment) into absolute-timed sentences."""
    sentences: list[list[Token]] = []
    for seg in segments:
        texts, offsets = seg.tokens or [], seg.timestamps or []
        starts = [seg.start + t for t in offsets]
        ends = [*starts[1:], seg.end]
        current: list[Token] = []
        for i, text in enumerate(texts):
            confidence = math.exp(seg.logprobs[i]) if seg.logprobs else None
            current.append(Token(text, starts[i], max(ends[i], starts[i]), confidence))
            if text.rstrip().endswith(SENTENCE_END):
                sentences.append(current)
                current = []
        if current:
            sentences.append(current)
    return sentences


def _providers() -> list[str]:
    import onnxruntime as ort

    if hasattr(ort, "preload_dlls"):
        try:
            ort.preload_dlls()
        except Exception:
            pass
    available = ort.get_available_providers()
    return [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available]


class OnnxBackend:
    model_id = MODEL_ID

    def __init__(self) -> None:
        import onnx_asr
        from huggingface_hub import snapshot_download

        providers = _providers()
        self.label = "ONNX Runtime (CUDA GPU)" if providers[0].startswith("CUDA") else "ONNX Runtime (CPU)"

        # ONNX Runtime rejects the HF cache's symlinked external-data file, so use a plain folder.
        snapshot_download(MODEL_ID, local_dir=MODEL_DIR, allow_patterns=MODEL_FILES)
        model = onnx_asr.load_model(MODEL_NAME, MODEL_DIR, providers=providers)
        vad = onnx_asr.load_vad("silero", providers=["CPUExecutionProvider"])
        self._asr = model.with_vad(vad, max_speech_duration_s=VAD_MAX_SPEECH_SECONDS).with_timestamps()

    def transcribe(self, wav: Path) -> list[list[Token]]:
        return segments_to_sentences(self._asr.recognize(str(wav)))
