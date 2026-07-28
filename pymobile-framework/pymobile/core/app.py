"""The application object.

:class:`App` is the single entry point an application author touches. It wires
together the platform bridge, the feature APIs, the event bus and navigation —
but it owns none of their logic, so each part stays independently testable.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..errors import PyMobileError
from ..logging import configure, get_logger
from .api.notifications import Notifications
from .api.permissions import Permission, PermissionManager
from .api.vibration import Vibration
from .bridge import Bridge, get_bridge
from .events import EventBus, Subscription
from .net.http import HttpClient
from .platform import current_platform
from .ui.screen import Navigator, Screen

__all__ = ["App"]

_log = get_logger("app")


class App:
    """Root object of a PyMobile application.

    Example::

        app = App("Demo")
        app.run(HomeScreen())
    """

    def __init__(
        self,
        name: str = "PyMobile App",
        *,
        bridge: Bridge | None = None,
        base_url: str = "",
        log_level: str = "info",
    ) -> None:
        self.name = name
        self.bridge: Bridge = bridge or get_bridge()
        self.events = EventBus()
        self.navigator = Navigator(self, on_change=self._on_screen_change)
        self.notifications = Notifications(self.bridge, channel_name=name)
        self.vibration = Vibration(self.bridge)
        self.permissions = PermissionManager(self.bridge)
        self.http = HttpClient(base_url=base_url)
        self._log_level = log_level
        self._running = False

    # -- properties --------------------------------------------------------
    @property
    def platform(self) -> str:
        """Name of the runtime platform (``"android"`` or ``"desktop"``)."""
        return str(current_platform())

    @property
    def running(self) -> bool:
        """Whether :meth:`run` has been called and :meth:`stop` has not."""
        return self._running

    @property
    def screen(self) -> Screen | None:
        """The currently visible screen."""
        return self.navigator.current

    # -- lifecycle ---------------------------------------------------------
    def run(self, screen: Screen) -> None:
        """Start the app with ``screen`` as the initial view.

        On a device this blocks in the UI event loop until the activity is
        destroyed; on a desktop it returns once the first screen is rendered,
        which keeps previews and tests non-blocking.
        """
        configure(self._log_level)
        _log.info("starting %s on %s (bridge=%s)", self.name, self.platform, self.bridge.name)
        self._running = True
        self.events.emit("app:start", source=self.name)
        self.navigator.reset(screen)

        if hasattr(self.bridge, "next_event"):
            self._event_loop()

    def _event_loop(self) -> None:
        """Dispatch UI events until the platform asks us to stop.

        Widgets are looked up by id in the current screen, so a callback always
        acts on the widget the user actually touched.
        """
        next_event = self.bridge.next_event  # type: ignore[attr-defined]
        _log.info("entering the UI event loop")
        while self._running:
            event = next_event(-1)
            if event is None:
                break
            widget_id, kind, value = event
            try:
                self._handle_ui_event(widget_id, kind, value)
            except Exception:
                _log.exception("error handling %s on %s", kind, widget_id)
        _log.info("event loop finished")

    def _handle_ui_event(self, widget_id: str, kind: str, value: str) -> None:
        """Apply one UI event to the widget it belongs to."""
        if kind == "back":
            if self.navigator.depth > 1:
                self.pop()
            else:
                self.stop()
            return

        screen = self.navigator.current
        if screen is None:
            return
        widget = screen.find(widget_id)
        if widget is None:
            _log.debug("event for unknown widget %r", widget_id)
            return

        if kind == "press" and hasattr(widget, "press"):
            widget.press()
        elif kind == "change" and hasattr(widget, "set_value"):
            widget.set_value(value)
        elif kind == "toggle" and hasattr(widget, "set_checked"):
            widget.set_checked(value == "true")
        self.events.emit(f"ui:{kind}", source=widget_id, value=value)

    def stop(self) -> None:
        """Shut the app down and release subscriptions."""
        if not self._running:
            return
        self._running = False
        self.events.emit("app:stop", source=self.name)
        self.events.clear()
        _log.info("stopped %s", self.name)

    # -- ui ----------------------------------------------------------------
    def render(self) -> dict[str, Any] | None:
        """Serialise the visible screen and hand it to the bridge."""
        screen = self.navigator.current
        if screen is None:
            return None
        tree = screen.to_dict()
        self.bridge.render(tree)
        self.events.emit("app:render", source=screen.title, tree=tree)
        return tree

    def push(self, screen: Screen) -> Screen:
        """Navigate to a new screen."""
        return self.navigator.push(screen)

    def pop(self) -> Screen | None:
        """Go back one screen; ``None`` when already at the root."""
        return self.navigator.pop()

    def toast(self, message: str, *, long: bool = False) -> None:
        """Show a short platform message."""
        self.bridge.toast(message, long)

    # -- convenience -------------------------------------------------------
    def notify(self, title: str, body: str = "", **kwargs: Any) -> int:
        """Post a local notification; returns its id."""
        return self.notifications.notify(title, body, **kwargs)

    def vibrate(self, milliseconds: int = 100) -> None:
        """Vibrate the device once."""
        self.vibration.vibrate(milliseconds)

    def require_permissions(self, *permissions: str | Permission) -> None:
        """Request permissions and fail loudly if any is denied."""
        self.permissions.require(*permissions)

    def on(self, event: str, handler: Callable[[Any], None]) -> Subscription:
        """Subscribe to an application event."""
        return self.events.on(event, handler)

    # -- internals ---------------------------------------------------------
    def _on_screen_change(self, screen: Screen | None) -> None:
        """Re-render whenever the navigator changes the visible screen."""
        if screen is None:
            return
        if not self._running:
            raise PyMobileError(
                "Navigation happened before App.run()",
                hint="Call app.run(FirstScreen()) to start the application.",
            )
        self.events.emit("screen:change", source=screen.title)
        self.render()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<App {self.name!r} platform={self.platform}>"
