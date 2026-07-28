"""Styling primitives.

Deliberately small: a handful of layout and colour attributes that map cleanly
onto Android view properties. Unset fields are dropped during serialisation so
the native side can apply its own defaults.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from typing import Any

__all__ = ["Style", "Color", "Align", "EdgeInsets"]

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class Color:
    """Named colours plus validation for ``#RGB``/``#RRGGBB``/``#AARRGGBB``."""

    PRIMARY = "#3F51B5"
    ACCENT = "#FF4081"
    BACKGROUND = "#FFFFFF"
    SURFACE = "#F5F5F5"
    TEXT = "#212121"
    TEXT_MUTED = "#757575"
    SUCCESS = "#2E7D32"
    WARNING = "#F9A825"
    ERROR = "#C62828"
    TRANSPARENT = "#00000000"

    @staticmethod
    def validate(value: str) -> str:
        """Return the colour unchanged, or raise :class:`ValueError`."""
        if not _HEX_COLOR.match(value):
            raise ValueError(
                f"invalid color {value!r}; expected #RGB, #RRGGBB or #AARRGGBB"
            )
        return value.upper()


class Align:
    """Alignment constants shared by layouts and text."""

    START = "start"
    CENTER = "center"
    END = "end"
    SPACE_BETWEEN = "space_between"


@dataclass(frozen=True, slots=True)
class EdgeInsets:
    """Padding or margin in density-independent pixels."""

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    @classmethod
    def all(cls, value: int) -> EdgeInsets:
        """The same inset on every side."""
        return cls(value, value, value, value)

    @classmethod
    def symmetric(cls, *, horizontal: int = 0, vertical: int = 0) -> EdgeInsets:
        """Separate horizontal and vertical insets."""
        return cls(horizontal, vertical, horizontal, vertical)

    def to_list(self) -> list[int]:
        """``[left, top, right, bottom]``."""
        return [self.left, self.top, self.right, self.bottom]

    def __bool__(self) -> bool:
        return any(self.to_list())


@dataclass(frozen=True, slots=True)
class Style:
    """Visual attributes of a widget; ``None`` means "inherit the default"."""

    background: str | None = None
    color: str | None = None
    font_size: int | None = None
    bold: bool = False
    italic: bool = False
    padding: EdgeInsets | None = None
    margin: EdgeInsets | None = None
    width: int | str | None = None
    height: int | str | None = None
    align: str | None = None
    corner_radius: int | None = None
    elevation: int | None = None
    weight: float | None = None

    def __post_init__(self) -> None:
        for value in (self.background, self.color):
            if value is not None:
                Color.validate(value)
        if self.font_size is not None and self.font_size <= 0:
            raise ValueError("font_size must be positive")

    def merge(self, **overrides: Any) -> Style:
        """Return a copy with some attributes replaced."""
        return replace(self, **overrides)

    def to_dict(self) -> dict[str, Any]:
        """Serialise, skipping unset and falsy-default fields."""
        raw = asdict(self)
        result: dict[str, Any] = {}
        for key, value in raw.items():
            if value is None or value is False:
                continue
            if key in ("padding", "margin"):
                insets = getattr(self, key)
                if insets:
                    result[key] = insets.to_list()
                continue
            result[key] = value
        return result
