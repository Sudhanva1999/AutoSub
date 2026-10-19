# AutoSub

Generate English subtitles for whole seasons of video, entirely on your own computer, and drop
them straight into Plex.

- **Local and private.** Speech is transcribed by NVIDIA's Parakeet TDT 0.6B v2 model running on
  your machine. The internet is only used once, to download the model.
- **Web UI.** Queue seasons or whole shows, and watch progress per episode and per season.
- **Plex-ready.** Each video gets a matching `<video name>.en.srt`.
- **Cross-platform.** Runs on macOS, Windows and Linux, on the GPU when one is available.

| Platform | Engine | Runs on |
|---|---|---|
| macOS, Apple Silicon (M1 and later) | MLX | Apple GPU |
| Windows 10/11 | ONNX Runtime | NVIDIA GPU (CUDA) if present, otherwise CPU |
| Linux | ONNX Runtime | NVIDIA GPU (CUDA) if present, otherwise CPU |
| macOS, Intel | ONNX Runtime | CPU |

The engine is chosen automatically. Both engines run the same model.

---

## Contents

1. [Install](#1-install)
2. [Use the web UI](#2-use-the-web-ui)
3. [Add the subtitles to Plex](#3-add-the-subtitles-to-plex)
4. [Command line](#4-command-line)
5. [Output files](#5-output-files)
6. [Troubleshooting](#6-troubleshooting)
7. [For developers](#7-for-developers)

---

## 1. Install

You only need to do this once. Setup installs FFmpeg and [uv](https://docs.astral.sh/uv/) if
they're missing, then creates a private Python environment in `.venv`. Nothing else on your
system is changed.

### macOS

1. Install [Homebrew](https://brew.sh) if you don't already have it.
2. Open Terminal in the AutoSub folder and run:
   ```
   ./setup.sh
   ```

### Windows

1. Double-click **`setup_windows.bat`**.
2. If it just installed FFmpeg and then reports it can't find it, close the window and run it again.

No `winget` on your PC? Install FFmpeg from <https://www.gyan.dev/ffmpeg/builds/>, add its `bin`
folder to your PATH, and run setup again.

### Linux

1. Install FFmpeg:
   ```
   sudo apt install ffmpeg      # Debian / Ubuntu
   sudo dnf install ffmpeg      # Fedora (enable RPM Fusion first)
   sudo pacman -S ffmpeg        # Arch
   ```
2. From the AutoSub folder:
   ```
   ./setup.sh
   ```

**NVIDIA GPUs (Windows and Linux):** if `nvidia-smi` works on your machine, setup installs the GPU
version automatically. You need a recent NVIDIA driver (CUDA 12 support); the CUDA libraries come
with the install.

---

## 2. Use the web UI

### Start it

| Platform | How |
|---|---|
| macOS | Double-click **`run_ui.command`** |
| Windows | Double-click **`run_ui.bat`** |
| Linux | `./run_ui.sh` |

Your browser opens at <http://127.0.0.1:8765>. Keep the terminal window open while AutoSub is
working; closing it stops AutoSub. The UI is only reachable from your own computer.

### Queue one season

1. **Input folder**: click **Browse…** and open the folder that contains the episodes.
   AutoSub shows how many episodes it found.
2. **Name**: filled in from the folder name. Change it if you like.
3. **Output folder**: defaults to `AutoSub/output/<folder name>`. Click **Browse…** to choose a
   different place. To make a new folder, type a name into **New folder name** and click
   **Create folder**. Folders that don't exist yet are also created automatically. Below the
   field, AutoSub shows where the Plex subtitles will end up.
4. Click **Add to queue**.

### Queue a whole show

Choose the **show** folder as the input, the one that contains `Season 1`, `Season 2`, and so on.
AutoSub lists every season folder it finds and how many episodes each has. Untick any you don't
want, then click **Add to queue**. Each season becomes its own entry in the queue, with its own
output folder `<output folder>/<season folder name>`.

### Options

| Option | What it does |
|---|---|
| **Also save each .srt next to its video** | Copies every subtitle into the input folder beside its video. If the input folder is your Plex library, the subtitles are in place without copying anything. |
| **Redo episodes that already have subtitles** | Normally, episodes that are already done are skipped. Tick this to transcribe them again. |

### Watch progress

At the top of the queue:

- **Seasons in queue**: seasons that are waiting or running.
- **Episodes finished**: across every season in the list.
- **Estimated time left**: based on the average time per episode so far.

Each season shows a progress bar (green = finished, blue = in progress, red = failed), how many
episodes are done, and its own time-left estimate. Click **Show episodes** to see each episode as
*Waiting*, *Transcribing…* (with a running timer), done (with how long it took), *Already done*,
or *Failed* (with the reason).

### Manage the queue

Seasons run one at a time, from the top of the list down.

| Button | What it does |
|---|---|
| ↑ / ↓ | Move a season up or down the queue |
| **Pause** | Hold a season that hasn't started yet |
| **Stop after this episode** | Finish the current episode, then stop that season |
| **Resume** / **Retry failed** | Put a paused or failed season back in the queue. Only unfinished episodes are processed. |
| **Open output** | Open the output folder in Finder, Explorer or your file manager |
| **Remove** | Remove the season from the list. Subtitles already written stay on disk. |
| **Clear finished** | Remove every completed season from the list |

The queue is saved to `ui_queue.json`. If you close AutoSub while a season is running, it carries
on from the next unfinished episode the next time you start the UI.

---

## 3. Add the subtitles to Plex

Every output folder has a **`plex`** folder with one `.srt` per episode, named to match its video:

```
Attack on Titan S3 - E01.mkv     ← your video, in your Plex library
Attack on Titan S3 - E01.en.srt  ← from the plex folder
```

1. Copy everything in the `plex` folder into the library folder that holds the videos. You can skip
   this step if you used **Also save each .srt next to its video** on your library folder.
2. In Plex, open the show and choose **⋯ → Refresh Metadata**.
3. While playing, choose **English (SRT)** in the subtitle menu.

**If Plex doesn't show them:**
- The subtitle's name must match the video's name exactly, apart from the `.en.srt` ending. If you
  renamed a video in your library, rename its subtitle the same way.
- Local subtitles must be allowed: **Library → Edit → Advanced → Use local assets** (newer agents),
  or **Settings → Agents → Local Media Assets** (legacy agents).

---

## 4. Command line

The UI is optional. To subtitle a single folder from a terminal:

| Platform | Command |
|---|---|
| macOS / Linux | `./run_batch.sh [options]` (or double-click `run_batch.command` on macOS) |
| Windows | `run_batch.bat [options]` |

With no options, it reads videos from `input/` and writes to `output/`.

| Option | Effect |
|---|---|
| `--input PATH` | Folder of videos (default `./input`) |
| `--output PATH` | Results folder (default `./output`) |
| `--sidecar` | Also save each `.srt` next to its video |
| `--force` | Redo videos that already have subtitles |
| `--backend mlx\|onnx` | Override the automatic engine choice |

Example:

```
./run_batch.sh --input "/Volumes/Media/Attack on Titan/Season 3" --output ~/Subs/AoT-S3
```

The UI launcher accepts `--port 8766` (if 8765 is taken), `--no-browser` and `--backend`.

---

## 5. Output files

For each video, the output folder contains:

```
<output folder>/
├── plex/
│   └── <video name>.en.srt          subtitles, ready for Plex
└── <video file name>/
    ├── <video name>.en.srt          subtitles
    ├── <video name>.en.vtt          WebVTT subtitles, for web players
    ├── <video name>.en.txt          plain transcript, one sentence per line
    ├── <video name>.words.json      word-level timestamps, for editing or translation
    └── state.json                   lets AutoSub skip videos that haven't changed
```

A video is transcribed again automatically if the file changes, or if the engine or the
subtitle-building rules change.

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| "Environment not found" | Run the setup step first. |
| Red banner: "ffmpeg … not found" | Install FFmpeg (see [Install](#1-install)), then restart AutoSub. |
| "Port 8765 is busy" | AutoSub is probably already running, so open <http://127.0.0.1:8765>. Or start it with `--port 8766`. |
| First season stays on "Loading model…" | The first run downloads the model (about 1.2 GB on Apple Silicon, 2.4 GB elsewhere) and shows no progress bar while it does. Wait, or check your connection. |
| Episode fails with "couldn't read this file" | The video is damaged or incomplete. Check that it plays in a video player. |
| Episode fails with "no audio stream found" | The file has no audio track, so there's nothing to transcribe. |
| NVIDIA GPU isn't used | The header shows `ONNX Runtime (CPU)`. Check that `nvidia-smi` works and your driver supports CUDA 12, then run setup again. |
| Need to work offline | Once the model has been downloaded, set `HF_HUB_OFFLINE=1` before starting AutoSub. |

---

## 7. For developers

### Layout

```
autosub/
├── config.py            paths and tunable cue rules (CueRules)
├── media.py             FFmpeg / ffprobe helpers, video discovery
├── transcript.py        Token / Word types, token → word merging
├── subtitles.py         cue building, SRT / WebVTT writers
├── pipeline.py          per-episode processing shared by the CLI and the UI
├── cli.py               command-line entry point (python -m autosub)
├── backends/
│   ├── base.py          Backend protocol
│   ├── mlx.py           parakeet-mlx (Apple Silicon)
│   ├── onnx.py          onnx-asr + Silero VAD (CUDA / CPU)
│   └── __init__.py      registry, auto-selection, lazy thread-safe loader
└── web/
    ├── server.py        HTTP server and routes (python -m autosub.web)
    ├── jobs.py          persistent job queue and background worker
    ├── files.py         folder browser helpers
    └── static/          index.html, app.css, app.js (no build step)
tests/                   pytest suite (fake backends; no model download needed)
```

The web server uses only the Python standard library. The browser polls `/api/state`, and all
transcription happens on a single background worker thread.

### Dev setup

```
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[mlx,dev]"    # or .[cpu,dev] / .[cuda,dev]
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

### Adding an engine

1. Create `autosub/backends/<name>.py` with a class that has `model_id`, `label` and
   `transcribe(wav: Path) -> list[list[Token]]`. It should return sentences of sub-word tokens timed
   in seconds from the start of the audio, where a leading space starts a new word. Import heavy
   libraries inside `__init__` so they only load when the engine is used.
2. Register it in `BACKENDS` in `autosub/backends/__init__.py`.
3. Add an optional-dependency group for it in `pyproject.toml`.

It's then available as `--backend <name>` in both the CLI and the UI.

### Tuning subtitles

Line length, cue duration and pause splitting are set in `CueRules` in `autosub/config.py`. Bump
`PIPELINE_VERSION` when you change them, so existing outputs are redone on the next run.

### Environment variables

| Variable | Effect |
|---|---|
| `AUTOSUB_HOME` | Base folder for `input/`, `output/`, `models/` and `ui_queue.json` (default: the project folder) |
| `HF_HUB_OFFLINE=1` | Use the downloaded model without contacting Hugging Face |
