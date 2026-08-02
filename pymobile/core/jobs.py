"""Background jobs (a lightweight WorkManager-style API).

The scheduler runs callbacks on a background thread but does not track "jobs"
that need to be remembered, cancelled by name, or observed when they finish.
:class:`JobManager` layers that on top: you enqueue a job, get back a
:class:`JobHandle`, and can cancel it by id or wait for its result. Jobs that
run repeatedly and one-shot jobs are both supported.

Jobs fire on a daemon thread, so the UI is never blocked. An exception inside a
job is captured on the handle and delivered to ``on_error`` (if any) rather than
crashing the app. All jobs are cancelled automatically when the app stops.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from ..logging import get_logger

__all__ = ["JobManager", "JobHandle", "job_id"]

_log = get_logger("jobs")


def job_id() -> str:
    """Return a unique, human-friendly job id."""
    return uuid.uuid4().hex[:12]


class JobHandle:
    """A handle to an enqueued background job.

    ``done``/``result``/``error`` expose the outcome; ``cancel()`` stops a
    pending or repeating job and clears its callbacks. ``wait()`` blocks until
    the job finishes and returns its result (raising the job's error if any).
    """

    __slots__ = ("id", "_cancel_fn", "_done", "_result", "_error", "_lock",
                 "_cancelled", "_callbacks")

    def __init__(self, job_id: str, cancel_fn: Callable[[], None]) -> None:
        self.id = job_id
        self._cancel_fn = cancel_fn
        self._done = threading.Event()
        self._result: Any = None
        self._error: BaseException | None = None
        self._lock = threading.Lock()
        self._cancelled = False
        self._callbacks: list[Callable[[], None]] = []

    @property
    def done(self) -> bool:
        """Whether the job has completed."""
        return self._done.is_set()

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` was called."""
        return self._cancelled

    def cancel(self) -> None:
        """Cancel the job (if not finished) and suppress its callbacks."""
        with self._lock:
            self._cancelled = True
            self._callbacks.clear()
            self._done.set()
        self._cancel_fn()

    def then(self, on_done: Callable[[Any], None],
             on_error: Callable[[BaseException], None] | None = None) -> "JobHandle":
        """Register callbacks for completion; run immediately if already done."""
        with self._lock:
            if self._cancelled:
                return self
            self._callbacks.append(lambda: self._fire(on_done, on_error))
            if self._done.is_set():
                cb = self._callbacks.pop()
                cb()
        return self

    def wait(self, timeout: float | None = None) -> Any:
        """Block until the job finishes and return its result."""
        self._done.wait(timeout)
        if self._error is not None:
            raise self._error
        return self._result

    def _fire(self, on_done, on_error) -> None:
        if self._error is not None:
            if on_error is not None:
                on_error(self._error)
        else:
            on_done(self._result)

    def _complete(self, result: Any, error: BaseException | None) -> None:
        with self._lock:
            self._result = result
            self._error = error
            self._done.set()
            callbacks = list(self._callbacks)
            self._callbacks.clear()
        for cb in callbacks:
            if not self._cancelled:
                cb()


class JobManager:
    """Enqueues and tracks background jobs.

    ``enqueue`` runs ``fn`` on a daemon thread. ``every`` runs ``fn`` on an
    interval until cancelled. ``cancel_all`` stops everything (called by
    :meth:`App.stop` integration).
    """

    __slots__ = ("_jobs", "_lock", "_alive")

    def __init__(self) -> None:
        self._jobs: dict[str, JobHandle] = {}
        self._lock = threading.Lock()
        self._alive = True

    @property
    def active(self) -> list[JobHandle]:
        """Handles for jobs that have not finished."""
        with self._lock:
            return [h for h in self._jobs.values() if not h.done]

    def enqueue(self, fn: Callable[[], Any], *, name: str | None = None) -> JobHandle:
        """Run ``fn`` once on a background thread; returns a :class:`JobHandle`."""
        if not self._alive:
            raise RuntimeError("JobManager has been shut down")
        handle_id = name or job_id()

        def run() -> None:
            try:
                result = fn()
                handle._complete(result, None)
            except BaseException as error:  # noqa: BLE001 - delivered via handle
                handle._complete(None, error)
            finally:
                with self._lock:
                    self._jobs.pop(handle_id, None)

        handle = JobHandle(handle_id, cancel_fn=lambda: None)
        with self._lock:
            self._jobs[handle_id] = handle
        threading.Thread(target=run, name=f"pymobile-job-{handle_id}", daemon=True).start()
        return handle

    def every(
        self,
        interval_ms: int,
        fn: Callable[[], Any],
        *,
        name: str | None = None,
    ) -> JobHandle:
        """Run ``fn`` every ``interval_ms`` until cancelled; returns a handle."""
        if not self._alive:
            raise RuntimeError("JobManager has been shut down")
        if interval_ms <= 0:
            raise ValueError("interval_ms must be > 0")
        handle_id = name or job_id()
        stop = threading.Event()

        def run() -> None:
            try:
                while not stop.is_set():
                    start = time.monotonic()
                    fn()
                    elapsed = (time.monotonic() - start) * 1000
                    remaining = interval_ms - elapsed
                    if remaining > 0:
                        stop.wait(remaining / 1000.0)
            except BaseException:  # noqa: BLE001
                _log.exception("repeating job %r failed; stopping", handle_id)
            finally:
                with self._lock:
                    self._jobs.pop(handle_id, None)
                stop.set()

        handle = JobHandle(handle_id, cancel_fn=lambda: stop.set())
        with self._lock:
            self._jobs[handle_id] = handle
        threading.Thread(target=run, name=f"pymobile-job-{handle_id}", daemon=True).start()
        return handle

    def cancel(self, handle_id: str) -> bool:
        """Cancel a job by id; returns whether it was found."""
        with self._lock:
            handle = self._jobs.get(handle_id)
        if handle is not None:
            handle.cancel()
            return True
        return False

    def cancel_all(self) -> None:
        """Cancel every pending/repeating job."""
        with self._lock:
            handles = list(self._jobs.values())
        for handle in handles:
            handle.cancel()

    def shutdown(self) -> None:
        """Stop accepting new jobs and cancel all pending ones."""
        self._alive = False
        self.cancel_all()
