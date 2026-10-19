"""Turn timed words into subtitle cues and serialize them as SRT / WebVTT."""

from __future__ import annotations

from dataclasses import dataclass

from autosub.config import CueRules
from autosub.transcript import Sentence, Word, join_words


@dataclass
class Cue:
    start: float
    end: float
    text: str


def wrap(text: str, max_line_chars: int) -> str:
    """Split into two lines at the space closest to the middle."""
    if len(text) <= max_line_chars:
        return text
    spaces = [i for i, c in enumerate(text) if c == " "]
    if not spaces:
        return text
    mid = len(text) // 2
    cut = min(spaces, key=lambda i: abs(i - mid))
    return f"{text[:cut]}\n{text[cut + 1 :]}"


def _split_sentence(sentence: Sentence, rules: CueRules) -> list[list[Word]]:
    groups: list[list[Word]] = []
    current: list[Word] = []
    for word in sentence:
        if current and (
            len(join_words([*current, word])) > rules.max_cue_chars
            or word.end - current[0].start > rules.max_cue_seconds
            or word.start - current[-1].end > rules.pause_split_seconds
        ):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    return groups


def build_cues(sentences: list[Sentence], rules: CueRules | None = None) -> list[Cue]:
    rules = rules or CueRules()
    cues = [
        Cue(group[0].start, group[-1].end, join_words(group))
        for sentence in sentences
        for group in _split_sentence(sentence, rules)
    ]
    cues.sort(key=lambda c: c.start)
    for i, cue in enumerate(cues):
        cue.start = max(cue.start, 0.0)
        cue.end = max(cue.end, cue.start + rules.min_cue_seconds)
        if i + 1 < len(cues):
            limit = cues[i + 1].start - rules.min_gap_seconds
            if cue.end > limit:
                cue.end = max(limit, cue.start + 0.01)
        cue.text = wrap(cue.text, rules.max_line_chars)
    return cues


def _timestamp(seconds: float, sep: str) -> str:
    ms = round(max(seconds, 0.0) * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    return "\n".join(
        f"{i}\n{_timestamp(c.start, ',')} --> {_timestamp(c.end, ',')}\n{c.text}\n" for i, c in enumerate(cues, 1)
    )


def to_vtt(cues: list[Cue]) -> str:
    body = "\n".join(f"{_timestamp(c.start, '.')} --> {_timestamp(c.end, '.')}\n{c.text}\n" for c in cues)
    return f"WEBVTT\n\n{body}"
