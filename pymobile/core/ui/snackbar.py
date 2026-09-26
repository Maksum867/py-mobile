"""A snackbar: a short message at the bottom of the screen, with an optional action.

A toast says "done"; a snackbar says "done — undo?". It slides in above the
content, can carry one action button, and disappears by itself::

    def delete(self, item):
        self.items.remove(item)
        self.list.refresh()
        self.app.snackbar(
            f"Deleted {item.name}",
            action="Undo",
            on_action=lambda: self.restore(item),
        )

Only one snackbar is shown at a time: a new one replaces the previous one,
as on Android. It is part of the rendered frame (``tree["snackbar"]``), so
the device, the Tk and browser previews, the PNG mockup and tests with the
stub bridge all see the same thing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...log import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..app import App
    from ..scheduler import TimerHandle

__all__ = ["Snackbar", "SNACKBAR_ID"]

_log = get_logger("ui.snackbar")

#: The widget id front ends use for snackbar events ("press", "dismiss").
SNACKBAR_ID = "__snackbar__"

#: How long a snackbar stays by default, in milliseconds.
DEFAULT_DURATION = 4000
#: ... and with an action button, which needs time to be read and reached.
DEFAULT_ACTION_DURATION = 7000


class Snackbar:
    """Handle to a snackbar shown with :meth:`App.snackbar <pymobile.core.app.App.snackbar>`."""

    __slots__ = (
        "message",
        "action",
        "on_action",
        "duration_ms",
        "token",
        "_app",
        "_timer",
        "_visible",
    )

    def __init__(
        self,
        app: App | None,
        message: str,
        *,
        action: str | None,
        on_action: Callable[[], Any] | None,
        duration_ms: int,
        token: int,
    ) -> None:
        self.message = message
        self.action = action
        self.on_action = on_action
        self.duration_ms = duration_ms
        #: Distinguishes this snackbar from the next one, so a late tap on an
        #: old "Undo" never runs the action of the snackbar that replaced it.
        self.token = token
        self._app = app
        self._timer: TimerHandle | None = None
        self._visible = True

    @property
    def visible(self) -> bool:
        """Whether the snackbar is still on screen."""
        return self._visible

    def press(self) -> None:
        """Run the action (what tapping the button does) and hide the snackbar."""
        if not self._visible:
            return
        callback = self.on_action
        self.dismiss()
        if callback is not None:
            callback()

    def dismiss(self) -> None:
        """Hide the snackbar now."""
        if not self._visible:
            return
        self._visible = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        app = self._app
        if app is not None:
            app._snackbar_closed(self)

    def _retire(self) -> None:
        """Replaced by a newer snackbar: hide without asking for a redraw."""
        self._visible = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def to_dict(self) -> dict[str, Any]:
        """The ``tree["snackbar"]`` payload renderers draw."""
        return {
            "id": SNACKBAR_ID,
            "message": self.message,
            "action": self.action or "",
            "token": self.token,
            "duration_ms": self.duration_ms,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        state = "visible" if self._visible else "hidden"
        return f"<Snackbar {self.message!r} action={self.action!r} {state}>"
