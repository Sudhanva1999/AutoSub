"""Persistent queue of season jobs, processed one at a time by a background worker."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path

from autosub.backends import BackendLoader
from autosub.media import MediaError, find_videos
from autosub.pipeline import run_episode

log = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"


class EpisodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class Episode:
    name: str
    status: EpisodeStatus = EpisodeStatus.PENDING
    seconds: float | None = None
    error: str | None = None
    started: float | None = None

    @property
    def finished(self) -> bool:
        return self.status in (EpisodeStatus.DONE, EpisodeStatus.SKIPPED)

    @classmethod
    def from_dict(cls, data: dict) -> Episode:
        known = {f.name for f in fields(cls)}
        ep = cls(**{k: v for k, v in data.items() if k in known})
        ep.status = EpisodeStatus(ep.status)
        return ep


@dataclass
class Job:
    name: str
    input: str
    output: str
    force: bool = False
    sidecar: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    status: JobStatus = JobStatus.QUEUED
    stop_requested: bool = False
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    episodes: list[Episode] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Job:
        known = {f.name for f in fields(cls)}
        job = cls(**{k: v for k, v in data.items() if k in known and k != "episodes"})
        job.status = JobStatus(job.status)
        job.episodes = [Episode.from_dict(e) for e in data.get("episodes", [])]
        return job

    def merge_episodes(self, videos: list[Path]) -> None:
        known = {ep.name for ep in self.episodes}
        self.episodes += [Episode(v.name) for v in videos if v.name not in known]
        self.episodes.sort(key=lambda ep: ep.name.lower())


class JobStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Job]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            jobs = [Job.from_dict(d) for d in raw]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, TypeError):
            log.exception("Ignoring unreadable queue file %s", self.path)
            return []
        for job in jobs:
            if job.status is JobStatus.RUNNING:
                job.status = JobStatus.QUEUED
            for ep in job.episodes:
                if ep.status is EpisodeStatus.RUNNING:
                    ep.status = EpisodeStatus.PENDING
        return jobs

    def save(self, jobs: list[Job]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(j) for j in jobs], indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


class JobQueue:
    def __init__(
        self,
        loader: BackendLoader,
        store: JobStore,
        runner: Callable[..., object] = run_episode,
    ) -> None:
        self.loader = loader
        self.store = store
        self.runner = runner
        self.jobs = store.load()
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._actions: dict[str, Callable[[Job], None]] = {
            "stop": self._stop,
            "remove": self._remove,
            "retry": self._retry,
            "up": lambda job: self._move(job, -1),
            "down": lambda job: self._move(job, 1),
        }

    # -- public API (thread-safe)

    def start(self) -> None:
        threading.Thread(target=self._worker, name="autosub-worker", daemon=True).start()

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [asdict(j) for j in self.jobs]

    def add(self, name: str, input_dir: str, output_dir: str, *, force: bool = False, sidecar: bool = False) -> Job:
        inp = Path(input_dir).expanduser()
        out = Path(output_dir).expanduser()
        if not inp.is_dir():
            raise ValueError(f"Input folder does not exist: {inp}")
        if not out.is_absolute():
            raise ValueError("Output folder must be a full path")
        videos = find_videos(inp)
        if not videos:
            raise ValueError(f"No videos found in {inp}")
        job = Job(name=name.strip() or inp.name, input=str(inp), output=str(out), force=force, sidecar=sidecar)
        job.merge_episodes(videos)
        with self._lock:
            self.jobs.append(job)
            self._save()
        self._wake.set()
        return job

    def act(self, job_id: str, action: str) -> None:
        handler = self._actions.get(action)
        if handler is None:
            raise ValueError(f"Unknown action: {action}")
        with self._lock:
            job = next((j for j in self.jobs if j.id == job_id), None)
            if job is None:
                raise ValueError("No such job")
            handler(job)
            self._save()
        self._wake.set()

    def clear_finished(self) -> None:
        with self._lock:
            self.jobs = [j for j in self.jobs if j.status is not JobStatus.DONE]
            self._save()

    def run_next(self) -> bool:
        """Process the next queued job synchronously. Returns False when nothing is queued."""
        with self._lock:
            job = next((j for j in self.jobs if j.status is JobStatus.QUEUED), None)
            if job is None:
                return False
            job.status = JobStatus.RUNNING
            job.started = job.started or time.time()
            if Path(job.input).is_dir():
                job.merge_episodes(find_videos(Path(job.input)))
            self._save()
        self._run(job)
        return True

    # -- actions

    def _stop(self, job: Job) -> None:
        if job.status is JobStatus.RUNNING:
            job.stop_requested = True
        elif job.status is JobStatus.QUEUED:
            job.status = JobStatus.STOPPED

    def _remove(self, job: Job) -> None:
        if job.status is JobStatus.RUNNING:
            raise ValueError("Stop the job before removing it")
        self.jobs.remove(job)

    def _retry(self, job: Job) -> None:
        if job.status is JobStatus.RUNNING:
            raise ValueError("Job is already running")
        job.status, job.stop_requested, job.finished = JobStatus.QUEUED, False, None
        for ep in job.episodes:
            if ep.status is EpisodeStatus.FAILED:
                ep.status, ep.error, ep.seconds = EpisodeStatus.PENDING, None, None

    def _move(self, job: Job, step: int) -> None:
        i = self.jobs.index(job)
        j = i + step
        if 0 <= j < len(self.jobs):
            self.jobs[i], self.jobs[j] = self.jobs[j], self.jobs[i]

    # -- worker

    def _save(self) -> None:
        self.store.save(self.jobs)

    def _worker(self) -> None:
        while True:
            if not self.run_next():
                self._wake.wait()
                self._wake.clear()

    def _run(self, job: Job) -> None:
        output = Path(job.output)
        for ep in job.episodes:
            if ep.finished:
                continue
            with self._lock:
                if job.stop_requested:
                    break
                ep.status, ep.error, ep.started = EpisodeStatus.RUNNING, None, time.time()
                self._save()
            started = time.monotonic()
            try:
                video = Path(job.input) / ep.name
                if not video.exists():
                    raise FileNotFoundError("video file is missing")
                outcome = self.runner(
                    self.loader,
                    video,
                    output,
                    model_id=self.loader.spec.model_id,
                    force=job.force,
                    sidecar=job.sidecar,
                )
                status, error = EpisodeStatus(outcome.value), None
            except MediaError as exc:
                log.warning("Failed: %s: %s", ep.name, exc)
                status, error = EpisodeStatus.FAILED, str(exc)
            except Exception as exc:
                log.exception("Failed: %s", ep.name)
                status, error = EpisodeStatus.FAILED, str(exc) or type(exc).__name__
            with self._lock:
                ep.status, ep.error, ep.seconds = status, error, round(time.monotonic() - started, 1)
                self._save()
            if self.loader.status == "error":
                break

        with self._lock:
            if job.stop_requested:
                job.status = JobStatus.STOPPED
            elif all(ep.finished for ep in job.episodes):
                job.status = JobStatus.DONE
            else:
                job.status = JobStatus.FAILED
            job.stop_requested = False
            job.finished = time.time()
            self._save()
