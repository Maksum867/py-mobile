"""Leaf UI components.

Each class is a small declarative node: it validates its own inputs, exposes
its state through plain attributes and serialises itself. Interaction is
reported through callbacks and, when the widget is mounted on a screen, through
the application event bus.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .widget import Widget, callback_name

__all__ = ["Label", "Button", "TextInput", "Image", "Switch", "ProgressBar", "Spacer"]


class Label(Widget):
    """Non-interactive text."""

    type_name = "Label"
    __slots__ = ("text",)

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.text = text

    def set_text(self, text: str) -> None:
        """Replace the displayed text."""
        self.text = text

    def props(self) -> dict[str, Any]:
        return {**super().props(), "text": self.text}


class Button(Widget):
    """A tappable button."""

    type_name = "Button"
    __slots__ = ("text", "on_press")

    def __init__(
        self,
        text: str = "",
        *,
        on_press: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.text = text
        self.on_press = on_press

    def press(self) -> None:
        """Simulate a tap; ignored while the button is disabled."""
        if self.enabled and self.on_press is not None:
            self.on_press()

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "text": self.text,
            "on_press": callback_name(self.on_press),
        }


class TextInput(Widget):
    """Single- or multi-line text field."""

    type_name = "TextInput"
    __slots__ = ("value", "placeholder", "multiline", "password", "max_length", "on_change")

    def __init__(
        self,
        value: str = "",
        *,
        placeholder: str = "",
        multiline: bool = False,
        password: bool = False,
        max_length: int | None = None,
        on_change: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if max_length is not None and max_length <= 0:
            raise ValueError("max_length must be positive")
        self.value = value
        self.placeholder = placeholder
        self.multiline = multiline
        self.password = password
        self.max_length = max_length
        self.on_change = on_change

    def set_value(self, value: str) -> None:
        """Update the text, truncating to ``max_length`` and notifying listeners."""
        if self.max_length is not None:
            value = value[: self.max_length]
        changed = value != self.value
        self.value = value
        if changed and self.on_change is not None:
            self.on_change(value)

    def clear(self) -> None:
        """Empty the field."""
        self.set_value("")

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "value": self.value,
            "placeholder": self.placeholder,
            "multiline": self.multiline,
            "password": self.password,
            "max_length": self.max_length,
            "on_change": callback_name(self.on_change),
        }


class Image(Widget):
    """An image loaded from a packaged resource, a file path or a URL."""

    type_name = "Image"
    __slots__ = ("source", "fit")

    FITS = ("contain", "cover", "fill", "none")

    def __init__(self, source: str, *, fit: str = "contain", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if not source:
            raise ValueError("image source must not be empty")
        if fit not in self.FITS:
            raise ValueError(f"fit must be one of {', '.join(self.FITS)}")
        self.source = source
        self.fit = fit

    def props(self) -> dict[str, Any]:
        return {**super().props(), "source": self.source, "fit": self.fit}


class Switch(Widget):
    """A binary on/off toggle."""

    type_name = "Switch"
    __slots__ = ("checked", "on_toggle")

    def __init__(
        self,
        checked: bool = False,
        *,
        on_toggle: Callable[[bool], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.checked = checked
        self.on_toggle = on_toggle

    def toggle(self) -> bool:
        """Flip the state and return the new value."""
        self.set_checked(not self.checked)
        return self.checked

    def set_checked(self, checked: bool) -> None:
        """Set the state, notifying listeners only on a real change."""
        if checked != self.checked:
            self.checked = checked
            if self.on_toggle is not None:
                self.on_toggle(checked)

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "checked": self.checked,
            "on_toggle": callback_name(self.on_toggle),
        }


class ProgressBar(Widget):
    """Determinate or indeterminate progress indicator."""

    type_name = "ProgressBar"
    __slots__ = ("value", "maximum", "indeterminate")

    def __init__(
        self,
        value: float = 0.0,
        *,
        maximum: float = 100.0,
        indeterminate: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if maximum <= 0:
            raise ValueError("maximum must be positive")
        self.maximum = maximum
        self.indeterminate = indeterminate
        self.value = 0.0
        self.set_value(value)

    def set_value(self, value: float) -> None:
        """Set progress, clamped to ``0..maximum``."""
        self.value = max(0.0, min(float(value), self.maximum))

    @property
    def fraction(self) -> float:
        """Progress as ``0.0..1.0``."""
        return self.value / self.maximum

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "value": self.value,
            "maximum": self.maximum,
            "indeterminate": self.indeterminate,
        }


class Spacer(Widget):
    """Empty flexible space between widgets."""

    type_name = "Spacer"
    __slots__ = ("size",)

    def __init__(self, size: int = 8, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if size < 0:
            raise ValueError("size must not be negative")
        self.size = size

    def props(self) -> dict[str, Any]:
        return {**super().props(), "size": self.size}


def widget_names() -> Sequence[str]:
    """Names of the built-in components (used by docs and tests)."""
    return tuple(__all__)
