"""The build pipeline.

The compiler is a sequence of small, independent stages:

``validate → collect → compile → icons → manifest → package``

Each stage is a plain function with an explicit input and output, timed and
logged individually. Adding a stage (signing, native libs, obfuscation) means
appending to the list — no existing stage has to change.
"""

from __future__ import annotations

import compileall
import hashlib
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.config import ProjectConfig
from ..errors import PyMobileError
from ..logging import get_logger
from .backends.native import NativeBackend
from .cache import BuildCache, fingerprint_files
from .collector import SourceSet, collect_sources
from .icon import IconSet, prepare_icons
from .manifest import build_manifest
from .packager import ApkPackager, PackageResult
from .runtime import ensure_runtime
from .toolchain import find_toolchain

__all__ = ["BuildPipeline", "BuildResult", "StageTiming", "build_apk"]

_log = get_logger("compiler")


@dataclass(frozen=True, slots=True)
class StageTiming:
    """How long one stage took."""

    name: str
    seconds: float


@dataclass(slots=True)
class BuildResult:
    """Everything the caller needs to know about a build."""

    apk: Path
    size: int
    entries: int
    duration: float
    cached: bool = False
    native: bool = False
    icon_is_default: bool = True
    timings: list[StageTiming] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def size_kb(self) -> float:
        """APK size in kilobytes."""
        return self.size / 1024

    def summary(self) -> str:
        """One-line human-readable summary."""
        state = "cached" if self.cached else "built"
        if self.native:
            return (
                f"{state} {self.apk.name} — {self.size / (1024 * 1024):.1f} MB, "
                f"installable, {self.duration:.1f}s"
            )
        return (
            f"{state} {self.apk.name} — {self.size_kb:.1f} KB, "
            f"{self.entries} entries, {self.duration:.2f}s"
        )


