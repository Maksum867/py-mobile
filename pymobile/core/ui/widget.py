"""Widget foundation.

A widget is a declarative description of a piece of UI, not a native view.
Trees are serialised with :meth:`Widget.to_dict` and handed to the bridge,
which owns the native rendering. Keeping widgets pure data makes the UI layer
trivially testable and lets the native renderer evolve independently.

Mutating a widget that is on screen schedules a re-render by itself: every
setter funnels through :meth:`Widget.invalidate`, which walks up to the screen
and asks the application to redraw. Forgetting ``app.render()`` is therefore no
longer a class of bug — see :mod:`pymobile.core.app` for how the redraws are
coalesced.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from itertools import count
from typing import TYPE_CHECKING, Any

from .contract import SerializedValue, WidgetNode, WidgetProps
from .style import Style

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .screen import Screen

__all__ = ["Widget", "Container", "auto_id", "reset_id_counter", "widget_scope"]

#: Fallback counter, used when no screen scope is active.
_ids = count(1)

#: Per-screen counters, so ids do not shift when an unrelated screen changes.
#: A ContextVar keeps concurrent builds (threads, tests) from sharing state.
_scope: ContextVar[dict[str, count[int]] | None] = ContextVar("pymobile_widget_scope", default=None)


def reset_id_counter() -> None:
    """Restart the anonymous-widget counter (used by tests)."""
    global _ids
    _ids = count(1)


def auto_id(prefix: str) -> str:
    """Return a unique id of the form ``prefix-N``.

    Inside a :func:`widget_scope` the number is local to that screen and
    restarts per widget type, so adding a Label at the top of one screen no
    longer renumbers every widget in the application.
    """
    counters = _scope.get()
    if counters is None:
        return f"{prefix}-{next(_ids)}"
    counter = counters.get(prefix)
    if counter is None:
        counter = count(1)
        counters[prefix] = counter
    return f"{prefix}-{next(counter)}"


@contextmanager
def widget_scope(owner: object = None) -> Iterator[None]:
    """Number widgets built inside the block per screen instead of globally."""
    token = _scope.set({})
    try:
        yield
    finally:
        _scope.reset(token)


def _serialise_value(value: object) -> SerializedValue:
    """Validate extension props at the public renderer boundary."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _serialise_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialise_value(item) for item in value]
    raise TypeError(
        f"widget extension props must contain only JSON-like values (got {type(value).__name__})"
    )


