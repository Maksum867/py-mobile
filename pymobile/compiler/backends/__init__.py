"""Build backends.

* :mod:`native` — full Android toolchain, produces an installable APK.
The default structural packager lives in :mod:`pymobile.compiler.packager`.
"""

from __future__ import annotations

from .native import NativeBackend, NativeBuildResult

__all__ = ["NativeBackend", "NativeBuildResult"]
