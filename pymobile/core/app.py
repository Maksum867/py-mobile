"""The application object.

:class:`App` is the single entry point an application author touches. It wires
together the platform bridge, the feature APIs, the event bus and navigation —
but it owns none of their logic, so each part stays independently testable.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from ..errors import PyMobileError
from ..logging import configure, get_logger
from .api.notifications import Notifications
from .api.permissions import Permission, PermissionManager
from .api.vibration import Vibration
from .bridge import Bridge, get_bridge
from .events import EventBus, Subscription
from .i18n import translations
from .net.http import HttpClient
from .platform import current_platform
from .scheduler import Scheduler, TimerHandle
from .ui.screen import Navigator, Screen, ScreenT

__all__ = ["App"]

_log = get_logger("app")

#: The application started most recently, or None. Developer tooling (the
#: interactive preview, the reloader) needs a handle on the running app
#: without dictating where the author keeps theirs.
_current: App | None = None


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
        auto_render: bool = True,
    ) -> None:
        self.name = name
        self.bridge: Bridge = bridge or get_bridge()
        self.events = EventBus()
        self.navigator = Navigator(self, on_change=self._on_screen_change)
        self.notifications = Notifications(self.bridge, channel_name=name)
        self.vibration = Vibration(self.bridge)
        self.permissions = PermissionManager(self.bridge)
        self.http = HttpClient(base_url=base_url)
        self._scheduler = Scheduler()
        self._log_level = log_level
        self._running = False
        #: When true (the default) a widget change redraws the screen by itself.
        self.auto_render = auto_render
        self._render_scheduled = False
        self._render_depth = 0
        self._render_lock = threading.Lock()
        # Rebuild the visible screen when the language changes: t() is called
        # inside build(), so the old text is already baked into the widgets.
        self._unsubscribe_language = translations.subscribe(self._on_language_change)

    @staticmethod
    def current() -> App | None:
        """The application currently running in this process, if any."""
        return _current

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
        global _current
        configure(self._log_level)
        _log.info("starting %s on %s (bridge=%s)", self.name, self.platform, self.bridge.name)
        self._running = True
        _current = self
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
                self.handle_ui_event(widget_id, kind, value)
            except Exception:
                _log.exception("error handling %s on %s", kind, widget_id)
        _log.info("event loop finished")

    def handle_ui_event(self, widget_id: str, kind: str, value: str) -> None:
        """Apply one UI interaction and draw a single frame for it.

        Every front end — the device event loop, the Tk window, the browser
        preview — funnels through here, so the batching lives inside rather
        than being something each caller has to remember to wrap.
        """
        with self.batch():
            self._handle_ui_event(widget_id, kind, value)

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
        """Shut the app down and release subscriptions.

        Pending timers are always cancelled, even when ``run`` was never
        called, so a partially initialised app cannot leak background work.
        """
        global _current
        self._scheduler.cancel_all()
        if not self._running:
            return
        self._running = False
        self._unsubscribe_language()
        if _current is self:
            _current = None
        self.events.emit("app:stop", source=self.name)
        self.events.clear()
        _log.info("stopped %s", self.name)

    # -- ui ----------------------------------------------------------------
    def render(self) -> dict[str, Any] | None:
        """Serialise the visible screen and hand it to the bridge.

        Calling this by hand is no longer required — widgets schedule their own
        redraws — but it stays available for the rare case that needs a frame
        pushed out right now.
        """
        screen = self.navigator.current
        if screen is None:
            return None
        with self._render_lock:
            self._render_scheduled = False
        tree = screen.to_dict()
        self.bridge.render(tree)
        self.events.emit("app:render", source=screen.title, tree=tree)
        return tree

    def schedule_render(self) -> None:
        """Request a redraw of the visible screen, coalescing repeats.

        This is what a widget calls when it changes. Inside a
        :meth:`batch` block — and while a UI callback is running — the redraws
        pile up into a single frame, so a handler that updates six labels
        still renders once.
        """
        if not self.auto_render or not self._running:
            return
        with self._render_lock:
            if self._render_depth > 0:
                self._render_scheduled = True
                return
        self.render()

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Group many widget updates into a single redraw.

        ::

            with app.batch():
                for label, value in zip(labels, values):
                    label.text = value
            # one render happens here

        Nesting is allowed; only the outermost block flushes.
        """
        with self._render_lock:
            self._render_depth += 1
        try:
            yield
        finally:
            with self._render_lock:
                self._render_depth -= 1
                flush = self._render_depth == 0 and self._render_scheduled
            if flush:
                self.render()

    def push(self, screen: ScreenT) -> ScreenT:
        """Navigate to a new screen."""
        return self.navigator.push(screen)

    def pop(self) -> Screen | None:
        """Go back one screen; ``None`` when already at the root."""
        return self.navigator.pop()

    # -- timers ------------------------------------------------------------
    def set_interval(
        self,
        interval_ms: int,
        callback: Callable[[], None],
        *,
        drift_correction: bool = True,
    ) -> TimerHandle:
        """Run ``callback`` every ``interval_ms`` until the handle is cancelled.

        The callback fires on a background thread on every platform, so a
        clock or poller needs no ``threading`` boilerplate. All timers are
        cancelled automatically by :meth:`stop`.

        Ticks are aligned to a fixed timeline, so the time spent inside the
        callback does not accumulate into a visible lag — a one-second timer
        is still on the second after an hour. Pass ``drift_correction=False``
        to wait a fixed pause between runs instead.
        """
        return self._scheduler.set_interval(
            interval_ms, callback, drift_correction=drift_correction
        )

    def set_timeout(self, delay_ms: int, callback: Callable[[], None]) -> TimerHandle:
        """Run ``callback`` once after ``delay_ms`` milliseconds."""
        return self._scheduler.set_timeout(delay_ms, callback)

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

    def on(
        self,
        event: str,
        handler: Callable[[Any], None],
        *,
        screen: Screen | None = None,
    ) -> Subscription:
        """Subscribe to an application event.

        Pass ``screen=`` to tie the subscription to a screen's lifetime: it is
        cancelled when that screen unmounts, which prevents the handler of a
        popped screen from firing (and from keeping the screen alive). Inside
        a screen, ``self.on(...)`` does the same thing with less typing.
        """
        subscription = self.events.on(event, handler)
        if screen is not None:
            screen._subscriptions.append(subscription)
        return subscription

    # -- internals ---------------------------------------------------------
    def _on_language_change(self, language: str) -> None:
        """Rebuild the visible screen so new translations are picked up."""
        screen = self.navigator.current
        if screen is None or not self._running:
            return
        self.events.emit("app:language", source=language)
        screen.refresh()

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
