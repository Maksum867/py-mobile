"""A tiny, dependency-free key/value store backed by a JSON file.

Designed for small mobile apps: settings, user prefs, a high score, a small
cache. Values are any JSON-serialisable object. Every write persists to disk
atomically (write-to-temp then rename), so a crash mid-write cannot corrupt the
store.

The file lives in the app's data directory — on Android inside the app's
private storage, on the desktop in a per-app folder under the user's data dir
overridable for tests.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

from ...logging import get_logger

__all__ = ["Storage", "default_storage_path"]

_log = get_logger("api.storage")


def default_storage_path(filename: str = "pymobile_store.json") -> Path:
    """Return a sensible default location for the store file.

    * Android: the app's private files dir (set via ``PYMOBILE_STORAGE_DIR``
      by the runtime bootstrap).
    * Desktop: ``~/.pymobile/<filename>`` (Linux/macOS) or the user's
      ``AppData`` (Windows). ``PYMOBILE_STORAGE_DIR`` overrides it everywhere
      so tests can isolate their store.
    """
    override = os.environ.get("PYMOBILE_STORAGE_DIR")
    if override:
        return Path(override) / filename
    platform = os.environ.get("ANDROID_APP_PATH")
    if platform:
        return Path(platform) / ".." / ".." / "files" / filename
    home = Path.home()
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(home))) / "pymobile"
    else:
        base = home / ".pymobile"
    return base / filename


class Storage:
    """A JSON-backed key/value store.

    Example::

        store = Storage()
        store["taps"] = store.get("taps", 0) + 1
        store.save()

    Keys must be non-empty strings. ``__getitem__``/``__setitem__`` map to
    :meth:`get`/:meth:`set`; ``in``/``del`` work as expected.
    """

    __slots__ = ("_path", "_data", "_loaded", "_lock")

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else default_storage_path()
        self._data: dict[str, Any] = {}
        self._loaded = False
        # A re-entrant lock protects read-modify-write sequences made by jobs,
        # timers and HTTP callbacks in the same application process.
        self._lock = threading.RLock()

    # -- lifecycle ---------------------------------------------------------
    @property
    def path(self) -> Path:
        """Filesystem location of the store."""
        return self._path

    def _load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._data.update(data)
            except (OSError, ValueError):
                # Missing or corrupt store = start fresh; the next save rewrites it.
                self._data = {}

    def save(self) -> None:
        """Persist the store to disk atomically and under its process lock."""
        with self._lock:
            self._load()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                dir=str(self._path.parent), suffix=".tmp", prefix=self._path.name
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(self._data, handle, ensure_ascii=False, indent=2)
                os.replace(temp_name, self._path)
            except BaseException:
                with suppress(OSError):
                    os.unlink(temp_name)
                raise

    # -- mapping API -------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for ``key``, or ``default`` when absent."""
        with self._lock:
            self._load()
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> Any:
        """Set ``key`` atomically within this process and persist it."""
        if not isinstance(key, str) or not key:
            raise ValueError("storage key must be a non-empty string")
        with self._lock:
            self._load()
            self._data[key] = value
            self.save()
            return value

    def delete(self, key: str) -> bool:
        """Remove ``key`` and return whether it existed."""
        with self._lock:
            self._load()
            if key in self._data:
                del self._data[key]
                self.save()
                return True
            return False

    def contains(self, key: str) -> bool:
        """Whether ``key`` is present."""
        with self._lock:
            self._load()
            return key in self._data

    def clear(self) -> None:
        """Remove every entry and persist the empty store."""
        with self._lock:
            self._data = {}
            self._loaded = True
            self.save()

    def keys(self) -> list[str]:
        """All stored keys."""
        with self._lock:
            self._load()
            return list(self._data.keys())

    def items(self) -> list[tuple[str, Any]]:
        """All ``(key, value)`` pairs."""
        with self._lock:
            self._load()
            return list(self._data.items())

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        if not self.delete(key):
            raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self.contains(key)

    def __len__(self) -> int:
        self._load()
        return len(self._data)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Storage path={self._path}>"
