"""CPython-for-Android runtime management.

Downloads and caches the official CPython Android release published by
python.org since 3.14. The archive is fetched once into a user-level cache and
reused by every project, so only the first build pays the cost.

Archives are pinned by SHA-256 the same way JDK and command-line tools are:
an unverified tarball is never extracted.
"""

from __future__ import annotations

import hashlib
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

#: SHA-256 of the official python.org Android embeddable packages for
#: :data:`PYTHON_VERSION`. python.org's download page lists MD5 only; these
#: digests were computed from the HTTPS artifacts themselves.
_RUNTIME_SHA256 = {
    "arm64-v8a": "f09bd8ae86f408580881ae224e848805c267bb65b3111dc77b41bda79456da6c",
    "x86_64": "5c953df43e47c43ce55888acc5f09f6cac67f2e292480b906be37c14381516e7",
}


def runtime_cache_dir() -> Path:
    """Directory where downloaded runtimes are cached."""
    override = os.environ.get("PYMOBILE_CACHE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "pymobile" / "runtimes"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, target: Path, description: str, expected_sha256: str) -> Path:
    """Fetch and verify a pinned archive before it is ever extracted."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size == 0:
        _log.info("downloading %s…", description)
        temporary = target.with_suffix(target.suffix + ".part")
        try:
            with (
                urllib.request.urlopen(url, timeout=180) as response,
                temporary.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            os.replace(temporary, target)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise PyMobileError(
                f"Could not download {description}: {error}",
                hint=f"Download {url} manually and verify SHA-256 {expected_sha256}.",
            ) from error
    actual = _sha256(target)
    if actual.casefold() != expected_sha256.casefold():
        target.unlink(missing_ok=True)
        raise PyMobileError(
            f"Checksum verification failed for {description}",
            hint=f"Expected SHA-256 {expected_sha256}, got {actual}. The archive was deleted.",
        )
    return target


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
    expected = _RUNTIME_SHA256.get(abi)
    if expected is None:
        raise PyMobileError(
            f"No pinned SHA-256 for CPython {version} ABI {abi!r}",
            hint="Refuse to extract an unauthenticated runtime archive.",
        )

    target = runtime_cache_dir() / f"python-{version}-{abi}"
    prefix = target / "prefix"
    if (prefix / "lib").exists():
        _log.debug("runtime cache hit: %s", prefix)
        return prefix

    url = _BASE_URL.format(version=version, triplet=triplet)
    archive = target.parent / f"python-{version}-{triplet}.tar.gz"
    _download(url, archive, f"CPython {version} for {abi} (~21 MB)", expected)

    _log.debug("extracting %s", archive.name)
    target.mkdir(parents=True, exist_ok=True)
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
