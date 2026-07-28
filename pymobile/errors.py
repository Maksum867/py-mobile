"""Framework-wide error hierarchy.

Every exception raised by PyMobile inherits from :class:`PyMobileError`, so an
application (or a host tool) can catch the whole framework with one clause.
Errors carry an optional ``hint`` describing how to fix the problem — the CLI
prints it right under the message.
"""

from __future__ import annotations

__all__ = [
    "PyMobileError",
    "ConfigError",
    "BridgeError",
    "PlatformError",
    "PermissionError_",
    "NetworkError",
    "ResourceError",
]


class PyMobileError(Exception):
    """Base class for all PyMobile errors."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class ConfigError(PyMobileError):
    """The project configuration is missing or invalid."""


class BridgeError(PyMobileError):
    """A call into the Android platform layer failed."""


class PlatformError(PyMobileError):
    """The requested feature is not available on the current platform."""


class PermissionError_(PyMobileError):
    """A runtime Android permission was denied by the user."""

    def __init__(self, permission: str, *, hint: str | None = None) -> None:
        super().__init__(f"Permission denied: {permission}", hint=hint)
        self.permission = permission


class NetworkError(PyMobileError):
    """An HTTP request could not be completed."""


class ResourceError(PyMobileError):
    """A packaged resource (template, icon) could not be read."""
