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
    """Non-interactive text.

    ``label.text = "5"`` and ``label.set_text("5")`` are equivalent, and both
    redraw the screen on their own.
    """

    type_name = "Label"
    __slots__ = ("_text",)

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._text = text

    @property
    def text(self) -> str:
        """The displayed text; assigning to it schedules a redraw."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self.invalidate()

    def set_text(self, text: str) -> None:
        """Replace the displayed text."""
        self.text = text

    def props(self) -> dict[str, Any]:
        return {**super().props(), "text": self._text}


class Button(Widget):
    """A tappable button."""

    type_name = "Button"
    __slots__ = ("_text", "on_press")

    def __init__(
        self,
        text: str = "",
        *,
        on_press: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._text = text
        self.on_press = on_press

    @property
    def text(self) -> str:
        """The button's label; assigning to it schedules a redraw."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self.invalidate()

    def set_text(self, text: str) -> None:
        """Replace the button's label, mirroring :meth:`Label.set_text`."""
        self.text = text

    def press(self) -> None:
        """Simulate a tap; ignored while the button is disabled."""
        if self.enabled and self.on_press is not None:
            self.on_press()

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "text": self._text,
            "on_press": callback_name(self.on_press),
        }


class TextInput(Widget):
    """Single- or multi-line text field."""

    type_name = "TextInput"
    __slots__ = ("_value", "placeholder", "multiline", "password", "max_length", "on_change")

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
        self._value = value
        self.placeholder = placeholder
        self.multiline = multiline
        self.password = password
        self.max_length = max_length
        self.on_change = on_change

    @property
    def value(self) -> str:
        """The current text; assigning to it schedules a redraw."""
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        self.set_value(value)

    def set_value(self, value: str) -> None:
        """Update the text, truncating to ``max_length`` and notifying listeners."""
        if self.max_length is not None:
            value = value[: self.max_length]
        if value == self._value:
            return
        self._value = value
        self.invalidate()
        if self.on_change is not None:
            self.on_change(value)

    def clear(self) -> None:
        """Empty the field."""
        self.set_value("")

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "value": self._value,
            "placeholder": self.placeholder,
            "multiline": self.multiline,
            "password": self.password,
            "max_length": self.max_length,
            "on_change": callback_name(self.on_change),
        }


from pathlib import Path
from typing import Any
import urllib.parse

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

        # Перевірка джерела
        self._validate_source(source)

        self.source = source
        self.fit = fit

    def _validate_source(self, source: str) -> None:
        # 1. Якщо це URL (http://, https://, file://) — пропускаємо перевірку файлової системи
        parsed = urllib.parse.urlparse(source)
        if parsed.scheme in ("http", "https", "data"):
            return

        # 2. Якщо це ресурс або відносний/абсолютний шлях
        path = Path(source)

        # Перевірка на спроби виходу за межі (Path Traversal на кшталт ../../etc/passwd)
        # Якщо шлях починається з системного кореня і не існує — це помилка
        if not path.exists():
            raise FileNotFoundError(f"Image resource file does not exist: '{source}'")

        if not path.is_file():
            raise IsADirectoryError(f"Image resource path points to a directory, not a file: '{source}'")

    def props(self) -> dict[str, Any]:
        return {**super().props(), "source": self.source, "fit": self.fit}

class Switch(Widget):
    """A binary on/off toggle."""

    type_name = "Switch"
    __slots__ = ("_checked", "on_toggle")

    def __init__(
        self,
        checked: bool = False,
        *,
        on_toggle: Callable[[bool], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._checked = checked
        self.on_toggle = on_toggle

    def toggle(self) -> bool:
        """Flip the state and return the new value."""
        self.set_checked(not self.checked)
        return self.checked

    @property
    def checked(self) -> bool:
        """Whether the switch is on; assigning to it schedules a redraw."""
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self.set_checked(value)

    def set_checked(self, checked: bool) -> None:
        """Set the state, notifying listeners only on a real change."""
        if checked != self._checked:
            self._checked = checked
            self.invalidate()
            if self.on_toggle is not None:
                self.on_toggle(checked)

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "checked": self._checked,
            "on_toggle": callback_name(self.on_toggle),
        }


class ProgressBar(Widget):
    """Determinate or indeterminate progress indicator."""

    type_name = "ProgressBar"
    __slots__ = ("_value", "maximum", "indeterminate")

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
        self._value = 0.0
        self.set_value(value)

    @property
    def value(self) -> float:
        """Current progress; assigning to it schedules a redraw."""
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self.set_value(value)

    def set_value(self, value: float) -> None:
        """Set progress, clamped to ``0..maximum``."""
        clamped = max(0.0, min(float(value), self.maximum))
        if clamped != self._value:
            self._value = clamped
            self.invalidate()

    @property
    def fraction(self) -> float:
        """Progress as ``0.0..1.0``."""
        return self._value / self.maximum

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "value": self._value,
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
