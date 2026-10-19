"""Filesystem helpers for the folder picker."""

from __future__ import annotations

import os
import string
import subprocess
import sys
from pathlib import Path

from autosub.config import OUTPUT_DIR
from autosub.media import find_videos, is_video


def _visible_dirs(folder: Path) -> list[Path]:
    dirs = []
    for entry in folder.iterdir():
        try:
            if entry.is_dir() and not entry.name.startswith("."):
                dirs.append(entry)
        except OSError:
            continue
    return sorted(dirs, key=lambda d: d.name.lower())


def _existing_dir(path: str) -> Path:
    p = Path(path).expanduser() if path else Path.home()
    if not p.is_dir():
        raise ValueError(f"Not a folder: {p}")
    return p.resolve()


def _mounts() -> list[Path]:
    if sys.platform == "win32":
        return [Path(f"{d}:\\") for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    bases = [Path("/Volumes")] if sys.platform == "darwin" else [Path("/media") / Path.home().name, Path("/mnt")]
    return [d for base in bases if base.is_dir() for d in _visible_dirs(base)]


def roots() -> list[dict]:
    home = Path.home()
    places = [("Home", home)]
    places += [(name, home / name) for name in ("Movies", "Videos", "Desktop", "Downloads") if (home / name).is_dir()]
    places.append(("AutoSub output", OUTPUT_DIR))
    places += [(str(m).rstrip("\\") if sys.platform == "win32" else m.name, m) for m in _mounts()]
    return [{"label": label, "path": str(path)} for label, path in places]


def browse(path: str) -> dict:
    folder = _existing_dir(path)
    try:
        entries = list(folder.iterdir())
    except PermissionError as exc:
        raise ValueError(f"No permission to open {folder}") from exc
    videos = sum(1 for e in entries if is_video(e) and e.is_file())
    parent = folder.parent if folder.parent != folder else None
    return {
        "path": str(folder),
        "parent": str(parent) if parent else None,
        "dirs": [d.name for d in _visible_dirs(folder)],
        "videos": videos,
    }


def scan(path: str) -> dict:
    """Count videos in a folder, and in any subfolders that look like seasons."""
    folder = _existing_dir(path)
    seasons = []
    for sub in _visible_dirs(folder):
        try:
            count = len(find_videos(sub))
        except OSError:
            continue
        if count:
            seasons.append({"name": sub.name, "path": str(sub), "videos": count})
    return {"path": str(folder), "name": folder.name, "videos": len(find_videos(folder)), "seasons": seasons}


def make_dir(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.is_absolute():
        raise ValueError("Folder must be a full path")
    p.mkdir(parents=True, exist_ok=True)
    return {"path": str(p)}


def reveal(path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Folder doesn't exist yet: {p}")
    if sys.platform == "win32":
        os.startfile(p)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)])
