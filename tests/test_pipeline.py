from pathlib import Path

import pytest

from autosub.media import MediaError
from autosub.pipeline import Outcome, episode_dir, plex_dir, run_episode, srt_name


def test_run_episode_writes_outputs_then_skips(tmp_path: Path, make_video, fake_backend):
    video = make_video()
    output = tmp_path / "out"
    run = lambda **kw: run_episode(lambda: fake_backend, video, output, model_id=fake_backend.model_id, **kw)  # noqa: E731

    assert run() is Outcome.DONE
    files = {p.name for p in episode_dir(output, video).iterdir()}
    assert {srt_name(video), "Show - S01E01.en.vtt", "Show - S01E01.en.txt", "state.json"} <= files
    assert "Hello world." in (plex_dir(output) / srt_name(video)).read_text()

    assert run() is Outcome.SKIPPED
    assert run(force=True) is Outcome.DONE
    assert fake_backend.calls == 2


def test_sidecar_copies_srt_next_to_video(tmp_path: Path, make_video, fake_backend):
    video = make_video()
    run_episode(lambda: fake_backend, video, tmp_path / "out", model_id="m", sidecar=True)
    assert (video.parent / srt_name(video)).exists()


def test_unreadable_video_raises_media_error(tmp_path: Path, make_video, fake_backend):
    make_video()  # skips the test when ffmpeg is unavailable
    broken = tmp_path / "broken.mkv"
    broken.write_text("not a video")
    with pytest.raises(MediaError, match="couldn't read this file"):
        run_episode(lambda: fake_backend, broken, tmp_path / "out", model_id="m")
