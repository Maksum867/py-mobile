"""Tiny logging helper.

PyMobile never configures the root logger on import: a library that hijacks
logging is painful to embed. :func:`configure` is called explicitly by the CLI,
and on-device by :meth:`pymobile.core.app.App.run`.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import ClassVar

__all__ = ["get_logger", "configure", "LOGGER_NAME"]

LOGGER_NAME = "pymobile"

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


class _Formatter(logging.Formatter):
    """Compact, optionally coloured formatter."""

    _COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[2;37m",
        logging.INFO: "\033[36m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    _RESET = "\033[0m"

    def __init__(self, *, color: bool) -> None:
        super().__init__("%(message)s")
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        prefix = record.levelname.lower()
        if record.levelno <= logging.INFO:
            prefix = "•"
        if self.color:
            tint = self._COLORS.get(record.levelno, "")
            return f"{tint}{prefix}{self._RESET} {message}"
        return f"{prefix} {message}"


def supports_color(stream: object = None) -> bool:
    """Return ``True`` when ANSI colours are safe to emit."""
    stream = stream or sys.stderr
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def configure(level: str | int = "info", *, color: bool | None = None) -> logging.Logger:
    """Attach a single stderr handler to the ``pymobile`` logger."""
    logger = logging.getLogger(LOGGER_NAME)
    resolved = _LEVELS.get(level, level) if isinstance(level, str) else level
    logger.setLevel(resolved)
    logger.propagate = False
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_Formatter(color=supports_color() if color is None else color))
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
    logger.addHandler(handler)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a namespaced child of the framework logger."""
    if not name:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
