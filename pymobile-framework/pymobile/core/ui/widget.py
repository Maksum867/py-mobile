"""Widget foundation.

A widget is a declarative description of a piece of UI, not a native view.
Trees are serialised with :meth:`Widget.to_dict` and handed to the bridge,
which owns the native rendering. Keeping widgets pure data makes the UI layer
trivially testable and lets the native renderer evolve independently.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from itertools import count
from typing import Any

from .style import Style

__all__ = ["Widget", "Container"]

_ids = count(1)


class Widget:
    """Base class for every UI component."""

    #: Type name used in the serialised tree; defaults to the class name.
    type_name: str = "Widget"

    __slots__ = ("id", "style", "visible", "enabled", "_parent", "_props")

    def __init__(
        self,
        *,
        id: str | None = None,
        style: Style | None = None,
        visible: bool = True,
        enabled: bool = True,
        **props: Any,
    ) -> None:
        self.id = id or f"{type(self).__name__.lower()}-{next(_ids)}"
        self.style = style or Style()
        self.visible = visible
        self.enabled = enabled
        self._parent: Widget | None = None
        self._props: dict[str, Any] = props

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

    # -- properties --------------------------------------------------------
    def props(self) -> dict[str, Any]:
        """Serialisable properties of this widget; subclasses extend this."""
        return dict(self._props)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the widget subtree into a plain dictionary."""
        node: dict[str, Any] = {
            "type": self.type_name,
            "id": self.id,
            "visible": self.visible,
            "enabled": self.enabled,
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
        if child._parent is not None:
            raise ValueError(f"widget {child.id!r} already has a parent")
        child._parent = self
        self._children.append(child)
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

    def clear(self) -> None:
        """Detach every child."""
        for child in self._children:
            child._parent = None
        self._children.clear()

    def __len__(self) -> int:
        return len(self._children)

    def __iter__(self) -> Iterator[Widget]:
        return iter(self._children)


def callback_name(handler: Callable[..., Any] | None) -> str | None:
    """Stable identifier for a callback, used when serialising handlers."""
    if handler is None:
        return None
    return getattr(handler, "__name__", repr(handler))
