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
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from ...errors import ResourceError
from ...logging import get_logger

__all__ = ["Storage", "default_storage_path"]

_log = get_logger("api.storage")


DEFAULT_STORE_FILENAME = "pymobile_store.json"


def default_storage_path(filename: str = DEFAULT_STORE_FILENAME) -> Path:
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


def _resolve_store_path(path: str | Path | None) -> Path:
    """Turn a user-supplied location into the path of the store *file*.

    ``storage_path`` is routinely read as "the folder to keep my data in" —
    the environment override ``PYMOBILE_STORAGE_DIR`` really is a directory —
    so a directory is accepted here and gets the default filename appended
    instead of failing with ``IsADirectoryError`` from inside :meth:`save`.
    """
    if path is None:
        return default_storage_path()
    text = str(path)
    resolved = Path(text)
    looks_like_dir = text.endswith(("/", os.sep)) or (os.altsep and text.endswith(os.altsep))
    if resolved.is_dir() or looks_like_dir:
        return resolved / DEFAULT_STORE_FILENAME
    return resolved


class Storage:
    """A JSON-backed key/value store.

    Example::

        store = Storage()
        store.increment("taps")          # atomic; safe from jobs and timers

    ``path`` may be either the store **file** or a **directory** to keep it in;
    a directory (existing, or a path ending in a separator) gets the default
    filename appended, so both spellings below do the same thing::

        Storage("/tmp/my-app/store.json")
        Storage("/tmp/my-app")

    Keys must be non-empty strings. ``__getitem__``/``__setitem__`` map to
    :meth:`get`/:meth:`set`; ``in``/``del`` work as expected.

    Individual operations are atomic. A read-modify-write **sequence** written
    by hand is not — use :meth:`update`, :meth:`increment` or the
    :meth:`transaction` context manager when several steps must be one unit.
    """

    __slots__ = ("_path", "_data", "_loaded", "_lock")

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = _resolve_store_path(path)
        self._data: dict[str, Any] = {}
        self._loaded = False
        # A re-entrant lock makes every single operation atomic, and backs the
        # explicit `transaction()` block for multi-step sequences.
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
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(
                    dir=str(self._path.parent), suffix=".tmp", prefix=self._path.name
                )
            except OSError as exc:
                raise ResourceError(
                    f"Could not open the storage directory {self._path.parent}: {exc}",
                    hint="Check that the path is writable and is not a file.",
                ) from exc
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(self._data, handle, ensure_ascii=False, indent=2)
                os.replace(temp_name, self._path)
            except IsADirectoryError as exc:
                with suppress(OSError):
                    os.unlink(temp_name)
                raise ResourceError(
                    f"The storage path {self._path} is a directory, not a file.",
                    hint=(
                        "Pass a file such as "
                        f"{self._path / DEFAULT_STORE_FILENAME}, or a directory that "
                        "does not yet exist; PYMOBILE_STORAGE_DIR takes the directory."
                    ),
                ) from exc
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

    # -- atomic sequences --------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[Storage]:
        """Hold the store lock for a multi-step read-modify-write.

        Single operations are already atomic; this is for sequences that must
        not interleave with a job, a timer or an HTTP callback::

            with app.storage.transaction() as store:
                cart = store.get("cart", [])
                cart.append(item)
                store["cart"] = cart

        Writes inside the block persist as they happen, and the whole block is
        serialised against other threads in this process.
        """
        with self._lock:
            self._load()
            yield self

    def update(self, key: str, function: Callable[[Any], Any], default: Any = None) -> Any:
        """Atomically replace ``key`` with ``function(current_value)``.

        ``store.update("cart", lambda items: [*items, new], default=[])`` is
        race-free where ``store["cart"] = store.get("cart", []) + [new]`` is
        not: the read and the write happen under one lock.
        """
        with self._lock:
            self._load()
            new_value = function(self._data.get(key, default))
            self.set(key, new_value)
            return new_value

    def increment(self, key: str, amount: float = 1) -> float:
        """Atomically add ``amount`` to a numeric entry and return the result.

        Missing or non-numeric entries start from zero.
        """
        def bump(current: Any) -> float:
            numeric = isinstance(current, (int, float)) and not isinstance(current, bool)
            return (current if numeric else 0) + amount

        return float(self.update(key, bump, default=0))

    def setdefault(self, key: str, default: Any) -> Any:
        """Return ``key``, storing and returning ``default`` when it is absent."""
        with self._lock:
            self._load()
            if key in self._data:
                return self._data[key]
            self.set(key, default)
            return default

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
        with self._lock:
            self._load()
            if key not in self._data:
                raise KeyError(key)
            return self._data[key]

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
