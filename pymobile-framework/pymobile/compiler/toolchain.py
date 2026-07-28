"""Discovery of the native Android toolchain.

Building a real, installable APK needs four external tools plus a Java runtime:

* ``aapt2``      — compiles resources and links the binary manifest;
* ``d8``         — turns Java bytecode into ``classes.dex``;
* ``zipalign``   — aligns the archive so Android can mmap it;
* ``apksigner``  — signs the package (v1/v2/v3 schemes);
* ``javac``      — compiles the launcher activity;
* the NDK        — compiles the JNI bridge that embeds CPython.

This module only *locates* them and reports precisely what is missing, so the
user gets one actionable message instead of a deep stack trace.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..errors import ConfigError
from ..logging import get_logger

__all__ = ["Toolchain", "find_toolchain", "ToolchainError"]

_log = get_logger("compiler.toolchain")


class ToolchainError(ConfigError):
    """The Android SDK/NDK is missing or incomplete."""


def _first_existing(*candidates: Path | None) -> Path | None:
    """Return the first candidate that exists on disk."""
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    return None


@dataclass(slots=True)
class Toolchain:
    """Resolved paths to every tool required for a native build."""

    sdk: Path
    build_tools: Path
    platform_jar: Path
    java_home: Path
    ndk: Path | None = None

    # -- individual tools --------------------------------------------------
    @staticmethod
    def _executable(directory: Path, name: str, *, script: bool = False) -> Path:
        """Resolve a tool name to its platform-specific filename.

        On Windows the SDK ships ``aapt2.exe`` and wrapper scripts such as
        ``d8.bat``/``apksigner.bat``; on POSIX the bare name is used.
        """
        if platform.system() != "Windows":
            return directory / name
        suffixes = (".bat", ".cmd", ".exe") if script else (".exe", ".bat", ".cmd")
        for suffix in suffixes:
            candidate = directory / f"{name}{suffix}"
            if candidate.exists():
                return candidate
        return directory / f"{name}{suffixes[0]}"

    @property
    def aapt2(self) -> Path:
        """Resource compiler and linker."""
        return self._executable(self.build_tools, "aapt2")

    @property
    def d8(self) -> Path:
        """Java bytecode → Dalvik bytecode."""
        return self._executable(self.build_tools, "d8", script=True)

    @property
    def zipalign(self) -> Path:
        """Archive aligner."""
        return self._executable(self.build_tools, "zipalign")

    @property
    def apksigner(self) -> Path:
        """APK signer."""
        return self._executable(self.build_tools, "apksigner", script=True)

    @property
    def javac(self) -> Path:
        """Java compiler."""
        return self._executable(self.java_home / "bin", "javac")

    @property
    def keytool(self) -> Path:
        """Keystore generator, used for the debug key."""
        return self._executable(self.java_home / "bin", "keytool")

    @property
    def clang(self) -> Path | None:
        """NDK clang for arm64, or ``None`` when the NDK is absent.

        Not a ``cached_property``: this dataclass uses ``slots=True``, which
        leaves no ``__dict__`` for the cache to live in.
        """
        if self.ndk is None:
            return None
        suffix = ".cmd" if platform.system() == "Windows" else ""
        pattern = f"toolchains/llvm/prebuilt/*/bin/aarch64-linux-android21-clang{suffix}"
        return next(iter(sorted(self.ndk.glob(pattern))), None)

    @property
    def has_ndk(self) -> bool:
        """Whether the JNI bridge can be compiled."""
        return self.clang is not None

    # -- validation --------------------------------------------------------
    def verify(self, *, require_ndk: bool = False, require_javac: bool = False) -> None:
        """Raise :class:`ToolchainError` listing everything that is missing.

        ``javac`` and the NDK are only needed to rebuild the launcher classes
        and the JNI bridge from source; prebuilt copies ship with the package,
        so by default they are not required.
        """
        required: list[tuple[str, Path]] = [
            ("aapt2", self.aapt2),
            ("zipalign", self.zipalign),
            ("apksigner", self.apksigner),
            ("android.jar", self.platform_jar),
        ]
        if require_javac:
            required.extend([("javac", self.javac), ("d8", self.d8)])

        missing: list[str] = []
        for name, path in required:
            if not path.exists():
                missing.append(f"{name} ({path})")
        if require_ndk and not self.has_ndk:
            missing.append("NDK clang for arm64")
        # apksigner and keytool are JVM wrappers, so a JRE is always needed.
        if not self.keytool.exists():
            missing.append(f"keytool ({self.keytool})")
        if missing:
            raise ToolchainError(
                "Android toolchain is incomplete: " + ", ".join(missing),
                hint=(
                    "Run `pymobile setup-sdk` to install everything automatically, "
                    "or set ANDROID_HOME to an existing SDK."
                ),
            )

    def describe(self) -> str:
        """One-line summary for logs and ``pymobile doctor``."""
        ndk = "yes" if self.has_ndk else "no"
        return f"sdk={self.sdk} build-tools={self.build_tools.name} ndk={ndk}"


def _sdk_root(explicit: str | Path | None = None) -> Path | None:
    """Locate the Android SDK from an argument, the environment or defaults."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    for variable in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(variable)
        if value:
            return Path(value).expanduser().resolve()
    return _first_existing(
        Path.home() / ".andro" / "sdk",
        Path.home() / "Android" / "Sdk",
        Path.home() / "Library" / "Android" / "sdk",
        Path("/usr/lib/android-sdk"),
    )


