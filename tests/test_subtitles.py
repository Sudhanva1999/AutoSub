from autosub.config import CueRules
from autosub.subtitles import Cue, build_cues, to_srt, to_vtt, wrap
from autosub.transcript import Word


def words(*specs: tuple[str, float, float]) -> list[Word]:
    return [Word(text, start, end) for text, start, end in specs]


def test_wrap_splits_near_middle():
    assert wrap("short", 42) == "short"
    text = "this line is definitely longer than forty two characters"
    first, second = wrap(text, 42).split("\n")
    assert abs(len(first) - len(second)) < 10


def test_long_pause_starts_new_cue():
    cues = build_cues([words(("Hi", 0.0, 0.3), ("there", 2.0, 2.4))])
    assert [c.text for c in cues] == ["Hi", "there"]


def test_cue_respects_max_characters():
    rules = CueRules(max_line_chars=10, max_lines=1)
    sentence = words(*[(f"word{i}", i * 0.3, i * 0.3 + 0.2) for i in range(6)])
    assert all(len(c.text.replace("\n", " ")) <= 10 for c in build_cues([sentence], rules))


def test_short_cue_is_extended_without_overlapping_next():
    rules = CueRules()
    cues = build_cues([words(("A", 0.0, 0.1)), words(("B", 0.5, 0.9))], rules)
    assert cues[0].end == 0.5 - rules.min_gap_seconds
    assert cues[1].end - cues[1].start >= rules.min_cue_seconds


def test_srt_and_vtt_format():
    cues = [Cue(1.5, 3.25, "Hello"), Cue(3661.0, 3662.0, "Later")]
    assert to_srt(cues) == "1\n00:00:01,500 --> 00:00:03,250\nHello\n\n2\n01:01:01,000 --> 01:01:02,000\nLater\n"
    assert to_vtt(cues).startswith("WEBVTT\n\n00:00:01.500 --> 00:00:03.250\nHello\n")
