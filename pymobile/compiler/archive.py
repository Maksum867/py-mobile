"""Archive extraction helpers compatible with Python 3.10+.

Python 3.12 added ``TarFile.extractall(..., filter="data")`` which rejects
absolute paths, ``..`` traversal and links escaping the target directory.
On Python 3.10/3.11 the same guarantees are enforced manually before the
archive is extracted, so the toolchain keeps working on every supported
interpreter.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

__all__ = ["safe_extractall"]


def safe_extractall(archive: tarfile.TarFile, target: Path) -> None:
    """Extract ``archive`` into ``target`` with ``data``-filter semantics.

    Uses the interpreter's native ``filter="data"`` when available (3.12+)
    and falls back to an explicit validation pass on older versions.
    """
    try:
        archive.extractall(target, filter="data")
        return
    except TypeError:  # pragma: no cover - Python < 3.12
        pass

    # Python 3.10/3.11: validate every member against the rules of the
    # ``data`` filter, then extract without a filter.
    base = target.resolve()
    for member in archive.getmembers():
        member_path = (base / member.name).resolve()
        if not member_path.is_relative_to(base):
            raise tarfile.TarError(f"unsafe member name in archive: {member.name!r}")
        if member.islnk() or member.issym():
            link_path = (base / member.linkname).resolve()
            if not link_path.is_relative_to(base):
                raise tarfile.TarError(f"unsafe link in archive: {member.linkname!r}")
        if member.isdev():
            raise tarfile.TarError(f"device entry in archive: {member.name!r}")
    archive.extractall(target)
