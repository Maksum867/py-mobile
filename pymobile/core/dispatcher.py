"""Thread-safe dispatch of application work into the next UI render.

Timers, jobs and HTTP futures intentionally run outside the code that created a
screen.  ``App.dispatch`` is the explicit hand-off point: it queues a small
state update, requests one render, and executes the update immediately before
that render serialises the widget tree.  Android, Tk and the web bridge already
marshal rendering to their respective UI/event-loop threads.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from typing import Any

from ..logging import get_logger

__all__ = ["UiDispatcher"]

_log = get_logger("dispatcher")


class UiDispatcher:
    """A FIFO queue of UI-state callbacks safe to post from any thread."""

    __slots__ = ("_lock", "_queue", "_closed")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: deque[Callable[[], None]] = deque()
        self._closed = False

    @property
    def pending(self) -> int:
        """Number of callbacks waiting to run."""
        with self._lock:
            return len(self._queue)

    def post(self, callback: Callable[..., None], *args: Any, **kwargs: Any) -> bool:
        """Queue ``callback(*args, **kwargs)`` and return whether it was accepted."""

        def invoke() -> None:
            callback(*args, **kwargs)

        with self._lock:
            if self._closed:
                return False
            self._queue.append(invoke)
            return True

    def drain(self) -> int:
        """Run all callbacks currently queued, logging one failure at a time."""
        with self._lock:
            callbacks = list(self._queue)
            self._queue.clear()
        for callback in callbacks:
            try:
                callback()
            except Exception:
                _log.exception("error in dispatched UI callback")
        return len(callbacks)

    def close(self) -> None:
        """Reject new work and discard callbacks during application shutdown."""
        with self._lock:
            self._closed = True
            self._queue.clear()
