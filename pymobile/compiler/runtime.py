"""CPython-for-Android runtime management.

Downloads and caches the official CPython Android release published by
python.org since 3.14. The archive is fetched once into a user-level cache and
reused by every project, so only the first build pays the cost.
"""

from __future__ import annotations

import os
import shutil
import tarfile
import urllib.request
from pathlib import Path

from ..errors import PyMobileError
from ..logging import get_logger

__all__ = ["ensure_runtime", "runtime_cache_dir", "PYTHON_VERSION", "ABI_TRIPLETS"]

_log = get_logger("compiler.runtime")

#: CPython version shipped with official Android binaries.
PYTHON_VERSION = "3.14.0"

#: Android ABI → GNU triplet used in the release filename.
ABI_TRIPLETS = {
    "arm64-v8a": "aarch64-linux-android",
    "x86_64": "x86_64-linux-android",
}

_BASE_URL = "https://www.python.org/ftp/python/{version}/python-{version}-{triplet}.tar.gz"


def runtime_cache_dir() -> Path:
    """Directory where downloaded runtimes are cached."""
    override = os.environ.get("PYMOBILE_CACHE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "pymobile" / "runtimes"


def ensure_runtime(abi: str = "arm64-v8a", *, version: str = PYTHON_VERSION) -> Path:
    """Return the extracted runtime prefix, downloading it if necessary.

    The returned directory contains ``lib/libpython3.14.so``,
    ``lib/python3.14/`` (the standard library) and ``include/``.
    """
    triplet = ABI_TRIPLETS.get(abi)
    if triplet is None:
        raise PyMobileError(
            f"No official CPython build for ABI {abi!r}",
            hint=f"Supported ABIs: {', '.join(sorted(ABI_TRIPLETS))}",
        )

    target = runtime_cache_dir() / f"python-{version}-{abi}"
    prefix = target / "prefix"
    if (prefix / "lib").exists():
        _log.debug("runtime cache hit: %s", prefix)
        return prefix

    url = _BASE_URL.format(version=version, triplet=triplet)
    target.mkdir(parents=True, exist_ok=True)
    archive = target.parent / f"python-{version}-{triplet}.tar.gz"

    if not archive.exists():
        _log.info("downloading CPython %s for %s (~21 MB, one time)", version, abi)
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                archive.write_bytes(response.read())
        except OSError as error:
            raise PyMobileError(
                f"Could not download the Python runtime: {error}",
                hint=f"Check your connection, or download {url} manually into {archive.parent}.",
            ) from error

    _log.debug("extracting %s", archive.name)
    try:
        with tarfile.open(archive) as tar:
            tar.extractall(target, filter="data")
    except (tarfile.TarError, OSError) as error:
        shutil.rmtree(target, ignore_errors=True)
        raise PyMobileError(f"Corrupt runtime archive: {error}") from error

    if not (prefix / "lib").exists():
        raise PyMobileError(
            "Unexpected runtime layout: prefix/lib is missing",
            hint="Delete the cache directory and retry.",
        )
    return prefix
