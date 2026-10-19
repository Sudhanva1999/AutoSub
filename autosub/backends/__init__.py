"""Backend registry. Add an engine by implementing `Backend` and registering a `BackendSpec`."""

from __future__ import annotations

import platform
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

from autosub.backends import mlx, onnx
from autosub.backends.base import Backend


@dataclass(frozen=True)
class BackendSpec:
    name: str
    model_id: str
    factory: Callable[[], Backend]

    def load(self) -> Backend:
        return self.factory()


BACKENDS: dict[str, BackendSpec] = {
    "mlx": BackendSpec("mlx", mlx.MODEL_ID, mlx.MlxBackend),
    "onnx": BackendSpec("onnx", onnx.MODEL_ID, onnx.OnnxBackend),
}


def default_backend() -> str:
    return "mlx" if sys.platform == "darwin" and platform.machine() == "arm64" else "onnx"


def resolve(name: str = "auto") -> BackendSpec:
    return BACKENDS[default_backend() if name == "auto" else name]


class BackendLoader:
    """Loads a backend on first call and caches it. Safe to call from several threads."""

    def __init__(self, spec: BackendSpec, on_loading: Callable[[], None] | None = None) -> None:
        self.spec = spec
        self.status = "idle"
        self.label = ""
        self.error = ""
        self._on_loading = on_loading
        self._backend: Backend | None = None
        self._lock = threading.Lock()

    def __call__(self) -> Backend:
        with self._lock:
            if self._backend is None:
                self.status, self.error = "loading", ""
                if self._on_loading:
                    self._on_loading()
                try:
                    self._backend = self.spec.load()
                except Exception as exc:
                    self.status, self.error = "error", str(exc) or type(exc).__name__
                    raise
                self.status, self.label = "ready", self._backend.label
            return self._backend


__all__ = ["BACKENDS", "Backend", "BackendLoader", "BackendSpec", "default_backend", "resolve"]
