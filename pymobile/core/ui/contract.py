"""Public, typed contract for a serialised PyMobile widget tree."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

__all__ = ["WidgetNode", "WidgetProps", "StyleNode", "SerializedValue"]

SerializedValue: TypeAlias = str | int | float | bool | list[object] | dict[str, object] | None
WidgetProps: TypeAlias = dict[str, SerializedValue]
StyleNode: TypeAlias = dict[str, SerializedValue]


class WidgetNode(TypedDict, total=False):
    """The stable renderer boundary emitted by :meth:`Widget.to_dict`.

    ``type``, ``id``, ``visible``, ``enabled`` and ``props`` are always emitted;
    ``style`` and ``children`` are omitted when empty. ``total=False`` keeps the
    contract compatible with Python 3.10 without a typing_extensions runtime
    dependency.
    """

    type: str
    id: str
    visible: bool
    enabled: bool
    props: WidgetProps
    style: StyleNode
    children: list[WidgetNode]
