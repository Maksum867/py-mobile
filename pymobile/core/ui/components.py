"""Leaf UI components.

Each class is a small declarative node: it validates its own inputs, exposes
its state through plain attributes and serialises itself. Interaction is
reported through callbacks and, when the widget is mounted on a screen, through
the application event bus.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .style import Color
from .widget import Container, Widget, callback_name

__all__ = [
    "Label",
    "Button",
    "TextInput",
    "Image",
    "Switch",
    "ProgressBar",
    "Spacer",
    "Slider",
    "Checkbox",
    "RatingBar",
    "Dropdown",
    "Chip",
    "Badge",
    "Stepper",
    "SearchBar",
    "RadioButton",
    "RadioGroup",
    "SegmentedButtons",
    "ProgressText",
    "Link",
    "DataTable",
    "Avatar",
]


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

        self._validate_source(source)

        self.source = source
        self.fit = fit

    def _validate_source(self, source: str) -> None:
        """Validate local paths while allowing web, data and packaged assets.

        A ``file://`` URI is intentionally treated as a local path rather than
        blindly trusted: it remains subject to the same existence/type checks.
        Relative paths that do not exist on the desktop are allowed — they are
        typically assets that only appear inside the APK.
        """
        parsed = urlparse(source)
        if parsed.scheme in ("http", "https", "data"):
            return
        if parsed.scheme == "file":
            if parsed.netloc not in ("", "localhost"):
                raise ValueError("file image URLs must refer to the local machine")
            path_text = unquote(parsed.path)
            # file:///C:/... is parsed as /C:/...; Windows paths must not
            # retain that URI-leading slash before being given to pathlib.
            if (
                os.name == "nt"
                and len(path_text) >= 3
                and path_text[0] == "/"
                and path_text[2] == ":"
            ):
                path_text = path_text[1:]
            path = Path(path_text)
        elif parsed.scheme:
            raise ValueError(f"unsupported image URL scheme: {parsed.scheme!r}")
        else:
            path = Path(source)

        if not path.exists():
            # Packaged assets are not on the desktop filesystem.
            if not path.is_absolute() and parsed.scheme == "":
                return
            raise FileNotFoundError(f"Image resource file does not exist: '{source}'")
        if not path.is_file():
            raise IsADirectoryError(
                f"Image resource path points to a directory, not a file: '{source}'"
            )

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


class Slider(Widget):
    """A draggable numeric input (Android SeekBar).

    ``slider.value`` ranges between ``minimum`` and ``maximum`` (both inclusive)
    and is snapped to ``step`` when one is given. ``on_change`` fires on every
    genuine value change.
    """

    type_name = "Slider"
    __slots__ = ("_value", "minimum", "maximum", "step", "on_change")

    def __init__(
        self,
        value: float = 0.0,
        *,
        minimum: float = 0.0,
        maximum: float = 100.0,
        step: float | None = None,
        on_change: Callable[[float], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if maximum <= minimum:
            raise ValueError("maximum must be greater than minimum")
        if step is not None and step <= 0:
            raise ValueError("step must be positive")
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.on_change = on_change
        # Set the initial value directly so the constructor never fires the
        # on_change callback (a listener should observe user edits, not setup).
        self._value = self._normalise(value)

    def _normalise(self, value: float) -> float:
        """Clamp ``value`` to the range and snap to ``step`` (no side effects)."""
        clamped = max(self.minimum, min(float(value), self.maximum))
        if self.step is not None:
            steps = round((clamped - self.minimum) / self.step)
            clamped = self.minimum + steps * self.step
            clamped = max(self.minimum, min(clamped, self.maximum))
        return clamped

    @property
    def value(self) -> float:
        """The current value; assigning to it schedules a redraw."""
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self.set_value(value)

    @property
    def fraction(self) -> float:
        """Value as ``0.0..1.0`` across the range."""
        return (self._value - self.minimum) / (self.maximum - self.minimum)

    def set_value(self, value: float) -> None:
        """Clamp ``value`` to the range, snap to ``step`` and notify listeners."""
        clamped = self._normalise(value)
        if clamped != self._value:
            self._value = clamped
            self.invalidate()
            if self.on_change is not None:
                self.on_change(clamped)

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "value": self._value,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "on_change": callback_name(self.on_change),
        }


class Checkbox(Widget):
    """A simple on/off check box (distinct from Switch by look).

    Behaves like :class:`Switch` — ``checked``/``set_checked``/``toggle`` and an
    ``on_toggle`` callback that fires only on a genuine change.
    """

    type_name = "Checkbox"
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

    @property
    def checked(self) -> bool:
        """Whether the box is ticked; assigning to it schedules a redraw."""
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

    def toggle(self) -> bool:
        """Flip the state and return the new value."""
        self.set_checked(not self._checked)
        return self._checked

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "checked": self._checked,
            "on_toggle": callback_name(self.on_toggle),
        }


class RatingBar(Widget):
    """A star-based rating input (Android RatingBar).

    ``rating`` is a number of stars (may be fractional); ``maximum`` is the
    total number of stars shown. ``on_change`` fires on a genuine change.
    """

    type_name = "RatingBar"
    __slots__ = ("_rating", "maximum", "on_change")

    def __init__(
        self,
        rating: float | None = None,
        *,
        value: float | None = None,
        maximum: int = 5,
        on_change: Callable[[float], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if rating is not None and value is not None:
            raise ValueError("pass either rating or value, not both")
        if maximum < 1:
            raise ValueError("maximum must be >= 1")
        self.maximum = maximum
        self.on_change = on_change
        initial: float = rating if rating is not None else (value if value is not None else 0.0)
        self._rating = max(0.0, min(float(initial), float(maximum)))

    @property
    def rating(self) -> float:
        """The current rating; assigning to it schedules a redraw."""
        return self._rating

    @rating.setter
    def rating(self, value: float) -> None:
        self.set_value(value)

    @property
    def value(self) -> float:
        """Alias of :attr:`rating` so the app's generic ``change`` event works."""
        return self._rating

    def set_value(self, value: float) -> None:
        """Clamp ``value`` to ``0..maximum`` and notify listeners."""
        clamped = max(0.0, min(float(value), float(self.maximum)))
        if clamped != self._rating:
            self._rating = clamped
            self.invalidate()
            if self.on_change is not None:
                self.on_change(clamped)

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "rating": self._rating,
            "maximum": self.maximum,
            "on_change": callback_name(self.on_change),
        }


