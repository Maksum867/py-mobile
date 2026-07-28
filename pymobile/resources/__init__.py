"""Packaged resources: project templates and the default application icon.

Access goes through :mod:`importlib.resources`, so everything keeps working
when PyMobile is installed as a zipped wheel.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from ..errors import ResourceError

__all__ = ["resource_path", "read_template", "default_icon_path", "templates_dir", "icons_dir"]

_PACKAGE = __name__


def resource_path(*parts: str) -> Path:
    """Absolute path to a packaged resource file."""
    try:
        base = resources.files(_PACKAGE)
    except ModuleNotFoundError as exc:  # pragma: no cover - broken installation
        raise ResourceError(f"Resource package missing: {exc}") from exc
    target = base.joinpath(*parts)
    path = Path(str(target))
    if not path.exists():
        raise ResourceError(
            f"Packaged resource not found: {'/'.join(parts)}",
            hint="Reinstall pymobile; the package data appears to be incomplete.",
        )
    return path


def templates_dir() -> Path:
    """Directory holding project templates."""
    return resource_path("templates")


def icons_dir() -> Path:
    """Directory holding built-in icons."""
    return resource_path("icons")


def read_template(name: str) -> str:
    """Read a template file as text."""
    return resource_path("templates", name).read_text(encoding="utf-8")


def default_icon_path() -> Path:
    """Path to the default Android-style launcher icon."""
    return resource_path("icons", "default_icon.png")
