"""Local HTTP server for the AutoSub web UI. Binds to 127.0.0.1 only."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from autosub import backends
from autosub.config import INPUT_DIR, OUTPUT_DIR, QUEUE_FILE
from autosub.media import missing_tools
from autosub.web import files
from autosub.web.jobs import JobQueue, JobStore

DEFAULT_PORT = 8765
STATIC_DIR = Path(__file__).parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

log = logging.getLogger(__name__)

Query = dict[str, str]
Body = dict[str, Any]


class App:
    def __init__(self, queue: JobQueue) -> None:
        self.queue = queue
        self.get_routes: dict[str, Callable[[Query], Any]] = {
            "/api/state": lambda q: self.state(),
            "/api/roots": lambda q: files.roots(),
            "/api/browse": lambda q: files.browse(q.get("path", "")),
            "/api/scan": lambda q: files.scan(q.get("path", "")),
        }
        self.post_routes: dict[str, Callable[[Body], Any]] = {
            "/api/jobs": self.add_job,
            "/api/action": lambda b: self.queue.act(b["id"], b["action"]),
            "/api/clear": lambda b: self.queue.clear_finished(),
            "/api/mkdir": lambda b: files.make_dir(b["path"]),
            "/api/reveal": lambda b: files.reveal(b["path"]),
        }

    def state(self) -> dict:
        loader = self.queue.loader
        return {
            "backend": {
                "name": loader.spec.name,
                "status": loader.status,
                "label": loader.label,
                "error": loader.error,
            },
            "missing_tools": missing_tools(),
            "jobs": self.queue.snapshot(),
            "default_input": str(INPUT_DIR),
            "default_output": str(OUTPUT_DIR),
            "path_sep": os.sep,
        }

    def add_job(self, body: Body) -> dict:
        job = self.queue.add(
            body.get("name", ""),
            body["input"],
            body["output"],
            force=bool(body.get("force")),
            sidecar=bool(body.get("sidecar")),
        )
        return {"id": job.id}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: App) -> None:
        super().__init__(address, Handler)
        self.app = app

    @property
    def allowed_hosts(self) -> set[str]:
        port = self.server_address[1]
        return {f"127.0.0.1:{port}", f"localhost:{port}"}


class Handler(BaseHTTPRequestHandler):
    server: Server

    def log_message(self, format: str, *args: Any) -> None:
        log.debug(format, *args)

    def do_GET(self) -> None:
        if not self._host_ok():
            return
        url = urlparse(self.path)
        if url.path in STATIC_FILES:
            name, ctype = STATIC_FILES[url.path]
            self._send(200, (STATIC_DIR / name).read_bytes(), ctype)
            return
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        self._dispatch(self.server.app.get_routes.get(url.path), query)

    def do_POST(self) -> None:
        if not self._host_ok():
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._json({"error": "Expected application/json"}, 415)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            self._json({"error": "Invalid JSON"}, 400)
            return
        self._dispatch(self.server.app.post_routes.get(urlparse(self.path).path), body)

    def _dispatch(self, route: Callable[[Any], Any] | None, arg: Any) -> None:
        if route is None:
            self._json({"error": "Not found"}, 404)
            return
        try:
            result = route(arg)
        except KeyError as exc:
            self._json({"error": f"Missing field: {exc.args[0]}"}, 400)
        except (ValueError, OSError) as exc:
            self._json({"error": str(exc)}, 400)
        else:
            self._json(result if result is not None else {"ok": True})

    def _host_ok(self) -> bool:
        # Blocks DNS-rebinding: only requests addressed to localhost are served.
        if self.headers.get("Host") in self.server.allowed_hosts:
            return True
        self._json({"error": "Forbidden"}, 403)
        return False

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(code, json.dumps(data).encode(), "application/json")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def create_server(port: int = DEFAULT_PORT, backend: str = "auto", queue_file: Path = QUEUE_FILE) -> Server:
    loader = backends.BackendLoader(backends.resolve(backend))
    queue = JobQueue(loader, JobStore(queue_file))
    server = Server(("127.0.0.1", port), App(queue))
    queue.start()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autosub-ui", description="AutoSub web UI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    parser.add_argument("--backend", choices=("auto", *backends.BACKENDS), default="auto")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("autosub").setLevel(logging.INFO)

    try:
        server = create_server(args.port, args.backend)
    except OSError:
        print(f"Port {args.port} is busy. AutoSub may already be running at http://127.0.0.1:{args.port}")
        print("Or start it on another port: --port 8766")
        return 1

    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"AutoSub UI running at {url}  (press Ctrl+C to quit)")
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
