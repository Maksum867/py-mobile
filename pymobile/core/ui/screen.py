"""Screens and navigation.

A :class:`Screen` builds a widget tree and receives lifecycle callbacks. The
:class:`Navigator` keeps a stack of screens and drives those callbacks, which
keeps navigation logic out of the app object.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from ...errors import PyMobileError
from ...logging import get_logger
from .widget import Widget

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..app import App

__all__ = ["Screen", "Navigator"]

_log = get_logger("ui.screen")


class Screen:
    """One full-window view.

    Subclasses override :meth:`build` to return the widget tree. Lifecycle
    hooks (:meth:`on_mount`, :meth:`on_show`, :meth:`on_hide`,
    :meth:`on_unmount`) are optional.
    """

    #: Title shown in the action bar; defaults to the class name.
    title: str = ""

    def __init__(self, title: str | None = None) -> None:
        self.title = title or self.title or type(self).__name__
        self.app: App | None = None
        self._root: Widget | None = None
        self._mounted = False

    # -- construction ------------------------------------------------------
    def build(self) -> Widget:
        """Return the widget tree for this screen."""
        raise NotImplementedError(f"{type(self).__name__} must implement build()")

    @property
    def root(self) -> Widget:
        """The built widget tree, constructed on first access."""
        if self._root is None:
            self._root = self.build()
        return self._root

    @property
    def mounted(self) -> bool:
        """Whether the screen is currently attached to a navigator."""
        return self._mounted

    def refresh(self) -> None:
        """Rebuild the tree and re-render if this screen is on top."""
        self._root = None
        if self.app is not None and self.app.navigator.current is self:
            self.app.render()

    def find(self, widget_id: str) -> Widget | None:
        """Look up a widget by id inside this screen."""
        return self.root.find(widget_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the screen (title + widget tree)."""
        return {"screen": self.title, **self.root.to_dict()}

    # -- lifecycle ---------------------------------------------------------
    def on_mount(self) -> None:
        """Called once when the screen is pushed onto the navigator."""

    def on_show(self) -> None:
        """Called every time the screen becomes visible."""

    def on_hide(self) -> None:
        """Called when another screen covers this one."""

    def on_unmount(self) -> None:
        """Called once when the screen is popped."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Screen {self.title!r}>"


class Navigator:
    """A stack of screens with lifecycle dispatch."""

    __slots__ = ("_stack", "_app", "_on_change")

    def __init__(
        self, app: App | None = None, on_change: Callable[[Screen | None], None] | None = None
    ) -> None:
        self._stack: list[Screen] = []
        self._app = app
        self._on_change = on_change

    @property
    def current(self) -> Screen | None:
        """The visible screen, or ``None`` when the stack is empty."""
        return self._stack[-1] if self._stack else None

    @property
    def stack(self) -> Sequence[Screen]:
        """Immutable view of the screen stack, bottom first."""
        return tuple(self._stack)

    @property
    def depth(self) -> int:
        """Number of screens on the stack."""
        return len(self._stack)

    def push(self, screen: Screen) -> Screen:
        """Show ``screen`` on top of the stack."""
        if screen in self._stack:
            raise PyMobileError(
                f"screen {screen.title!r} is already on the stack",
                hint="Create a new screen instance instead of pushing the same object twice.",
            )
        previous = self.current
        if previous is not None:
            previous.on_hide()
        screen.app = self._app
        self._stack.append(screen)
        if not screen._mounted:
            screen._mounted = True
            screen.on_mount()
        screen.on_show()
        _log.debug("push %s (depth=%d)", screen.title, self.depth)
        self._notify()
        return screen

    def pop(self) -> Screen | None:
        """Remove the top screen and reveal the one below it."""
        if len(self._stack) <= 1:
            return None
        screen = self._stack.pop()
        screen.on_hide()
        screen._mounted = False
        screen.on_unmount()
        screen.app = None
        current = self.current
        if current is not None:
            current.on_show()
        _log.debug("pop %s (depth=%d)", screen.title, self.depth)
        self._notify()
        return screen

    def replace(self, screen: Screen) -> Screen:
        """Swap the top screen for ``screen``."""
        if self._stack:
            top = self._stack.pop()
            top.on_hide()
            top._mounted = False
            top.on_unmount()
            top.app = None
        return self.push(screen)

    def reset(self, screen: Screen) -> Screen:
        """Clear the stack and start again from ``screen``."""
        while self._stack:
            top = self._stack.pop()
            top._mounted = False
            top.on_unmount()
            top.app = None
        return self.push(screen)

    def _notify(self) -> None:
        """Tell the app that the visible screen changed."""
        if self._on_change is not None:
            self._on_change(self.current)