class BuildPipeline:
    """Runs the stages that turn a project into an APK."""

    def __init__(
        self,
        config: ProjectConfig,
        *,
        use_cache: bool = True,
        native: bool = False,
        on_stage: Callable[[str], None] | None = None,
        keystore: Path | None = None,
        keystore_password: str | None = None,
        key_alias: str | None = None,
        key_password: str | None = None,
    ) -> None:
        self.config = config
        self.use_cache = use_cache
        self.native = native
        self.on_stage = on_stage
        self.keystore = keystore
        self.keystore_password = keystore_password
        self.key_alias = key_alias
        self.key_password = key_password
        self.warnings: list[str] = []
        self._timings: list[StageTiming] = []

    # -- helpers -----------------------------------------------------------
    def _stage(self, name: str, action: Callable[[], Any]) -> Any:
        """Run one stage, timing it and reporting progress."""
        if self.on_stage is not None:
            self.on_stage(name)
        started = time.perf_counter()
        try:
            result = action()
        except PyMobileError:
            raise
        except Exception as exc:
            raise PyMobileError(
                f"Build stage {name!r} failed: {exc}",
                hint="Run with --verbose for the full traceback.",
            ) from exc
        elapsed = time.perf_counter() - started
        self._timings.append(StageTiming(name, elapsed))
        _log.debug("stage %s finished in %.3fs", name, elapsed)
        return result

    # -- stages ------------------------------------------------------------
    def _validate(self) -> None:
        """Re-check the configuration and warn about likely mistakes."""
        self.config.validate()
        permissions = {str(p) for p in self.config.permissions}
        if "android.permission.INTERNET" not in permissions and self._uses_http():
            self.warnings.append(
                "Your code uses HttpClient but android.permission.INTERNET is not "
                "declared; HTTP requests will fail on device."
            )
        if self.config.target_sdk >= 33 and "android.permission.POST_NOTIFICATIONS" not in (
            permissions
        ):
            self.warnings.append(
                "targetSdk >= 33 without POST_NOTIFICATIONS: notifications stay hidden."
            )
        if self.config.no_ssl and self._uses_http():
            self.warnings.append(
                "Built with --no-ssl but code uses HttpClient; HTTPS requests will fail."
            )

    def _uses_http(self) -> bool:
        """Best-effort scan of the app sources for HTTP client usage.

        Keeps the missing-INTERNET warning from firing on apps that never
        touch the network. Only ``.py`` files are inspected and any read
        error simply suppresses the warning rather than failing the build.
        """
        markers = ("HttpClient", "app.http", ".http.")
        source = self.config.source_path
        if not source.is_dir():
            return False
        for path in source.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(marker in text for marker in markers):
                return True
        return False

    def _check_requested_permissions(self, sources: SourceSet) -> None:
        """Warn about permissions used in code but missing from the config.

        Android denies undeclared runtime permissions without showing a dialog,
        which is almost impossible to debug from the app side.
        """
        import re

        declared = {str(p).rsplit(".", 1)[-1] for p in self.config.permissions}
        pattern = re.compile(r"Permission\.([A-Z_]+)\b")
        used: set[str] = set()
        for path in sources.files:
            if path.suffix != ".py":
                continue
            try:
                used.update(pattern.findall(path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue

        missing = sorted(used - declared)
        if missing:
            names = ", ".join(f"android.permission.{name}" for name in missing)
            self.warnings.append(
                f"requested in code but not declared in pymobile.toml: {names} — "
                "Android will deny them without showing a dialog"
            )

    def _collect(self) -> SourceSet:
        """Gather the files that go into the APK."""
        return collect_sources(
            self.config.source_path,
            self.config.entrypoint_path,
            exclude=self.config.exclude,
        )

    def _compile_sources(self, sources: SourceSet, workdir: Path) -> list[tuple[str, Path]]:
        """Copy sources into the work dir, optionally as bytecode only.

        Shipping ``.pyc`` instead of ``.py`` cuts both APK size and app start
        time, since the device never has to compile at runtime.
        """
        staged = workdir / "app"
        staged.mkdir(parents=True, exist_ok=True)
        entries: list[tuple[str, Path]] = []

        for absolute in sources.files:
            relative = absolute.relative_to(sources.root)
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(absolute, target)
            entries.append((relative.as_posix(), target))

        # A native build runs CPython 3.14 on the device, while this process may
        # be any other version. .pyc files are version-locked, so ship sources.
        if not self.config.optimize or self.native:
            return entries

        quiet = 2
        optimize_level = 2 if self.config.strip_debug else 1
        compileall.compile_dir(
            str(staged),
            quiet=quiet,
            optimize=optimize_level,
            legacy=True,
            force=True,
        )

        compiled: list[tuple[str, Path]] = []
        for name, path in entries:
            if path.suffix != ".py":
                compiled.append((name, path))
                continue
            bytecode = path.with_suffix(".pyc")
            if bytecode.exists():
                compiled.append((f"{name}c", bytecode))
            else:  # syntax error: keep the source so the failure is visible
                self.warnings.append(f"{name} could not be byte-compiled; shipping source")
                compiled.append((name, path))
        return compiled

    def _icons(self, workdir: Path) -> IconSet:
        """Generate launcher icons (custom or default)."""
        return prepare_icons(self.config.icon_path, workdir / "res")

    def _manifest(self) -> str:
        """Render AndroidManifest.xml."""
        return build_manifest(self.config)

    def _package(
        self,
        output: Path,
        manifest: str,
        entries: list[tuple[str, Path]],
        icons: IconSet,
        sources: SourceSet,
    ) -> PackageResult:
        """Write the final archive."""
        resources = {
            f"res/mipmap-{density}/icon.png": path for density, path in icons.files.items()
        }
        metadata = (
            f"name={self.config.name}\n"
            f"package={self.config.package}\n"
            f"version={self.config.version}\n"
            f"entrypoint={sources.entrypoint.relative_to(sources.root).as_posix()}\n"
            f"optimize={int(self.config.optimize)}\n"
        )
        packager = ApkPackager(compress=True)
        return packager.build(
            output,
            manifest=manifest,
            sources=entries,
            resources=resources,
            extra={"assets/pymobile.properties": metadata.encode("utf-8")},
        )

    # -- entry point -------------------------------------------------------
    def run(self) -> BuildResult:
        """Execute every stage and return the result."""
        started = time.perf_counter()
        self.warnings.clear()
        self._timings.clear()

        self._stage("validate", self._validate)
        sources: SourceSet = self._stage("collect", self._collect)
        self._check_requested_permissions(sources)

        output_dir = self.config.output_path
        output_dir.mkdir(parents=True, exist_ok=True)
        apk_path = output_dir / self.config.apk_name

        cache = BuildCache(output_dir)
        fingerprint = self._fingerprint(sources)
        if self.use_cache:
            cached = cache.is_fresh(fingerprint)
            if cached is not None:
                duration = time.perf_counter() - started
                _log.info("no changes detected; reusing %s", cached.name)
                return BuildResult(
                    apk=cached,
                    size=cached.stat().st_size,
                    entries=0,
                    duration=duration,
                    cached=True,
                    timings=list(self._timings),
                    warnings=list(self.warnings),
                )

        with tempfile.TemporaryDirectory(prefix="pymobile-build-") as temporary:
            workdir = Path(temporary)
            entries = self._stage("compile", lambda: self._compile_sources(sources, workdir))
            icons: IconSet = self._stage("icons", lambda: self._icons(workdir))

            if self.native:
                result = self._run_native(workdir, entries, icons, apk_path, started)
                cache.save(fingerprint, result.apk)
                return result

            manifest: str = self._stage("manifest", self._manifest)
            package: PackageResult = self._stage(
                "package", lambda: self._package(apk_path, manifest, entries, icons, sources)
            )

        cache.save(fingerprint, package.path)
        duration = time.perf_counter() - started
        return BuildResult(
            apk=package.path,
            size=package.size,
            entries=package.entries,
            duration=duration,
            cached=False,
            icon_is_default=icons.is_default,
            timings=list(self._timings),
            warnings=list(self.warnings),
        )

    def _run_native(
        self,
        workdir: Path,
        entries: list[tuple[str, Path]],
        icons: IconSet,
        apk_path: Path,
        started: float,
    ) -> BuildResult:
        """Build a real, installable APK using the Android toolchain."""
        toolchain = self._stage("toolchain", find_toolchain)
        # The NDK is optional: without it the packaged prebuilt JNI bridge is
        # used, which saves users a 2 GB download.
        toolchain.verify(require_ndk=False)

        runtime = self._stage("runtime", lambda: ensure_runtime(self.config.abis[0]))
        backend = NativeBackend(self.config, toolchain, runtime, abi=self.config.abis[0])

        native_dir = self._stage("jni", lambda: backend.compile_jni(workdir))
        dex = self._stage("dex", lambda: backend.compile_java(workdir))
        base = self._stage("resources", lambda: backend.link_resources(workdir, icons.files))
        assets = self._stage("assets", lambda: backend.collect_assets(entries))
        signed = self._stage(
            "sign",
            lambda: backend.package(base, dex, native_dir, assets, apk_path, workdir),
        )
        verified = self._stage("verify", lambda: backend.verify(signed))
        if not verified:
            self.warnings.append("apksigner could not verify the signature")
        self.warnings.extend(backend.warnings)

        duration = time.perf_counter() - started
        return BuildResult(
            apk=signed,
            size=signed.stat().st_size,
            entries=len(assets) + 2,
            duration=duration,
            cached=False,
            native=True,
            icon_is_default=icons.is_default,
            timings=list(self._timings),
            warnings=list(self.warnings),
        )

    def _fingerprint(self, sources: SourceSet) -> str:
        """Hash of every input that can change the artifact.

        The configuration part uses blake2b rather than the built-in ``hash``:
        string hashing is salted per interpreter process, which would make the
        fingerprint differ on every run and defeat the cache entirely.
        """
        paths = list(sources.files)
        icon = self.config.icon_path
        if icon is not None and icon.exists():
            paths.append(icon)
        config_digest = hashlib.blake2b(
            repr(sorted(self.config.to_dict().items())).encode("utf-8"), digest_size=8
        ).hexdigest()
        return f"{fingerprint_files(paths)}:{config_digest}"


def build_apk(
    config: ProjectConfig, *, use_cache: bool = True, native: bool = False
) -> BuildResult:
    """Build an APK from a project configuration.

    With ``native=True`` the full Android toolchain is used and the result is a
    signed, installable APK; otherwise a fast structural package is produced.
    """
    return BuildPipeline(config, use_cache=use_cache, native=native).run()
