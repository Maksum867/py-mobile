"""PyMobile — a Python framework for building Android applications.

Quick start::

    from pymobile import App, Column, Label, Button, Screen

    class Home(Screen):
        def build(self):
            return Column(
                Label("Hello, Android!"),
                Button("Tap", on_press=lambda: print("tapped")),
            )

    App("Demo").run(Home())

Build it with ``pymobile build``.
"""

from __future__ import annotations

__version__ = "0.2.0"
__author__ = "MAKSYM KHLYSTUN"
__license__ = "MIT"

from .core.api import Notifications, Permission, PermissionManager, Vibration
from .core.app import App
from .core.config import ProjectConfig, load_config
from .core.events import Event, EventBus
from .core.net import HttpClient, Response
from .core.platform import Platform, current_platform, is_android, is_desktop
from .core.scheduler import Scheduler, TimerHandle
from .core.ui import (
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
from .errors import (
    BridgeError,
    ConfigError,
    NetworkError,
    PlatformError,
    PyMobileError,
    ResourceError,
)

__all__ = [
    "__version__",
    # application
    "App",
    "ProjectConfig",
    "load_config",
    "Event",
    "EventBus",
    "Scheduler",
    "TimerHandle",
    # platform
    "Platform",
    "current_platform",
    "is_android",
    "is_desktop",
    # android apis
    "Notifications",
    "Vibration",
    "Permission",
    "PermissionManager",
    # networking
    "HttpClient",
    "Response",
    # ui
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
    # errors
    "PyMobileError",
    "ConfigError",
    "BridgeError",
    "PlatformError",
    "NetworkError",
    "ResourceError",
]
