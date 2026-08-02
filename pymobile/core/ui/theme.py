"""Application themes: named colour palettes applied app-wide.

A :class:`Theme` maps the framework's semantic colour names (``PRIMARY``,
``ACCENT``, ``BACKGROUND``, ``SURFACE``, ``TEXT``, ``TEXT_MUTED``, ``SUCCESS``,
``WARNING``, ``ERROR``) to concrete ``#RRGGBB``/``#AARRGGBB`` values. Two
presets ship: :data:`Theme.LIGHT` and :data:`Theme.DARK`.

Give an app a theme and read resolved colours with :meth:`Theme.color` (or the
shorthand ``app.theme["PRIMARY"]``). Widgets pick up themed defaults when they
build; a theme change redraws the visible screen just like a language change.
"""

from __future__ import annotations

from typing import Any

from .style import Color

__all__ = ["Theme"]

#: Semantic colour names a theme may (or may not) override.
_SEMANTIC = (
    "PRIMARY",
    "ACCENT",
    "BACKGROUND",
    "SURFACE",
    "TEXT",
    "TEXT_MUTED",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "TRANSPARENT",
)


class Theme:
    """A named set of colours resolved through the semantic palette.

    ``colors`` maps semantic names (or any name) to ``#RRGGBB`` hex strings.
    Unknown semantic names fall back to the built-in :class:`Color` defaults, so
    a partial theme (e.g. only ``BACKGROUND`` and ``TEXT`` for a dark mode) is
    enough.
    """

    __slots__ = ("name", "_colors")

    def __init__(self, name: str, colors: dict[str, str] | None = None) -> None:
        self.name = name
        self._colors: dict[str, str] = {}
        if colors:
            for key, value in colors.items():
                self._colors[key.upper()] = Color.validate(value)

    # -- presets -----------------------------------------------------------
    @classmethod
    def light(cls) -> "Theme":
        """The default light palette (mirrors the built-in ``Color`` values)."""
        return cls(
            "light",
            {
                "PRIMARY": Color.PRIMARY,
                "ACCENT": Color.ACCENT,
                "BACKGROUND": Color.BACKGROUND,
                "SURFACE": Color.SURFACE,
                "TEXT": Color.TEXT,
                "TEXT_MUTED": Color.TEXT_MUTED,
                "SUCCESS": Color.SUCCESS,
                "WARNING": Color.WARNING,
                "ERROR": Color.ERROR,
            },
        )

    @classmethod
    def dark(cls) -> "Theme":
        """A built-in dark palette (Material-ish dark colours)."""
        return cls(
            "dark",
            {
                "PRIMARY": "#5C6BC0",
                "ACCENT": "#FF80AB",
                "BACKGROUND": "#121212",
                "SURFACE": "#1E1E1E",
                "TEXT": "#EEEEEE",
                "TEXT_MUTED": "#9E9E9E",
                "SUCCESS": "#81C784",
                "WARNING": "#FFB74D",
                "ERROR": "#EF5350",
            },
        )

    # -- access ------------------------------------------------------------
    @property
    def is_dark(self) -> bool:
        """Whether this is the dark preset (or a custom theme named dark)."""
        return self.name.lower() == "dark"

    def color(self, name: str) -> str:
        """Resolve a semantic colour name to a hex string.

        Returns the themed value when present, otherwise the built-in
        :class:`Color` default for that name (so ``PRIMARY`` etc. always work),
        and finally raises ``ValueError`` for an unknown name.
        """
        key = name.upper()
        if key in self._colors:
            return self._colors[key]
        fallback = getattr(Color, key, None)
        if fallback is not None:
            return fallback
        raise ValueError(f"unknown colour {name!r}")

    def as_dict(self) -> dict[str, str]:
        """All resolved colours as a ``{NAME: hex}`` mapping."""
        return {key: self.color(key) for key in _SEMANTIC}

    def __getitem__(self, name: str) -> str:
        return self.color(name)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Theme {self.name!r} colours={len(self._colors)}>"


#: Convenience constants.
LIGHT = Theme.light()
DARK = Theme.dark()
