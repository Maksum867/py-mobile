"""Compiler: turns a Python project into an Android APK."""

from __future__ import annotations

from .cache import BuildCache
from .collector import SourceSet, collect_sources
from .icon import IconSet, prepare_icons
from .manifest import build_manifest
from .packager import ApkPackager, PackageResult
from .pipeline import BuildPipeline, BuildResult, build_apk
from .scaffold import create_project

__all__ = [
    "BuildPipeline",
    "BuildResult",
    "build_apk",
    "build_manifest",
    "collect_sources",
    "SourceSet",
    "prepare_icons",
    "IconSet",
    "ApkPackager",
    "PackageResult",
    "BuildCache",
    "create_project",
]
