"""APK assembly.

An APK is a ZIP with a fixed internal layout, so packaging is done with
:mod:`zipfile` directly — no external archiver, no shell-out, minimal overhead.
Two details matter for size and reproducibility:

* deflate compression for everything except already-compressed assets;
* a fixed timestamp for every entry, so identical inputs give identical bytes.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ..logging import get_logger

__all__ = ["ApkPackager", "PackageResult", "FIXED_TIMESTAMP"]

_log = get_logger("compiler.packager")

#: Fixed ZIP timestamp (2000-01-01) for reproducible archives.
FIXED_TIMESTAMP = (2000, 1, 1, 0, 0, 0)

#: Entries that gain nothing from a second round of compression.
_STORED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".zip", ".so", ".ogg"})


@dataclass(frozen=True, slots=True)
class PackageResult:
    """Outcome of an APK write."""

    path: Path
    entries: int
    size: int

    @property
    def size_kb(self) -> float:
        """Artifact size in kilobytes."""
        return self.size / 1024


class ApkPackager:
    """Writes the APK archive."""

    def __init__(self, *, compress: bool = True) -> None:
        self.compress = compress

    def _compression_for(self, name: str) -> int:
        """Pick a compression method per entry."""
        if not self.compress:
            return zipfile.ZIP_STORED
        suffix = Path(name).suffix.lower()
        return zipfile.ZIP_STORED if suffix in _STORED_SUFFIXES else zipfile.ZIP_DEFLATED

    def _write(self, archive: zipfile.ZipFile, name: str, data: bytes) -> None:
        """Add one deterministic entry."""
        info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
        info.compress_type = self._compression_for(name)
        info.external_attr = 0o644 << 16
        archive.writestr(info, data)

    def build(
        self,
        output: Path,
        *,
        manifest: str,
        sources: Iterable[tuple[str, Path]],
        resources: Mapping[str, Path] | None = None,
        extra: Mapping[str, bytes] | None = None,
    ) -> PackageResult:
        """Write the APK.

        ``sources`` are ``(archive_name, file_path)`` pairs placed under
        ``assets/app/``; ``resources`` are ``(archive_name, file_path)`` pairs
        placed verbatim; ``extra`` holds in-memory files.
        """
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        entries = 0

        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                self._write(archive, "AndroidManifest.xml", manifest.encode("utf-8"))
                entries += 1

                for name, path in sorted(sources, key=lambda item: item[0]):
                    self._write(archive, f"assets/app/{name}", path.read_bytes())
                    entries += 1

                for name, path in sorted((resources or {}).items()):
                    self._write(archive, name, path.read_bytes())
                    entries += 1

                for name, payload in sorted((extra or {}).items()):
                    self._write(archive, name, payload)
                    entries += 1

            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)

        size = output.stat().st_size
        _log.debug("packaged %d entries into %s (%d bytes)", entries, output.name, size)
        return PackageResult(path=output, entries=entries, size=size)
