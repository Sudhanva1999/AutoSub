from types import SimpleNamespace

import pytest

from autosub.backends.onnx import segments_to_sentences
from autosub.transcript import Token, tokens_to_words


def test_tokens_merge_into_words_with_offset():
    tokens = [Token(" He", 0.0, 0.1, 0.9), Token("llo", 0.1, 0.3, 0.6), Token(" world", 0.4, 0.7), Token(".", 0.7, 0.8)]
    [sentence] = tokens_to_words([tokens], offset=10.0)
    assert [w.text for w in sentence] == ["Hello", "world."]
    assert sentence[0].start == 10.0
    assert sentence[0].end == pytest.approx(10.3)
    assert sentence[0].confidence == 0.6


def test_empty_sentences_are_dropped():
    assert tokens_to_words([[Token(" ", 0, 0)], []]) == []


def test_onnx_segments_split_into_sentences_with_absolute_times():
    seg = SimpleNamespace(
        start=5.0,
        end=6.0,
        tokens=[" Hi", ".", " Bye", "."],
        timestamps=[0.0, 0.2, 0.4, 0.8],
        logprobs=[0.0, 0.0, 0.0, 0.0],
    )
    sentences = segments_to_sentences([seg])
    assert [[t.text for t in s] for s in sentences] == [[" Hi", "."], [" Bye", "."]]
    assert sentences[0][0].start == 5.0
    assert sentences[-1][-1].end == 6.0
    assert sentences[0][0].confidence == 1.0
