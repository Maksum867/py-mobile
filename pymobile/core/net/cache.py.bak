"""A tiny disk-backed HTTP response cache (offline support).

Caches the body, status and headers of ``GET`` responses keyed by URL so an app
can render the last-known-good data while offline, or avoid refetching data
that rarely changes. Built on the same JSON store the framework uses for local
storage, so it adds no dependency and lives in the app's data directory.

The cache is deliberately simple: keys are URLs (with query strings), a ``ttl``
bounds freshness, and stale entries are still returned so callers can show
something rather than nothing. Use :class:`HttpCache` directly or hand it to
:class:`~pymobile.core.net.http.HttpClient` via ``cache=``.
"""

from __future__ import annotations

import base64
import hashlib
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...logging import get_logger
from ..api.storage import Storage

__all__ = ["HttpCache"]

_log = get_logger("net.cache")


def _key_for(url: str) -> str:
    """A stable, filesystem-safe cache key for a URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class HttpCache:
    """A disk-backed cache of HTTP responses keyed by URL.

    Each entry stores the status, headers, body (as bytes) and a timestamp.
    ``get`` returns ``None`` when the URL is not cached; ``set`` stores it.
    ``ttl`` seconds bound freshness but a stale entry is still returned by
    ``get_stale`` so an offline app can show the last-known data.
    """

    __slots__ = ("_storage", "_prefix")

    def __init__(self, path: str | Path | None = None, *, prefix: str = "http:") -> None:
        # Defaults to the shared app data store (keys namespaced by prefix).
        self._storage = Storage(path) if path is not None else Storage()
        self._prefix = prefix

    @classmethod
    def at(cls, path: str | Path) -> HttpCache:
        """Create a cache backed by a specific file (useful for tests)."""
        return cls(path)

    def _full_key(self, url: str) -> str:
        return self._prefix + _key_for(url)

    def get(self, url: str) -> dict[str, Any] | None:
        """Return the cached entry ``{status, headers, content, fetched_at}`` or ``None``."""
        entry = self._storage.get(self._full_key(url))
        return entry if isinstance(entry, dict) else None

    def get_stale(self, url: str, ttl: float) -> dict[str, Any] | None:
        """Return a cached entry even if it is older than ``ttl``, or ``None``."""
        return self.get(url)

    def is_fresh(self, url: str, ttl: float) -> bool:
        """Whether a cached entry exists and is newer than ``ttl`` seconds."""
        entry = self.get(url)
        if entry is None:
            return False
        return (time.time() - float(entry.get("fetched_at", 0))) < ttl

    def set(self, url: str, status: int, headers: Mapping[str, str], content: bytes) -> None:
        """Store a response for ``url``.

        The body is stored as base64 rather than a JSON array of bytes, which
        used to inflate both disk and CPU for large payloads.
        """
        self._storage.set(
            self._full_key(url),
            {
                "status": status,
                "headers": dict(headers),
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64",
                "fetched_at": time.time(),
            },
        )

    def delete(self, url: str) -> bool:
        """Remove a cached entry; returns whether it existed."""
        return self._storage.delete(self._full_key(url))

    def clear(self) -> None:
        """Drop every cached entry."""
        for key in list(self._storage.keys()):
            if key.startswith(self._prefix):
                self._storage.delete(key)

    def __contains__(self, url: object) -> bool:
        return isinstance(url, str) and self.get(url) is not None

    def __len__(self) -> int:
        # Storage exposes keys() but deliberately is not a Mapping/iterable.
        return sum(1 for key in self._storage.keys() if key.startswith(self._prefix))  # noqa: SIM118
