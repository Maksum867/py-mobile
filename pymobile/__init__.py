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

__version__ = "0.6.3"
__author__ = "MAKSYM KHLYSTUN"
__license__ = "MIT"

from .core.api import (
    Notifications,
    Permission,
    PermissionManager,
    Storage,
    Vibration,
    default_storage_path,
)
from .core.app import App
from .core.config import ProjectConfig, load_config
from .core.events import Event, EventBus
from .core.i18n import device_language, t, translations
from .core.jobs import JobHandle, JobManager
from .core.net import HttpCache, HttpClient, HttpFuture, HttpSecurityPolicy, Response
from .core.platform import Platform, current_platform, is_android, is_desktop
from .core.plugins import Plugin, PluginRegistry, plugins
from .core.scheduler import Scheduler, TimerHandle
from .core.ui import (
    Align,
    Avatar,
    Badge,
    Button,
    Checkbox,
    Chip,
    Color,
    Column,
    Container,
    DataTable,
    Divider,
    Dropdown,
    EdgeInsets,
    Expanded,
    Flexible,
    Grid,
    Image,
    Label,
    Link,
    List,
    ListTile,
    Navigator,
    ProgressBar,
    ProgressText,
    RadioButton,
    RadioGroup,
    RatingBar,
    Row,
    SafeArea,
    Screen,
    ScrollView,
    SearchBar,
    SegmentedButtons,
    Slider,
    Spacer,
    Stack,
    Stepper,
    Style,
    Switch,
    TextInput,
    Theme,
    Widget,
)
from .core.validation import ValidationError, Validator
from .errors import (
    BridgeError,
    ConfigError,
    NetworkError,
    PermissionError_,
    PlatformError,
    PyMobileError,
    ResourceError,
)
from .logging import get_diagnostics

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
    "Storage",
    "default_storage_path",
    # networking
    "HttpClient",
    "HttpCache",
    "HttpFuture",
    "HttpSecurityPolicy",
    "Response",
    # i18n
    "device_language",
    "t",
    "translations",
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
    "List",
    "ListTile",
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
    "Divider",
    "Expanded",
    "Flexible",
    "Grid",
    "SafeArea",
    "Theme",
    # validation
    "Validator",
    "ValidationError",
    # jobs & plugins
    "JobManager",
    "JobHandle",
    "Plugin",
    "PluginRegistry",
    "plugins",
    # diagnostics
    "get_diagnostics",
    # errors
    "PyMobileError",
    "ConfigError",
    "BridgeError",
    "PlatformError",
    "PermissionError_",
    "NetworkError",
    "ResourceError",
]
