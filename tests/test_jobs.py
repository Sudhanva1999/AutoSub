from pathlib import Path

import pytest

from autosub.backends import BackendLoader, BackendSpec
from autosub.pipeline import Outcome
from autosub.web.jobs import EpisodeStatus, JobQueue, JobStatus, JobStore


@pytest.fixture
def season(tmp_path: Path) -> Path:
    folder = tmp_path / "Season 1"
    folder.mkdir()
    for i in (1, 2, 3):
        (folder / f"Show - S01E0{i}.mkv").write_bytes(b"")
    return folder


def make_queue(tmp_path: Path, runner) -> JobQueue:
    loader = BackendLoader(BackendSpec("fake", "fake/model", lambda: None))
    return JobQueue(loader, JobStore(tmp_path / "queue.json"), runner=runner)


def test_job_runs_all_episodes(tmp_path, season):
    queue = make_queue(tmp_path, lambda *a, **k: Outcome.DONE)
    job = queue.add("", str(season), str(tmp_path / "out"))
    assert job.name == "Season 1"
    assert queue.run_next()
    assert job.status is JobStatus.DONE
    assert all(ep.status is EpisodeStatus.DONE for ep in job.episodes)
    assert not queue.run_next()


def test_failed_episode_marks_job_failed_and_retry_reruns_only_failures(tmp_path, season):
    calls = []

    def runner(_loader, video, *_a, **_k):
        calls.append(video.name)
        if video.name.endswith("E02.mkv") and calls.count(video.name) == 1:
            raise RuntimeError("boom")
        return Outcome.DONE

    queue = make_queue(tmp_path, runner)
    job = queue.add("S1", str(season), str(tmp_path / "out"))
    queue.run_next()
    assert job.status is JobStatus.FAILED
    assert job.episodes[1].error == "boom"

    queue.act(job.id, "retry")
    queue.run_next()
    assert job.status is JobStatus.DONE
    assert len(calls) == 4


def test_stop_and_reorder(tmp_path, season):
    queue = make_queue(tmp_path, lambda *a, **k: Outcome.SKIPPED)
    first = queue.add("A", str(season), str(tmp_path / "a"))
    second = queue.add("B", str(season), str(tmp_path / "b"))
    queue.act(second.id, "up")
    assert [j.name for j in queue.jobs] == ["B", "A"]
    queue.act(first.id, "stop")
    assert first.status is JobStatus.STOPPED
    with pytest.raises(ValueError):
        queue.act(first.id, "explode")


def test_queue_persists_and_resets_interrupted_work(tmp_path, season):
    queue = make_queue(tmp_path, lambda *a, **k: Outcome.DONE)
    job = queue.add("S1", str(season), str(tmp_path / "out"))
    job.status = JobStatus.RUNNING
    job.episodes[0].status = EpisodeStatus.RUNNING
    queue.store.save(queue.jobs)

    [restored] = JobStore(tmp_path / "queue.json").load()
    assert restored.status is JobStatus.QUEUED
    assert restored.episodes[0].status is EpisodeStatus.PENDING


def test_add_rejects_bad_input(tmp_path):
    queue = make_queue(tmp_path, lambda *a, **k: Outcome.DONE)
    with pytest.raises(ValueError, match="does not exist"):
        queue.add("", str(tmp_path / "missing"), str(tmp_path / "out"))
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="No videos"):
        queue.add("", str(tmp_path / "empty"), str(tmp_path / "out"))
