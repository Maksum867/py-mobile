"""A tiny plugin/extension registry.

Lets third-party code extend the framework without touching its internals: a
plugin registers an ``activate(app)`` hook that runs when the app starts, plus
optional lifecycle hooks. This keeps additions isolated and testable while
giving apps a way to bundle reusable behaviour.

Example::

    class MyPlugin:
        name = "myplugin"

        def activate(self, app):
            app.on("app:start", ...)

    plugins.register(MyPlugin())
    app = App("Demo")
    plugins.activate_all(app)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .app import App

__all__ = ["Plugin", "PluginRegistry", "plugins"]

_log = get_logger("plugins")


class Plugin:
    """Base class for a plugin.

    Subclasses set ``name`` and may implement ``activate(app)`` plus optional
    ``on_app_start(app)`` / ``on_app_stop(app)`` hooks. ``activate`` runs once
    when the plugin is registered or when the registry activates everything.
    """

    #: Unique plugin name.
    name: str = ""

    def activate(self, app: App) -> None:
        """Called when the plugin is activated with the application.

        Subclasses override this to subscribe to events, register widgets, etc.
        """

    def on_app_start(self, app: App) -> None:
        """Optional hook: called when the app starts."""

    def on_app_stop(self, app: App) -> None:
        """Optional hook: called when the app stops."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.name!r}>"


class PluginRegistry:
    """Holds registered plugins and activates them against an :class:`App`."""

    __slots__ = ("_plugins", "_activated")

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._activated: set[str] = set()

    @property
    def names(self) -> tuple[str, ...]:
        """Names of all registered plugins."""
        return tuple(self._plugins)

    def register(self, plugin: Plugin) -> None:
        """Register ``plugin``; duplicates are ignored."""
        name = plugin.name or type(plugin).__name__
        if name in self._plugins:
            _log.debug("plugin %r already registered; ignoring", name)
            return
        self._plugins[name] = plugin
        _log.debug("registered plugin %r", name)

    def unregister(self, name: str) -> bool:
        """Remove a plugin by name; returns whether it was present."""
        return self._plugins.pop(name, None) is not None

    def activate_all(self, app: App) -> None:
        """Run ``activate`` on every plugin that has not been activated yet."""
        for name, plugin in self._plugins.items():
            if name in self._activated:
                continue
            try:
                plugin.activate(app)
                self._activated.add(name)
            except Exception:
                _log.exception("plugin %r failed to activate", name)

    def on_app_start(self, app: App) -> None:
        """Dispatch the app-start hook to all plugins."""
        for plugin in self._plugins.values():
            try:
                plugin.on_app_start(app)
            except Exception:
                _log.exception("plugin %r on_app_start failed", plugin.name)

    def on_app_stop(self, app: App) -> None:
        """Dispatch the app-stop hook to all plugins."""
        for plugin in self._plugins.values():
            try:
                plugin.on_app_stop(app)
            except Exception:
                _log.exception("plugin %r on_app_stop failed", plugin.name)

    def clear(self) -> None:
        """Drop all registered plugins and activation state."""
        self._plugins.clear()
        self._activated.clear()

    def __contains__(self, name: object) -> bool:
        return name in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)


#: The process-wide plugin registry.
plugins = PluginRegistry()
