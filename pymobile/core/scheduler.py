"""A tiny cross-platform scheduler.

Both desktop previews and on-device apps get identical behaviour: callbacks
fire on background daemon threads, so the UI thread is never blocked, and the
app does not need to import :mod:`threading` itself. Every scheduled job
returns a :class:`TimerHandle` that cancels it; :class:`App` cancels them all
when it stops.

Example::

    handle = app.set_interval(1000, tick)   # every second
    app.set_timeout(250, splash.dismiss)    # once, after 250 ms
    handle.cancel()                         # stop early
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from ..logging import get_logger

__all__ = ["TimerHandle", "Scheduler"]

_log = get_logger("scheduler")


class TimerHandle:
    """A cancellable scheduled job.

    Cancellation is idempotent and thread-safe: the underlying
    :class:`threading.Timer` is swapped on every reschedule of an interval,
    so ``cancel`` always reaches whichever timer is currently armed.
    """

    __slots__ = ("_timer", "_cancelled", "_lock")

    def __init__(self) -> None:
        self._timer: threading.Timer | None = None
        self._cancelled = False
        self._lock = threading.Lock()

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` has been called."""
        return self._cancelled

    def _set_timer(self, timer: threading.Timer) -> None:
        """Point the handle at the newest armed timer (internal)."""
        with self._lock:
            self._timer = timer

    def cancel(self) -> None:
        """Stop the job; further callbacks are suppressed."""
        with self._lock:
            self._cancelled = True
            timer = self._timer
        if timer is not None:
            timer.cancel()


class Scheduler:
    """Owns the one-shot and repeating timers for an application."""

    def __init__(self) -> None:
        self._handles: set[TimerHandle] = set()
        self._lock = threading.Lock()

    # -- public API --------------------------------------------------------
    def set_timeout(self, delay_ms: int, callback: Callable[[], None]) -> TimerHandle:
        """Run ``callback`` once after ``delay_ms`` milliseconds."""
        if delay_ms < 0:
            raise ValueError("delay_ms must be >= 0")
        handle = TimerHandle()

        def run() -> None:
            self._forget(handle)
            if handle.cancelled:
                return
            self._fire(callback)

        self._arm(handle, delay_ms, run)
        return self._track(handle)

    def set_interval(
        self,
        interval_ms: int,
        callback: Callable[[], None],
        *,
        drift_correction: bool = True,
    ) -> TimerHandle:
        """Run ``callback`` every ``interval_ms`` milliseconds until cancelled.

        Ticks are scheduled against a fixed timeline — the deadline for tick
        *n* is ``start + n * interval`` — so the time each callback takes does
        not accumulate. Sleeping until the next deadline instead of "interval
        milliseconds from now" is the difference between a clock that is a
        second or two slow after an hour and one that is not.

        Missed deadlines (the device slept, a callback ran long) are skipped
        rather than fired back to back, which keeps a metronome in phase
        instead of stuttering to catch up.

        Pass ``drift_correction=False`` for the old behaviour: a fixed pause
        *between* runs, which is what a poller that must not overlap wants.
        """
        if interval_ms <= 0:
            raise ValueError("interval_ms must be > 0")
        handle = TimerHandle()
        interval = interval_ms / 1000.0

        if not drift_correction:

            def repeat() -> None:
                if handle.cancelled:
                    return
                self._fire(callback)
                if handle.cancelled:
                    return
                self._arm(handle, interval_ms, repeat)

            self._arm(handle, interval_ms, repeat)
            return self._track(handle)

        started = time.monotonic()
        tick = 0

        def repeat_corrected() -> None:
            nonlocal tick
            if handle.cancelled:
                return
            self._fire(callback)
            if handle.cancelled:
                return
            tick += 1
            deadline = started + tick * interval
            delay = deadline - time.monotonic()
            if delay < 0:
                # Fell behind: jump forward to the next deadline still ahead
                # of us so the phase is preserved and no burst of catch-up
                # callbacks is fired.
                missed = int(-delay / interval) + 1
                tick += missed
                delay = started + tick * interval - time.monotonic()
            self._arm_seconds(handle, max(0.0, delay), repeat_corrected)

        self._arm(handle, interval_ms, repeat_corrected)
        return self._track(handle)

    def cancel_all(self) -> None:
        """Cancel every pending timer; called by :meth:`App.stop`."""
        with self._lock:
            handles = list(self._handles)
            self._handles.clear()
        for handle in handles:
            handle.cancel()

    # -- internals ---------------------------------------------------------
    def _arm(self, handle: TimerHandle, delay_ms: int, target: Callable[[], None]) -> None:
        self._arm_seconds(handle, delay_ms / 1000.0, target)

    def _arm_seconds(self, handle: TimerHandle, delay: float, target: Callable[[], None]) -> None:
        timer = threading.Timer(delay, target)
        timer.daemon = True
        handle._set_timer(timer)
        timer.start()

    def _fire(self, callback: Callable[[], None]) -> None:
        """Invoke ``callback``; an error is logged, never propagated."""
        try:
            callback()
        except Exception:
            _log.exception("error in scheduled callback")

    def _track(self, handle: TimerHandle) -> TimerHandle:
        with self._lock:
            self._handles.add(handle)
        return handle

    def _forget(self, handle: TimerHandle) -> None:
        with self._lock:
            self._handles.discard(handle)
