"""File watching for the hot-reload workflow.

A deliberately small polling watcher: no dependency on ``watchdog``/inotify,
identical behaviour on Linux, macOS and Windows, and no surprises inside
containers or on network shares where native events are unreliable.

Polling a few hundred source files costs well under a millisecond, and the
default interval means a save is picked up in about a fifth of a second —
comfortably below the point where an edit-run cycle stops feeling immediate.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

from ..logging import get_logger

__all__ = ["FileWatcher", "watch_paths"]

_log = get_logger("watcher")

#: Directories that never contain sources worth reloading for.
_IGNORED_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "node_modules",
        "build",
        "dist",
    }
)

#: Suffixes worth reacting to; everything else is noise.
DEFAULT_SUFFIXES = (".py", ".toml", ".json", ".txt")


#: Files up to this size are compared by content; larger ones by mtime+size.
_HASH_LIMIT = 2 * 1024 * 1024


class FileWatcher:
    """Detects changes to a set of files by polling.

    Timestamps alone are not enough. Several filesystems (tmpfs and overlayfs
    in containers among them, which is where hot reload is often run) report a
    coarse mtime, so two saves in quick succession look identical — the second
    edit would simply never reload. Source files are therefore compared by a
    cheap content hash, which for a project of a few hundred modules costs a
    handful of milliseconds per poll; anything above ``_HASH_LIMIT`` falls back
    to mtime and size.
    """

    def __init__(
        self,
        roots: Iterable[Path],
        *,
        suffixes: Sequence[str] = DEFAULT_SUFFIXES,
        interval: float = 0.2,
    ) -> None:
        self.roots = [Path(root).resolve() for root in roots]
        self.suffixes = tuple(suffix.lower() for suffix in suffixes)
        self.interval = interval
        self._state: dict[Path, tuple[Any, ...]] = self._snapshot()

    # -- scanning ----------------------------------------------------------
    def _files(self) -> Iterator[Path]:
        """Every file worth watching under the configured roots."""
        for root in self.roots:
            if root.is_file():
                yield root
                continue
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() not in self.suffixes:
                    continue
                if any(part in _IGNORED_DIRS for part in path.relative_to(root).parts):
                    continue
                if path.is_file():
                    yield path

    def _signature(self, path: Path) -> tuple[Any, ...] | None:
        """A value that changes whenever the file's contents do."""
        try:
            info = path.stat()
            if info.st_size <= _HASH_LIMIT:
                digest = hashlib.blake2b(path.read_bytes(), digest_size=8).digest()
                return (info.st_size, digest)
            return (info.st_size, info.st_mtime_ns)
        except OSError:  # vanished or unreadable between listing and stat
            return None

    def _snapshot(self) -> dict[Path, tuple[Any, ...]]:
        state: dict[Path, tuple[Any, ...]] = {}
        for path in self._files():
            signature = self._signature(path)
            if signature is not None:
                state[path] = signature
        return state

    def poll(self) -> list[Path]:
        """Return the paths that changed since the last call."""
        current = self._snapshot()
        changed = [
            path
            for path, signature in current.items()
            if self._state.get(path) != signature
        ]
        changed.extend(path for path in self._state if path not in current)
        self._state = current
        return sorted(changed)

    def wait(self) -> list[Path]:
        """Block until at least one file changes, then report the changes."""
        while True:
            changed = self.poll()
            if changed:
                return changed
            time.sleep(self.interval)


def watch_paths(
    roots: Iterable[Path],
    *,
    suffixes: Sequence[str] = DEFAULT_SUFFIXES,
    interval: float = 0.2,
) -> Iterator[list[Path]]:
    """Yield lists of changed paths forever."""
    watcher = FileWatcher(roots, suffixes=suffixes, interval=interval)
    while True:
        yield watcher.wait()
