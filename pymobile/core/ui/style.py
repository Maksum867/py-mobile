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

#: Named sizes a Style width/height accepts (mirrors the native renderer).
_DIMENSION_WORDS = frozenset({"match", "fill", "wrap", "match_parent", "wrap_content"})


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
    """Alignment constants shared by layouts and text.

    ``START``/``CENTER``/``END``/``SPACE_BETWEEN`` position children along a
    container's main axis. The cross axis (how a Row's children line up
    vertically, or how wide a Column's children are) uses the same names plus
    :attr:`STRETCH`, and is set through ``cross_align``.
    """

    START = "start"
    CENTER = "center"
    END = "end"
    SPACE_BETWEEN = "space_between"
    #: Cross-axis only: fill the container across the axis.
    STRETCH = "stretch"

    #: Values accepted by ``align`` (main axis).
    MAIN = (START, CENTER, END, SPACE_BETWEEN)
    #: Values accepted by ``cross_align``.
    CROSS = (START, CENTER, END, STRETCH)

    @classmethod
    def validate_main(cls, value: str) -> str:
        """Return a valid ``align`` value, or raise :class:`ValueError`."""
        if value not in cls.MAIN:
            raise ValueError(
                f"invalid align {value!r}; expected one of {', '.join(cls.MAIN)}"
            )
        return value

    @classmethod
    def validate_cross(cls, value: str) -> str:
        """Return a valid ``cross_align`` value, or raise :class:`ValueError`."""
        if value not in cls.CROSS:
            raise ValueError(
                f"invalid cross_align {value!r}; expected one of {', '.join(cls.CROSS)}"
            )
        return value


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
    """Visual attributes of a widget; ``None`` means "inherit the default".

    Besides the fixed ``width``/``height`` there is a set of constraints —
    ``min_width``, ``max_width``, ``min_height``, ``max_height`` and
    ``aspect_ratio`` — for the common "at least this big, never bigger than
    that" card, and for images that must keep a 16:9 shape.
    """

    background: str | None = None
    color: str | None = None
    font_size: int | None = None
    bold: bool = False
    italic: bool = False
    padding: EdgeInsets | None = None
    margin: EdgeInsets | None = None
    width: int | str | None = None
    height: int | str | None = None
    min_width: int | None = None
    max_width: int | None = None
    min_height: int | None = None
    max_height: int | None = None
    aspect_ratio: float | None = None
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
        for name in ("min_width", "max_width", "min_height", "max_height"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must not be negative")
        # A contradictory pair silently clips the widget to nothing on device,
        # which is far harder to debug than an exception here.
        if (
            self.min_width is not None
            and self.max_width is not None
            and self.min_width > self.max_width
        ):
            raise ValueError("min_width must not exceed max_width")
        if (
            self.min_height is not None
            and self.max_height is not None
            and self.min_height > self.max_height
        ):
            raise ValueError("min_height must not exceed max_height")
        if self.aspect_ratio is not None and self.aspect_ratio <= 0:
            raise ValueError("aspect_ratio must be positive")
        if (
            self.align is not None
            and self.align not in Align.MAIN
            and self.align not in Align.CROSS
        ):
            raise ValueError(f"invalid align {self.align!r}")
        for name, size in (("width", self.width), ("height", self.height)):
            if isinstance(size, int):
                if size <= 0:
                    raise ValueError(f"{name} must be a positive number of dp")
            elif isinstance(size, str):
                if size not in _DIMENSION_WORDS:
                    raise ValueError(
                        f"invalid {name} {size!r}; expected a positive number "
                        f"or one of: {', '.join(sorted(_DIMENSION_WORDS))}"
                    )
            elif size is not None:
                raise ValueError(
                    f"invalid {name} {size!r}; expected a positive number "
                    f"or one of: {', '.join(sorted(_DIMENSION_WORDS))}"
                )
        if self.weight is not None and self.weight < 0:
            raise ValueError("weight must not be negative")
        if self.elevation is not None and self.elevation < 0:
            raise ValueError("elevation must not be negative")
        if self.corner_radius is not None and self.corner_radius < 0:
            raise ValueError("corner_radius must not be negative")

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
