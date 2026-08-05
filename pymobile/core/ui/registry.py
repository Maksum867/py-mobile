"""Declared renderer capabilities and parity checks for built-in widgets.

The registry is intentionally conservative: a renderer is listed only when it
has a dedicated implementation, not a generic ``<Widget>`` fallback. This lets
CI expose parity gaps without pretending that previews support native features.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["WidgetCapability", "WIDGET_CAPABILITIES", "widget_types", "supported_by"]


@dataclass(frozen=True, slots=True)
class WidgetCapability:
    """Support declaration for one built-in serialised widget type."""

    type_name: str
    android: bool = True
    web: bool = False
    gui: bool = False
    ascii: bool = True


# Every type produced by a built-in widget must have one row here. Web/GUI are
# deliberately explicit: an unsupported node renders a visible fallback rather
# than silently claiming native parity.
WIDGET_CAPABILITIES: tuple[WidgetCapability, ...] = (
    WidgetCapability("Label", web=True, gui=True),
    WidgetCapability("Button", web=True, gui=True),
    WidgetCapability("TextInput", web=True, gui=True),
    WidgetCapability("Image", web=True, gui=True),
    WidgetCapability("Switch", web=True, gui=True),
    WidgetCapability("ProgressBar", web=True, gui=True),
    WidgetCapability("Spacer", web=True, gui=True),
    WidgetCapability("Column", web=True, gui=True),
    WidgetCapability("Row", web=True, gui=True),
    WidgetCapability("ScrollView", web=True, gui=True),
    WidgetCapability("Stack", web=True, gui=True),
    WidgetCapability("Grid", web=True, gui=True),
    WidgetCapability("Expanded", web=True, gui=True),
    WidgetCapability("Flexible", web=True, gui=True),
    WidgetCapability("Divider", web=True, gui=True),
    WidgetCapability("SafeArea", web=True, gui=True),
    WidgetCapability("Container", android=False, web=True, gui=True),
    WidgetCapability("Slider"),
    WidgetCapability("Checkbox"),
    WidgetCapability("RatingBar"),
    WidgetCapability("Dropdown"),
    WidgetCapability("Chip"),
    WidgetCapability("Badge"),
    WidgetCapability("Stepper"),
    WidgetCapability("SearchBar"),
    WidgetCapability("RadioButton"),
    WidgetCapability("RadioGroup"),
    WidgetCapability("SegmentedButtons"),
    WidgetCapability("ProgressText"),
    WidgetCapability("Link"),
    WidgetCapability("DataTable"),
    WidgetCapability("Avatar"),
    WidgetCapability("List"),
    WidgetCapability("ListTile"),
)


def widget_types() -> frozenset[str]:
    """All built-in serialised widget names."""
    return frozenset(capability.type_name for capability in WIDGET_CAPABILITIES)


def supported_by(renderer: str) -> frozenset[str]:
    """Return types with dedicated support in ``android``, ``web``, ``gui`` or ``ascii``."""
    if renderer not in {"android", "web", "gui", "ascii"}:
        raise ValueError(f"unknown renderer: {renderer!r}")
    return frozenset(
        capability.type_name
        for capability in WIDGET_CAPABILITIES
        if bool(getattr(capability, renderer))
    )
