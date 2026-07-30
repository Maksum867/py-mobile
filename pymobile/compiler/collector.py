"""Source collection.

The fastest build is the one that copies the fewest files, so collection is a
first-class stage: it applies exclude globs, skips caches and reports exactly
what will be packaged.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..errors import ConfigError
from ..logging import get_logger

__all__ = ["SourceSet", "collect_sources"]

_log = get_logger("compiler.collector")

_ALWAYS_EXCLUDED_DIRS = frozenset({"__pycache__", ".git", ".hg", ".svn", ".mypy_cache",
                                   ".pytest_cache", ".ruff_cache", ".venv", "venv", "node_modules"})


@dataclass(frozen=True, slots=True)
class SourceSet:
    """The files that will go into the APK."""

    root: Path
    files: tuple[Path, ...]
    entrypoint: Path

    @property
    def total_bytes(self) -> int:
        """Combined size of all collected files."""
        return sum(path.stat().st_size for path in self.files)

    @property
    def count(self) -> int:
        """Number of collected files."""
        return len(self.files)

    def relative(self) -> Iterator[Path]:
        """Paths relative to the source root."""
        for path in self.files:
            yield path.relative_to(self.root)


def _match_pattern(text: str, pattern: str) -> bool:
    """Match ``text`` against a single gitignore-style glob pattern."""
    # ``dir/**`` — match anything *inside* the directory (we never collect
    # directory entries themselves, only files, so matching the literal
    # directory name is unnecessary and would incorrectly match a file
    # called ``dir``).
    if pattern.endswith("/**"):
        head = pattern[:-3]
        return text.startswith(head + "/")
    # A trailing slash means "directory only" and never matches a file path
    # the collector produces, so treat it like ``dir/**`` for safety.
    if pattern.endswith("/"):
        head = pattern[:-1]
        return text.startswith(head + "/")
    return fnmatch.fnmatch(text, pattern)


def _is_excluded(relative: Path, patterns: Sequence[str]) -> bool:
    """Whether a relative path matches any exclude glob.

    Semantics mirror gitignore so project-level patterns behave the way
    users expect:

    * a pattern that contains no ``/`` is matched against the file name
      and against every path suffix, so ``test_*.py`` catches ``test_app.py``
      at the root *and* ``pkg/test_foo.py``;
    * a pattern beginning with ``**/`` is unanchored in the same way, so
      ``**/__pycache__/**`` and ``**/*.pyc`` also match root-level files;
    * any other pattern containing ``/`` is anchored at the source root,
      so ``build/**`` matches only the top-level ``build/`` directory;
    * a leading ``/`` is accepted for readability and stripped before
      matching (``/tests/**`` ≡ ``tests/**``).
    """
    text = relative.as_posix()
    basename = relative.name
    parts = relative.parts
    for raw in patterns:
        pattern = raw.strip()
        if not pattern:
            continue
        if pattern.startswith("/"):
            pattern = pattern[1:]
        # ``**/`` at the front means "match anywhere"; keep the original so
        # the anchored check on the full path still works (e.g. ``__pycache__/x.py``
        # at the root must still match ``**/__pycache__/**``), and also try
        # the trimmed form when walking suffixes.
        anywhere = pattern.startswith("**/")
        if anywhere:
            trimmed = pattern[3:]
        else:
            trimmed = pattern
        anchored = (not anywhere) and ("/" in pattern)
        # Full-path anchored match.
        if _match_pattern(text, pattern):
            return True
        if anchored:
            continue
        # Unanchored — try the file name first (catches test_app.py at root),
        # then every trailing suffix of the path (catches nested matches).
        if _match_pattern(basename, trimmed):
            return True
        for index in range(1, len(parts)):
            suffix = "/".join(parts[index:])
            if _match_pattern(suffix, trimmed):
                return True
    return False


def collect_sources(
    source_dir: Path,
    entrypoint: Path,
    *,
    exclude: Sequence[str] = (),
    include_suffixes: Sequence[str] | None = None,
) -> SourceSet:
    """Walk ``source_dir`` and return the set of files to package.

    ``include_suffixes`` defaults to Python sources plus common asset types.
    """
    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise ConfigError(
            f"Source directory does not exist: {source_dir}",
            hint="Check `source_dir` in your project configuration.",
        )
    if not entrypoint.exists():
        raise ConfigError(
            f"Entry point not found: {entrypoint}",
            hint="Create the file or point `entrypoint` at an existing module.",
        )

    suffixes = (
        {s.lower() for s in include_suffixes}
        if include_suffixes is not None
        else {".py", ".json", ".txt", ".toml", ".png", ".jpg", ".jpeg", ".webp", ".ttf", ".otf"}
    )

    collected: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir)
        if any(part in _ALWAYS_EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() not in suffixes:
            continue
        if _is_excluded(relative, exclude):
            continue
        collected.append(path)

    if entrypoint not in collected:
        collected.insert(0, entrypoint)

    result = SourceSet(root=source_dir, files=tuple(collected), entrypoint=entrypoint)
    _log.debug("collected %d files (%d bytes)", result.count, result.total_bytes)
    return result
