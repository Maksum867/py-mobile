"""Layout containers.

Three primitives cover the vast majority of mobile screens: a vertical stack,
a horizontal stack and a scrollable region. Anything more exotic can be built
by composing them, or by subclassing :class:`~pymobile.core.ui.widget.Container`.
"""

from __future__ import annotations

from typing import Any

from .style import Align
from .widget import Container, Widget

__all__ = ["Column", "Row", "ScrollView", "Stack"]


class _Linear(Container):
    """Shared behaviour of :class:`Column` and :class:`Row`."""

    __slots__ = ("spacing", "align")

    def __init__(
        self,
        *children: Widget,
        spacing: int = 0,
        align: str = Align.START,
        **kwargs: Any,
    ) -> None:
        if spacing < 0:
            raise ValueError("spacing must not be negative")
        self.spacing = spacing
        self.align = align
        super().__init__(*children, **kwargs)

    def props(self) -> dict[str, Any]:
        return {**super().props(), "spacing": self.spacing, "align": self.align}


class Column(_Linear):
    """Stacks children vertically."""

    type_name = "Column"
    __slots__ = ()


class Row(_Linear):
    """Stacks children horizontally."""

    type_name = "Row"
    __slots__ = ()


class ScrollView(Container):
    """Makes its content scrollable."""

    type_name = "ScrollView"
    __slots__ = ("horizontal",)

    def __init__(self, *children: Widget, horizontal: bool = False, **kwargs: Any) -> None:
        self.horizontal = horizontal
        super().__init__(*children, **kwargs)

    def props(self) -> dict[str, Any]:
        return {**super().props(), "horizontal": self.horizontal}


class Stack(Container):
    """Overlays children on top of each other (last child on top)."""

    type_name = "Stack"
    __slots__ = ()
