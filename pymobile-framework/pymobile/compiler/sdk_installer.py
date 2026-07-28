"""Automatic Android SDK/NDK provisioning.

Native builds need ~4 GB of Google tooling. Asking a Python developer to
install Android Studio is a poor first experience, so ``pymobile setup-sdk``
fetches exactly the packages required — command-line tools, platform,
build-tools and NDK — into a private directory.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from ..errors import PyMobileError
from ..logging import get_logger

__all__ = ["install_sdk", "default_sdk_home", "REQUIRED_PACKAGES"]

_log = get_logger("compiler.sdk")

#: Everything needed to build an APK using the prebuilt JNI bridge (~450 MB).
MINIMAL_PACKAGES = (
    "platforms;android-34",
    "build-tools;34.0.0",
)

#: Adds the NDK, needed only to rebuild the native bridge from source (~2 GB).
REQUIRED_PACKAGES = (*MINIMAL_PACKAGES, "ndk;27.3.13750724")

_CMDLINE_TOOLS = {
    "Linux": "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip",
    "Darwin": "https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip",
    "Windows": "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip",
}

_JDK_BASE = (
    "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.13%2B11/"
)
#: host system -> (archive name, is_zip)
_JDK_ARCHIVES = {
    "Linux": ("OpenJDK17U-jdk_x64_linux_hotspot_17.0.13_11.tar.gz", False),
    "Windows": ("OpenJDK17U-jdk_x64_windows_hotspot_17.0.13_11.zip", True),
    "Darwin": ("OpenJDK17U-jdk_x64_mac_hotspot_17.0.13_11.tar.gz", False),
}


def default_sdk_home() -> Path:
    """Directory PyMobile installs the toolchain into."""
    override = os.environ.get("PYMOBILE_SDK_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".andro"


def _download(url: str, target: Path, description: str) -> Path:
    """Fetch a file unless it is already present."""
    if target.exists() and target.stat().st_size > 0:
        _log.debug("%s already downloaded", description)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    _log.info("downloading %s…", description)
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            target.write_bytes(response.read())
    except OSError as error:
        raise PyMobileError(
            f"Could not download {description}: {error}",
            hint=f"Download {url} manually and place it at {target}.",
        ) from error
    return target


def _ensure_jdk(home: Path) -> Path:
    """Return a JDK 17 path, downloading Temurin when necessary."""
    existing = sorted(home.glob("jdk-17*"), reverse=True)
    if existing:
        return existing[0]

    java_home = os.environ.get("JAVA_HOME")
    if java_home and (Path(java_home) / "bin" / "javac").exists():
        return Path(java_home)

    entry = _JDK_ARCHIVES.get(platform.system())
    if entry is None:
        raise PyMobileError(
            f"No automatic JDK download for {platform.system()}",
            hint="Install Temurin/OpenJDK 17 and set JAVA_HOME.",
        )
    filename, is_zip = entry
    archive = _download(_JDK_BASE + filename, home / filename, "JDK 17 (~190 MB)")

    _log.info("extracting the JDK…")
    if is_zip:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(home)
    else:
        with tarfile.open(archive) as tar:
            tar.extractall(home, filter="data")
    archive.unlink(missing_ok=True)

    found = sorted(home.glob("jdk-17*"), reverse=True)
    if not found:
        raise PyMobileError("JDK extraction produced no jdk-17* directory")
    # macOS archives nest the real home inside Contents/Home.
    nested = found[0] / "Contents" / "Home"
    return nested if nested.exists() else found[0]


def install_sdk(
    home: Path | None = None,
    *,
    packages: tuple[str, ...] = MINIMAL_PACKAGES,
    with_ndk: bool = False,
) -> Path:
    """Install the Android toolchain and return the SDK root.

    Defaults to the minimal set; pass ``with_ndk=True`` to also fetch the NDK,
    which is only required for rebuilding the native bridge.

    Safe to re-run: existing downloads and packages are reused.
    """
    if with_ndk:
        packages = REQUIRED_PACKAGES
    root = Path(home) if home else default_sdk_home()
    root.mkdir(parents=True, exist_ok=True)
    sdk = root / "sdk"

    jdk = _ensure_jdk(root)
    _log.debug("using JDK at %s", jdk)

    tools_bin = sdk / "cmdline-tools" / "latest" / "bin"
    script = "sdkmanager.bat" if platform.system() == "Windows" else "sdkmanager"
    sdkmanager = tools_bin / script
    if not sdkmanager.exists():
        url = _CMDLINE_TOOLS.get(platform.system())
        if url is None:
            raise PyMobileError(f"Unsupported host platform: {platform.system()}")
        archive = _download(url, root / "cmdline-tools.zip", "Android command-line tools (~150 MB)")
        _log.info("extracting the command-line tools…")
        staging = root / "_cmdline"
        shutil.rmtree(staging, ignore_errors=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(staging)
        destination = sdk / "cmdline-tools" / "latest"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(destination, ignore_errors=True)
        shutil.move(str(staging / "cmdline-tools"), str(destination))
        shutil.rmtree(staging, ignore_errors=True)
        archive.unlink(missing_ok=True)
        if platform.system() != "Windows":
            sdkmanager.chmod(0o755)

    environment = {
        **os.environ,
        "JAVA_HOME": str(jdk),
        "PATH": f"{jdk / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
    }

    _log.info("accepting SDK licences…")
    subprocess.run(
        [str(sdkmanager), f"--sdk_root={sdk}", "--licenses"],
        input="y\n" * 30,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    _log.info("installing %s (this can take several minutes)…", ", ".join(packages))
    completed = subprocess.run(
        [str(sdkmanager), f"--sdk_root={sdk}", *packages],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise PyMobileError(
            "sdkmanager failed to install the required packages",
            hint=detail[-800:] or "Check your connection and available disk space (~5 GB).",
        )
    return sdk