class Dropdown(Widget):
    """A select-one drop-down list (Android Spinner).

    ``options`` is the ordered list of choices; ``value`` is the currently
    selected one. ``on_select`` fires when the selection changes.
    """

    type_name = "Dropdown"
    __slots__ = ("options", "_value", "on_select")

    def __init__(
        self,
        options: Sequence[str],
        *,
        value: str | None = None,
        on_select: Callable[[str], None] | None = None,
        on_change: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if on_select is not None and on_change is not None:
            raise ValueError("pass either on_select or on_change, not both")
        if not options:
            raise ValueError("options must not be empty")
        if not all(isinstance(o, str) for o in options):
            raise ValueError("options must be strings")
        self.options = list(options)
        self.on_select = on_select or on_change
        # Fail fast, the way Style() does for a bad colour: silently swapping an
        # unknown value for the first option hides a typo until someone notices
        # the wrong row is selected on a phone.
        if value is not None and value not in self.options:
            raise ValueError(
                f"value {value!r} is not one of the options {self.options!r}"
            )
        self._value = value if value is not None else self.options[0]

    @property
    def value(self) -> str:
        """The selected option; assigning to it schedules a redraw."""
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        self.select(value)

    def select(self, value: str) -> None:
        """Choose ``value``, notifying listeners only on a real change."""
        if value not in self.options:
            raise ValueError(f"{value!r} is not one of the options")
        if value != self._value:
            self._value = value
            self.invalidate()
            if self.on_select is not None:
                self.on_select(value)

    def set_value(self, value: str) -> None:
        """Generic setter used by the app's ``change`` event handler."""
        self.select(value)

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "options": list(self.options),
            "value": self._value,
            "on_select": callback_name(self.on_select),
        }


