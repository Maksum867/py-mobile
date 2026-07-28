"""Application icon handling.

Rules:

* a custom icon given in the config is validated and resized to every density;
* when none is set, the packaged default Android-style icon is used;
* Pillow is optional — without it a valid single-density icon is still emitted,
  so a build never fails just because an image library is missing.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..errors import ResourceError
from ..logging import get_logger
from ..resources import default_icon_path

__all__ = ["IconSet", "prepare_icons", "DENSITIES"]

_log = get_logger("compiler.icon")

#: Android mipmap densities and their icon edge length in pixels.
DENSITIES: dict[str, int] = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

_SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True, slots=True)
class IconSet:
    """Result of icon preparation."""

    source: Path
    is_default: bool
    files: dict[str, Path]

    @property
    def densities(self) -> list[str]:
        """Densities that were generated."""
        return sorted(self.files)


def _validate_source(icon: Path) -> None:
    """Fail early with actionable messages for a bad icon path."""
    if not icon.exists():
        raise ResourceError(
            f"Icon not found: {icon}",
            hint="Check the `icon` path in pymobile.toml, or remove it to use the default.",
        )
    if icon.suffix.lower() not in _SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(_SUPPORTED_SUFFIXES))
        raise ResourceError(
            f"Unsupported icon format: {icon.suffix or 'no extension'}",
            hint=f"Use one of: {supported}. A square PNG of at least 512x512 works best.",
        )
    if icon.stat().st_size == 0:
        raise ResourceError(f"Icon file is empty: {icon}")


def prepare_icons(icon: Path | None, output_dir: Path) -> IconSet:
    """Write ``icon.png`` into ``mipmap-*`` folders under ``output_dir``.

    Falls back to the bundled default when ``icon`` is ``None``.
    """
    is_default = icon is None
    source = icon if icon is not None else default_icon_path()
    _validate_source(source)

    output_dir.mkdir(parents=True, exist_ok=True)
    resized = _resize_all(source, output_dir)
    if resized is None:
        resized = _copy_all(source, output_dir)
        _log.debug("Pillow unavailable: icon copied without resizing")

    _log.debug("prepared %d icon densities (default=%s)", len(resized), is_default)
    return IconSet(source=source, is_default=is_default, files=resized)


def _resize_all(source: Path, output_dir: Path) -> dict[str, Path] | None:
    """Resize the icon for every density; ``None`` when Pillow is missing."""
    try:
        from PIL import Image
    except ImportError:
        return None

    # Pillow >= 9.1 exposes the filters via Image.Resampling; keep the old
    # attribute as a fallback so older installations still work.
    resample = getattr(Image, "Resampling", Image).LANCZOS

    files: dict[str, Path] = {}
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        for density, size in DENSITIES.items():
            target_dir = output_dir / f"mipmap-{density}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "icon.png"
            rgba.resize((size, size), resample).save(target, format="PNG", optimize=True)
            files[density] = target
    return files


def _copy_all(source: Path, output_dir: Path) -> dict[str, Path]:
    """Copy the icon unchanged into each density folder."""
    files: dict[str, Path] = {}
    for density in DENSITIES:
        target_dir = output_dir / f"mipmap-{density}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "icon.png"
        shutil.copyfile(source, target)
        files[density] = target
    return files
