"""Runtime platform detection.

The same application code runs twice: on a developer machine (preview / tests)
and inside an APK. Everything that must branch on that fact goes through this
module, so the check lives in exactly one place.
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from functools import lru_cache

__all__ = ["Platform", "current_platform", "is_android", "is_desktop"]


class Platform(str, Enum):
    """Supported runtime environments."""

    ANDROID = "android"
    DESKTOP = "desktop"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@lru_cache(maxsize=1)
def current_platform() -> Platform:
    """Detect the environment the interpreter is running in.

    Android is recognised by the markers set by the python-for-android
    bootstrap (``ANDROID_ARGUMENT``/``ANDROID_APP_PATH``) or by the Android
    system itself (``ANDROID_ROOT`` + ``ANDROID_DATA``).
    """
    env = os.environ
    if env.get("PYMOBILE_FORCE_PLATFORM"):
        return Platform(env["PYMOBILE_FORCE_PLATFORM"].strip().lower())
    if "ANDROID_ARGUMENT" in env or "ANDROID_APP_PATH" in env:
        return Platform.ANDROID
    if "ANDROID_ROOT" in env and "ANDROID_DATA" in env:
        return Platform.ANDROID
    if sys.platform == "android":  # Python 3.13+ native Android build
        return Platform.ANDROID
    return Platform.DESKTOP


def is_android() -> bool:
    """``True`` when running inside an Android application."""
    return current_platform() is Platform.ANDROID


def is_desktop() -> bool:
    """``True`` when running on a developer machine."""
    return current_platform() is Platform.DESKTOP