class Chip(Widget):
    """A small tappable filter/tag (a compact button with a selected state)."""

    type_name = "Chip"
    __slots__ = ("_text", "_selected", "on_press")

    def __init__(
        self,
        text: str = "",
        *,
        selected: bool = False,
        on_press: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._text = text
        self._selected = selected
        self.on_press = on_press

    @property
    def text(self) -> str:
        """The chip's label; assigning to it schedules a redraw."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self.invalidate()

    @property
    def selected(self) -> bool:
        """Whether the chip is toggled on; assigning schedules a redraw."""
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self.set_selected(value)

    def set_selected(self, value: bool) -> None:
        if value != self._selected:
            self._selected = value
            self.invalidate()

    def press(self) -> None:
        """Simulate a tap; ignored while disabled."""
        if self.enabled and self.on_press is not None:
            self.on_press()

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "text": self._text,
            "selected": self._selected,
            "on_press": callback_name(self.on_press),
        }


class Badge(Widget):
    """A small numeric/status pill shown over content (e.g. an unread count)."""

    type_name = "Badge"
    __slots__ = ("_text", "color", "background")

    def __init__(
        self,
        text: str | int = "",
        *,
        color: str = Color.BACKGROUND,
        background: str = Color.PRIMARY,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._text = str(text)
        self.color = Color.validate(color)
        self.background = Color.validate(background)

    @property
    def text(self) -> str:
        """The badge content; assigning to it schedules a redraw."""
        return self._text

    @text.setter
    def text(self, value: str | int) -> None:
        value = str(value)
        if value != self._text:
            self._text = value
            self.invalidate()

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "text": self._text,
            "color": self.color,
            "background": self.background,
        }


class Stepper(Widget):
    """A value with increment/decrement controls (programmatic interaction).

    ``increment()`` / ``decrement()`` move the value by ``step`` within
    ``[minimum, maximum]``; ``on_change`` fires on a genuine change.
    """

    type_name = "Stepper"
    __slots__ = ("_value", "minimum", "maximum", "step", "on_change")

    def __init__(
        self,
        value: int = 0,
        *,
        minimum: int = 0,
        maximum: int = 100,
        step: int = 1,
        on_change: Callable[[int], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if maximum < minimum:
            raise ValueError("maximum must be >= minimum")
        if step <= 0:
            raise ValueError("step must be positive")
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.on_change = on_change
        self._value = max(minimum, min(int(value), maximum))

    @property
    def value(self) -> int:
        """The current value; assigning to it schedules a redraw."""
        return self._value

    @value.setter
    def value(self, value: int) -> None:
        self.set_value(value)

    def set_value(self, value: int) -> None:
        """Clamp ``value`` to the range and notify listeners."""
        clamped = max(self.minimum, min(int(value), self.maximum))
        if clamped != self._value:
            self._value = clamped
            self.invalidate()
            if self.on_change is not None:
                self.on_change(clamped)

    def increment(self) -> int:
        """Step up and return the new value."""
        self.set_value(self._value + self.step)
        return self._value

    def decrement(self) -> int:
        """Step down and return the new value."""
        self.set_value(self._value - self.step)
        return self._value

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "value": self._value,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "on_change": callback_name(self.on_change),
        }


class SearchBar(Widget):
    """A text field styled for search with an optional submit callback.

    Thin convenience wrapper over a :class:`TextInput`-like value:
    ``value``/``set_value`` plus ``on_change`` and ``on_search``.
    """

    type_name = "SearchBar"
    __slots__ = ("_value", "placeholder", "on_change", "on_search")

    def __init__(
        self,
        value: str = "",
        *,
        placeholder: str = "Search…",
        on_change: Callable[[str], None] | None = None,
        on_search: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._value = value
        self.placeholder = placeholder
        self.on_change = on_change
        self.on_search = on_search

    @property
    def value(self) -> str:
        """The current query; assigning to it schedules a redraw."""
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        self.set_value(value)

    def set_value(self, value: str) -> None:
        if value != self._value:
            self._value = value
            self.invalidate()
            if self.on_change is not None:
                self.on_change(value)

    def submit(self) -> None:
        """Fire the search action with the current query."""
        if self.enabled and self.on_search is not None:
            self.on_search(self._value)

    def clear(self) -> None:
        """Empty the field."""
        self.set_value("")

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "value": self._value,
            "placeholder": self.placeholder,
            "on_change": callback_name(self.on_change),
            "on_search": callback_name(self.on_search),
        }


class RadioButton(Widget):
    """A single selectable option (usually inside a :class:`RadioGroup`)."""

    type_name = "RadioButton"
    __slots__ = ("_text", "_selected", "on_press")

    def __init__(
        self,
        text: str = "",
        *,
        selected: bool = False,
        on_press: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._text = text
        self._selected = selected
        self.on_press = on_press

    @property
    def text(self) -> str:
        """The radio's label; assigning to it schedules a redraw."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self.invalidate()

    @property
    def selected(self) -> bool:
        """Whether this radio is chosen; assigning schedules a redraw."""
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self.set_selected(value)

    def set_selected(self, value: bool) -> None:
        if value != self._selected:
            self._selected = value
            self.invalidate()

    def press(self) -> None:
        """Simulate a tap; ignored while disabled.

        When this radio lives inside a :class:`RadioGroup`, the group is
        updated first so Python-layer tests and the web preview actually
        change the selected value.
        """
        if not self.enabled:
            return
        parent = self.parent
        if isinstance(parent, RadioGroup):
            parent.select(self.text)
        if self.on_press is not None:
            self.on_press()

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "text": self._text,
            "selected": self._selected,
            "on_press": callback_name(self.on_press),
        }


