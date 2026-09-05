"""A virtualised list for many rows without rendering them all at once.

A plain ``Column`` materialises every child, which is fine for a dozen rows but
wastes memory and slows the renderer for hundreds or thousands. :class:`List`
is a data-driven container: you give it a number of items and a ``builder``
callback that produces the widget for each index, and it only instantiates the
rows near the viewport (in the desktop/text preview it renders the first
``visible_count`` rows). The Android renderer maps it to a ``RecyclerView``-style
lazy container.

Because the rows are built lazily, ``List`` cannot be patched in place like a
static tree — every structural change should call :meth:`List.refresh` (or the
owning screen's ``refresh``) so the visible window is rebuilt.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .widget import Container, Widget, callback_name

__all__ = ["List", "ListTile"]


class List(Container):
    """A virtualised list of ``item_count`` rows built by ``builder``.

    ``builder(index) -> Widget`` returns the widget for row ``index``. ``spacing``
    separates rows. ``visible_count`` bounds how many rows are realised at once
    (the desktop renderer shows exactly that many), which is the whole point of
    the component. ``item_count`` may change; call :meth:`refresh` to rebuild.
    """

    type_name = "List"
    __slots__ = ("_builder", "item_count", "spacing", "visible_count")

    def __init__(
        self,
        item_count: int = 0,
        *,
        builder: Callable[[int], Widget] | None = None,
        spacing: int = 0,
        visible_count: int = 20,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if item_count < 0:
            raise ValueError("item_count must not be negative")
        if spacing < 0:
            raise ValueError("spacing must not be negative")
        if visible_count < 1:
            raise ValueError("visible_count must be >= 1")
        self._builder = builder
        self.item_count = item_count
        self.spacing = spacing
        self.visible_count = visible_count
        self._build_window()

    def _build_window(self) -> None:
        """Realise the visible window of children (first ``visible_count`` rows)."""
        super().clear()
        for index in range(min(self.item_count, self.visible_count)):
            row = self._row_for(index)
            super().add(row)

    def _row_for(self, index: int) -> Widget:
        if self._builder is None:
            return ListTile(f"Item {index + 1}")
        return self._builder(index)

    # Override add/clear so users cannot disturb the virtualised children.
    def add(self, child: Widget) -> Widget:  # pragma: no cover - defensive
        raise ValueError("List is virtualised; set item_count and rebuild instead")

    def clear(self) -> None:  # pragma: no cover - defensive
        raise ValueError("List is virtualised; set item_count and rebuild instead")

    def refresh(self) -> None:
        """Rebuild the visible window after ``item_count``/``builder`` changed."""
        self._build_window()
        self.invalidate()

    def scroll_to(self, index: int) -> None:
        """No-op on the desktop (the native renderer scrolls the real list)."""
        if not 0 <= index < self.item_count:
            raise IndexError(index)

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "item_count": self.item_count,
            "spacing": self.spacing,
            "visible_count": self.visible_count,
        }


class ListTile(Widget):
    """A simple row with a title and optional subtitle/trailing text.

    A convenience building block for :class:`List` (and usable standalone).

    ``on_long_press`` gives a row a second action — delete, archive, "edit
    this one" — which a list otherwise cannot offer without a permanent button
    on every row::

        ListTile(title=item.name, on_press=self.toggle, on_long_press=self.delete)

    The device vibrates on the long press, as Android users expect.
    """

    type_name = "ListTile"
    __slots__ = ("_title", "subtitle", "trailing", "on_press", "on_long_press")

    def __init__(
        self,
        title: str = "",
        *,
        subtitle: str = "",
        trailing: str = "",
        on_press: Callable[[], None] | None = None,
        on_long_press: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self.subtitle = subtitle
        self.trailing = trailing
        self.on_press = on_press
        self.on_long_press = on_long_press

    @property
    def title(self) -> str:
        """The row's title; assigning to it schedules a redraw."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        if value != self._title:
            self._title = value
            self.invalidate()

    def set_title(self, value: str) -> None:
        """Replace the title."""
        self.title = value

    def press(self) -> None:
        """Simulate a tap; ignored while disabled."""
        if self.enabled and self.on_press is not None:
            self.on_press()

    def long_press(self) -> None:
        """Simulate a long press; ignored while disabled."""
        if self.enabled and self.on_long_press is not None:
            self.on_long_press()

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "title": self._title,
            "subtitle": self.subtitle,
            "trailing": self.trailing,
            "on_press": callback_name(self.on_press),
            "on_long_press": callback_name(self.on_long_press),
            "long_pressable": self.on_long_press is not None,
        }