class Widget:
    """Base class for every UI component."""

    #: Type name used in the serialised tree; defaults to the class name.
    type_name: str = "Widget"

    __slots__ = (
        "id",
        "style",
        "_visible",
        "_enabled",
        "_parent",
        "_props",
        "_screen",
        "_explicit_id",
    )

    def __init__(
        self,
        *,
        id: str | None = None,
        style: Style | None = None,
        visible: bool = True,
        enabled: bool = True,
        **props: Any,
    ) -> None:
        self._explicit_id = id is not None
        self.id = id or auto_id(type(self).__name__.lower())
        self.style = style or Style()
        self._visible = visible
        self._enabled = enabled
        self._parent: Widget | None = None
        self._screen: Screen | None = None
        self._props: WidgetProps = {}
        for name, value in props.items():
            self.set_prop(name, value, invalidate=False)

    # -- tree --------------------------------------------------------------
    @property
    def parent(self) -> Widget | None:
        """The widget this one is attached to, if any."""
        return self._parent

    @property
    def children(self) -> Sequence[Widget]:
        """Child widgets; leaf widgets return an empty tuple."""
        return ()

    def walk(self) -> Iterator[Widget]:
        """Depth-first iteration over this widget and its descendants."""
        yield self
        for child in self.children:
            yield from child.walk()

    def find(self, widget_id: str) -> Widget | None:
        """Find a descendant (or self) by id."""
        return next((widget for widget in self.walk() if widget.id == widget_id), None)

    # -- reactivity --------------------------------------------------------
    @property
    def screen(self) -> Screen | None:
        """The screen this widget belongs to, if it is attached to one.

        The link is stored on the root widget only, so this walks up the
        parent chain — a handful of pointer hops on trees of realistic depth.
        """
        node: Widget = self
        while node._parent is not None:
            node = node._parent
        return node._screen

    def invalidate(self) -> None:
        """Mark this widget as changed and schedule a redraw.

        Safe to call at any time: while the widget is detached, during
        ``build()``, or before the app is running. In those cases there is
        nothing on screen yet and the call does nothing.
        """
        screen = self.screen
        if screen is not None:
            screen.invalidate()

    # -- properties --------------------------------------------------------
    @property
    def visible(self) -> bool:
        """Whether the widget is drawn; hidden widgets keep their place free."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if value != self._visible:
            self._visible = value
            self.invalidate()

    @property
    def enabled(self) -> bool:
        """Whether the widget reacts to input."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        if value != self._enabled:
            self._enabled = value
            self.invalidate()

    def set_prop(self, name: str, value: object, *, invalidate: bool = True) -> None:
        """Set a validated extension prop for a custom widget/renderer.

        Extension props are deliberately JSON-like, so every renderer receives
        the same portable data rather than a Python callback or host object.
        """
        if not name or not name.isidentifier() or name.startswith("_"):
            raise ValueError("widget extension prop names must be public identifiers")
        serialised = _serialise_value(value)
        if self._props.get(name) != serialised:
            self._props[name] = serialised
            if invalidate:
                self.invalidate()

    def props(self) -> WidgetProps:
        """Serialisable properties of this widget; subclasses extend this."""
        return dict(self._props)

    def to_dict(self) -> WidgetNode:
        """Serialise the widget subtree into the public renderer contract."""
        node: WidgetNode = {
            "type": self.type_name,
            "id": self.id,
            "visible": self._visible,
            "enabled": self._enabled,
            "props": self.props(),
        }
        style = self.style.to_dict()
        if style:
            node["style"] = style
        children = [child.to_dict() for child in self.children]
        if children:
            node["children"] = children
        return node

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} id={self.id!r}>"


class Container(Widget):
    """A widget that owns and lays out children."""

    type_name = "Container"

    __slots__ = ("_children",)

    def __init__(self, *children: Widget, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._children: list[Widget] = []
        self.extend(children)

    @property
    def children(self) -> Sequence[Widget]:
        """Immutable view over the child list."""
        return tuple(self._children)

    def add(self, child: Widget) -> Widget:
        """Append a child and return it (so calls can be chained/assigned)."""
        if child is self:
            raise ValueError("a container cannot contain itself")
        # Reject attaching an ancestor below its own descendant. Without this,
        # ``root.add(child); child.add(root)`` forms a cycle and recursion in
        # walk()/to_dict() never terminates.
        ancestor: Widget | None = self
        while ancestor is not None:
            if ancestor is child:
                raise ValueError("a container cannot contain one of its ancestors")
            ancestor = ancestor._parent
        if child._parent is not None:
            raise ValueError(f"widget {child.id!r} already has a parent")
        child._parent = self
        self._children.append(child)
        self.invalidate()
        return child

    def extend(self, children: Sequence[Widget]) -> None:
        """Append several children."""
        for child in children:
            self.add(child)

    def remove(self, child: Widget) -> None:
        """Detach a child (no error if it is not present)."""
        if child in self._children:
            self._children.remove(child)
            child._parent = None
            self.invalidate()

    def clear(self) -> None:
        """Detach every child."""
        if not self._children:
            return
        for child in self._children:
            child._parent = None
        self._children.clear()
        self.invalidate()

    def __len__(self) -> int:
        return len(self._children)

    def __iter__(self) -> Iterator[Widget]:
        return iter(self._children)


def callback_name(handler: Callable[..., Any] | None) -> str | None:
    """Stable identifier for a callback, used when serialising handlers."""
    if handler is None:
        return None
    return getattr(handler, "__name__", repr(handler))