class RadioGroup(Container):
    """A group of :class:`RadioButton`\\ s where at most one is selected.

    Selecting a radio in the group unselects the others. ``value`` is the text
    of the selected radio (or ``None``). ``on_select`` fires on a change.
    """

    type_name = "RadioGroup"
    __slots__ = ("_value", "on_select", "_radios")

    def __init__(
        self,
        *children: RadioButton,
        value: str | None = None,
        on_select: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        # _radios must exist before add() runs (Container.extend calls add()).
        self._radios: dict[str, RadioButton] = {}
        super().__init__(*children, **kwargs)
        self.on_select = on_select
        self._value: str | None = None
        # Set the initial selection WITHOUT firing on_select — a constructor
        # should observe user edits, not report setup.
        if value is not None:
            self._select_silent(value)
        elif children:
            for radio in children:
                if radio.selected:
                    self._select_silent(radio.text)
                    break

    def _select_silent(self, text: str) -> None:
        """Set the selected radio and update visuals without calling on_select."""
        if text not in self._radios:
            raise ValueError(f"{text!r} is not a radio in this group")
        self._value = text
        for label, radio in self._radios.items():
            radio.set_selected(label == text)

    def _register(self, radio: RadioButton) -> None:
        if not isinstance(radio, RadioButton):
            raise ValueError("RadioGroup children must be RadioButton instances")
        self._radios[radio.text] = radio

    @property
    def value(self) -> str | None:
        """The currently selected radio's text, or ``None``."""
        return self._value

    def select(self, text: str) -> None:
        """Choose the radio labelled ``text``, unselecting the others."""
        if text not in self._radios:
            raise ValueError(f"{text!r} is not a radio in this group")
        if text == self._value:
            return
        self._select_silent(text)
        self.invalidate()
        if self.on_select is not None:
            self.on_select(text)

    def set_value(self, value: str) -> None:
        """Generic setter used by the app's ``change`` event handler."""
        self.select(value)

    def add(self, child: Widget) -> Widget:
        if not isinstance(child, RadioButton):
            raise ValueError("RadioGroup children must be RadioButton instances")
        result = super().add(child)
        self._register(child)
        return result

    def props(self) -> dict[str, Any]:
        return {**super().props(), "value": self._value}


class SegmentedButtons(Widget):
    """A horizontal bar of mutually exclusive options (like a tab bar / filter).

    ``options`` is the ordered list of choices; ``value`` is the selected one.
    ``on_select`` fires when the selection changes. ``on_change`` is a
    documented compatibility alias.
    """

    type_name = "SegmentedButtons"
    __slots__ = ("options", "_value", "on_select")

    def __init__(
        self,
        options: Sequence[str],
        *,
        value: str | None = None,
        on_select: Callable[[str], None] | None = None,
        on_change: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if on_select is not None and on_change is not None:
            raise ValueError("pass either on_select or on_change, not both")
        if not options:
            raise ValueError("options must not be empty")
        self.options = list(options)
        self.on_select = on_select or on_change
        # Fail fast, the way Style() does for a bad colour: silently swapping an
        # unknown value for the first option hides a typo until someone notices
        # the wrong row is selected on a phone.
        if value is not None and value not in self.options:
            raise ValueError(
                f"value {value!r} is not one of the options {self.options!r}"
            )
        self._value = value if value is not None else self.options[0]

    @property
    def value(self) -> str:
        """The selected option; assigning to it schedules a redraw."""
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        self.select(value)

    def select(self, value: str) -> None:
        """Choose ``value``, notifying listeners only on a real change."""
        if value not in self.options:
            raise ValueError(f"{value!r} is not one of the options")
        if value != self._value:
            self._value = value
            self.invalidate()
            if self.on_select is not None:
                self.on_select(value)

    def set_value(self, value: str) -> None:
        self.select(value)

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "options": list(self.options),
            "value": self._value,
            "on_select": callback_name(self.on_select),
        }


class ProgressText(Widget):
    """A determinate progress bar with a textual label (e.g. "Downloading 42%").

    Combines the value of a :class:`ProgressBar` with a formatted label that
    updates as the value changes.
    """

    type_name = "ProgressText"
    __slots__ = ("_value", "maximum", "format", "label")

    def __init__(
        self,
        value: float = 0.0,
        *,
        maximum: float = 100.0,
        format: str | None = None,
        label: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if maximum <= 0:
            raise ValueError("maximum must be positive")
        self.maximum = maximum
        # {percent} and {value} are interpolated into the label.
        self.format = format or "{percent}%"
        self.label = label
        self._value = max(0.0, min(float(value), maximum))

    @property
    def value(self) -> float:
        """Current progress; assigning to it schedules a redraw."""
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self.set_value(value)

    def set_value(self, value: float) -> None:
        clamped = max(0.0, min(float(value), self.maximum))
        if clamped != self._value:
            self._value = clamped
            self.invalidate()

    @property
    def fraction(self) -> float:
        """Progress as ``0.0..1.0``."""
        return self._value / self.maximum

    @property
    def percent(self) -> int:
        """Progress as a whole-number percentage."""
        return round(self.fraction * 100)

    @property
    def text(self) -> str:
        """The formatted label (e.g. ``"42%"`` or ``"Downloading 42%"``)."""
        shown = self._value
        if float(shown).is_integer():
            shown = int(shown)
        body = self.format.format(
            value=shown,
            percent=self.percent,
            maximum=self.maximum,
            fraction=self.fraction,
        )
        return f"{self.label} {body}".strip() if self.label else body

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "value": self._value,
            "maximum": self.maximum,
            "format": self.format,
            "label": self.label,
            "text": self.text,
        }


class Link(Widget):
    """A tappable text styled as a hyperlink."""

    type_name = "Link"
    __slots__ = ("_text", "url", "on_press")

    def __init__(
        self,
        text: str = "",
        *,
        url: str = "",
        on_press: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._text = text
        self.url = url
        self.on_press = on_press

    @property
    def text(self) -> str:
        """The link's label; assigning to it schedules a redraw."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self.invalidate()

    def press(self) -> None:
        """Simulate a tap; ignored while disabled.

        Opens ``url`` through the active platform bridge when one is set.
        """
        if not self.enabled:
            return
        if self.url:
            from ...bridge import get_bridge

            get_bridge().open_url(self.url)
        if self.on_press is not None:
            self.on_press()

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "text": self._text,
            "url": self.url,
            "on_press": callback_name(self.on_press),
        }


class DataTable(Widget):
    """A simple read-only table of ``headers`` and ``rows``.

    ``rows`` is a list of lists (or tuples) of values. Useful for stats,
    schedules and reference data without pulling in a heavy widget.
    """

    type_name = "DataTable"
    __slots__ = ("headers", "rows")

    def __init__(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]] = (),
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if not headers:
            raise ValueError("headers must not be empty")
        self.headers = [str(h) for h in headers]
        self.rows: list[list[str]] = [[str(cell) for cell in row] for row in rows]

    def add_row(self, row: Sequence[Any]) -> None:
        """Append a row (missing cells become empty strings)."""
        values = [str(cell) for cell in row]
        if len(values) > len(self.headers):
            raise ValueError("row has more cells than the table has columns")
        values += [""] * (len(self.headers) - len(values))
        self.rows.append(values)
        self.invalidate()

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "headers": list(self.headers),
            "rows": [list(r) for r in self.rows],
        }


def _looks_like_image_source(value: str) -> bool:
    """Whether ``value`` is a path, URL or filename rather than initials."""
    if not value:
        return False
    parsed = urlparse(value)
    if parsed.scheme in ("http", "https", "data", "file"):
        return True
    if "/" in value or "\\" in value:
        return True
    lower = value.lower()
    return lower.endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".ico")
    )


class Avatar(Widget):
    """A round image or initial-avatar (e.g. a user's picture or initials).

    ``Avatar("MK")`` is initials (as documented). Pass ``image=`` or a
    path-like positional for a photo.
    """

    type_name = "Avatar"
    __slots__ = ("source", "text", "size", "color", "background")

    def __init__(
        self,
        source: str = "",
        *,
        text: str = "",
        image: str | None = None,
        size: int = 48,
        color: str = Color.BACKGROUND,
        background: str = Color.PRIMARY,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if size <= 0:
            raise ValueError("size must be positive")
        # Docs: Avatar("MK") is initials. Avatar("MK", image=...) is a photo
        # with a fallback glyph. A path-like positional is a source.
        if image is not None:
            if source and _looks_like_image_source(source):
                raise ValueError("pass either source or image, not both")
            if source and not text:
                text = source
            source = image
        elif source and not text and not _looks_like_image_source(source):
            text = source
            source = ""
        if not source and not text:
            raise ValueError("Avatar needs a source or a text")
        self.source = source
        self.text = text
        self.size = size
        self.color = Color.validate(color)
        self.background = Color.validate(background)

    def props(self) -> dict[str, Any]:
        return {
            **super().props(),
            "source": self.source,
            "text": self.text,
            "size": self.size,
            "color": self.color,
            "background": self.background,
        }


def widget_names() -> Sequence[str]:
    """Names of the built-in components (used by docs and tests)."""
    return tuple(__all__)
