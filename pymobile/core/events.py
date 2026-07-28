"""A minimal synchronous event bus.

Used to decouple UI widgets from application logic: widgets emit events, the
app subscribes. No threading, no async — Android delivers UI callbacks on the
main thread and the bus keeps that contract simple and predictable.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from ..logging import get_logger

__all__ = ["Event", "EventBus", "Subscription"]

_log = get_logger("events")

Handler = Callable[["Event"], None]


@dataclass(frozen=True, slots=True)
class Event:
    """An immutable message flowing through the bus."""

    name: str
    source: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Read a payload field."""
        return self.data.get(key, default)


@dataclass(slots=True)
class Subscription:
    """Handle returned by :meth:`EventBus.on`; call :meth:`cancel` to detach."""

    _bus: EventBus
    _name: str
    _handler: Handler
    active: bool = True

    def cancel(self) -> None:
        """Remove the handler from the bus (idempotent)."""
        if self.active:
            self._bus.off(self._name, self._handler)
            self.active = False


class EventBus:
    """Named channels of callbacks, dispatched in registration order."""

    __slots__ = ("_handlers",)

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def on(self, name: str, handler: Handler) -> Subscription:
        """Register ``handler`` for events called ``name``."""
        self._handlers.setdefault(name, []).append(handler)
        return Subscription(self, name, handler)

    def off(self, name: str, handler: Handler) -> None:
        """Detach a previously registered handler (no error if missing)."""
        handlers = self._handlers.get(name)
        if not handlers:
            return
        with_removed = [h for h in handlers if h is not handler]
        if with_removed:
            self._handlers[name] = with_removed
        else:
            del self._handlers[name]

    def emit(self, name: str, *, source: str | None = None, **data: Any) -> Event:
        """Build an :class:`Event` and deliver it to every subscriber."""
        event = Event(name=name, source=source, data=data)
        self.dispatch(event)
        return event

    def dispatch(self, event: Event) -> None:
        """Deliver a pre-built event; handler errors are logged, never raised."""
        for handler in tuple(self._handlers.get(event.name, ())):
            try:
                handler(event)
            except Exception:
                _log.exception("handler for %r failed", event.name)

    def clear(self) -> None:
        """Drop every subscription."""
        self._handlers.clear()

    def __contains__(self, name: object) -> bool:
        return name in self._handlers

    def __iter__(self) -> Iterator[str]:
        return iter(self._handlers)

    def __len__(self) -> int:
        return sum(len(v) for v in self._handlers.values())
