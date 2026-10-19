"""Command-line batch: subtitle every video in a folder."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from autosub import backends
from autosub.config import INPUT_DIR, OUTPUT_DIR
from autosub.media import find_videos, missing_tools
from autosub.pipeline import Outcome, run_episode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="autosub", description="Generate English subtitles for a folder of videos.")
    parser.add_argument("--input", type=Path, default=INPUT_DIR, help="folder of videos (default: ./input)")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="results folder (default: ./output)")
    parser.add_argument("--force", action="store_true", help="reprocess videos even if unchanged")
    parser.add_argument("--sidecar", action="store_true", help="also save each .srt next to its video")
    parser.add_argument(
        "--backend",
        choices=("auto", *backends.BACKENDS),
        default="auto",
        help="auto = MLX on Apple Silicon, ONNX Runtime elsewhere",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if missing := missing_tools():
        print(f"error: {', '.join(missing)} not found. Run the setup script first (see README).", file=sys.stderr)
        return 1

    args.input.mkdir(parents=True, exist_ok=True)
    videos = find_videos(args.input)
    if not videos:
        print(f"No videos found in {args.input}")
        return 0

    spec = backends.resolve(args.backend)
    loader = backends.BackendLoader(spec, on_loading=lambda: print(f"Loading model {spec.model_id} ..."))
    counts = {Outcome.DONE: 0, Outcome.SKIPPED: 0}
    failures = 0
    for i, video in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] {video.name}", flush=True)
        started = time.monotonic()
        try:
            outcome = run_episode(
                loader, video, args.output, model_id=spec.model_id, force=args.force, sidecar=args.sidecar
            )
        except Exception as exc:
            if loader.status == "error":
                print(f"error: could not load the model: {exc}", file=sys.stderr)
                return 1
            failures += 1
            print(f"      FAILED: {exc}", file=sys.stderr)
            continue
        counts[outcome] += 1
        if outcome is Outcome.SKIPPED:
            print("      already done")
        else:
            print(f"      done in {time.monotonic() - started:.1f}s")

    print(
        f"\nFinished: {counts[Outcome.DONE]} transcribed, {counts[Outcome.SKIPPED]} already done, {failures} failed."
        f"\nPlex subtitles: {args.output / 'plex'}"
    )
    return 1 if failures else 0
