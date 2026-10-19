"""Model-agnostic transcript types."""

from __future__ import annotations

from dataclasses import dataclass

Sentence = list["Word"]


@dataclass
class Token:
    """A sub-word unit from the model. A leading space marks the start of a new word."""

    text: str
    start: float
    end: float
    confidence: float | None = None


@dataclass
class Word:
    text: str
    start: float
    end: float
    confidence: float | None = None


def tokens_to_words(sentences: list[list[Token]], offset: float = 0.0) -> list[Sentence]:
    """Merge sub-word tokens into words and shift them by `offset` seconds."""
    result: list[Sentence] = []
    for tokens in sentences:
        words: Sentence = []
        for tok in tokens:
            start, end = tok.start + offset, tok.end + offset
            if words and not tok.text.startswith(" "):
                last = words[-1]
                last.text += tok.text
                last.end = max(last.end, end)
                if tok.confidence is not None and last.confidence is not None:
                    last.confidence = min(last.confidence, tok.confidence)
            elif text := tok.text.strip():
                words.append(Word(text, start, end, tok.confidence))
        if words:
            result.append(words)
    return result


def join_words(words: list[Word]) -> str:
    return " ".join(w.text for w in words)
