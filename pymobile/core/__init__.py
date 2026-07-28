"""PyMobile core: application runtime, UI, Android APIs and networking."""

from __future__ import annotations

from .api import Notifications, Permission, PermissionManager, Vibration
from .app import App
from .config import ProjectConfig, load_config
from .events import Event, EventBus
from .net import HttpClient, Response
from .platform import Platform, current_platform, is_android, is_desktop
from .ui import (
    Align,
    Button,
    Color,
    Column,
    Container,
    EdgeInsets,
    Image,
    Label,
    Navigator,
    ProgressBar,
    Row,
    Screen,
    ScrollView,
    Spacer,
    Stack,
    Style,
    Switch,
    TextInput,
    Widget,
)

__all__ = [
    "App",
    "ProjectConfig",
    "load_config",
    "Event",
    "EventBus",
    "Platform",
    "current_platform",
    "is_android",
    "is_desktop",
    "Notifications",
    "Vibration",
    "Permission",
    "PermissionManager",
    "HttpClient",
    "Response",
    "Widget",
    "Container",
    "Label",
    "Button",
    "TextInput",
    "Image",
    "Switch",
    "ProgressBar",
    "Spacer",
    "Column",
    "Row",
    "ScrollView",
    "Stack",
    "Screen",
    "Navigator",
    "Style",
    "Color",
    "Align",
    "EdgeInsets",
]