def _java_home(sdk: Path | None) -> Path | None:
    """Locate a JDK (17+ preferred, as required by modern build-tools)."""
    value = os.environ.get("JAVA_HOME")
    if value and Path(value).exists():
        return Path(value)
    bundled = _first_existing(*sorted((Path.home() / ".andro").glob("jdk-17*"), reverse=True))
    if bundled is not None:
        return bundled
    if sdk is not None:
        embedded = sdk.parent / "jbr"
        if embedded.exists():
            return embedded
    javac = shutil.which("javac")
    if javac:
        return Path(javac).resolve().parent.parent
    return None


def find_toolchain(
    sdk: str | Path | None = None,
    *,
    build_tools_version: str | None = None,
    platform_api: int = 34,
) -> Toolchain:
    """Discover the Android toolchain.

    The newest installed build-tools and the newest platform at or above
    ``platform_api`` are chosen unless pinned explicitly.
    """
    root = _sdk_root(sdk)
    if root is None or not root.exists():
        raise ToolchainError(
            "Android SDK not found",
            hint=(
                "Set ANDROID_HOME to your SDK directory, or run "
                "`pymobile setup-sdk` to download it automatically."
            ),
        )

    build_tools_dir = root / "build-tools"
    if build_tools_version:
        build_tools = build_tools_dir / build_tools_version
    else:
        installed = sorted((p for p in build_tools_dir.glob("*") if p.is_dir()), reverse=True)
        if not installed:
            raise ToolchainError(
                f"No build-tools installed in {build_tools_dir}",
                hint="sdkmanager 'build-tools;34.0.0'",
            )
        build_tools = installed[0]

    platform_jar = root / "platforms" / f"android-{platform_api}" / "android.jar"
    if not platform_jar.exists():
        available = sorted((root / "platforms").glob("android-*"), reverse=True)
        if available:
            platform_jar = available[0] / "android.jar"

    java_home = _java_home(root)
    if java_home is None:
        raise ToolchainError(
            "No Java Development Kit found",
            hint="Install JDK 17+ and set JAVA_HOME.",
        )

    ndk_root = root / "ndk"
    ndk = next(iter(sorted((p for p in ndk_root.glob("*") if p.is_dir()), reverse=True)), None)

    toolchain = Toolchain(
        sdk=root,
        build_tools=build_tools,
        platform_jar=platform_jar,
        java_home=java_home,
        ndk=ndk,
    )
    _log.debug("toolchain: %s", toolchain.describe())
    return toolchain
