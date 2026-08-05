"""Command line interface.

Sub-commands: ``init``, ``build``, ``run``, ``info``, ``clean``, ``doctor``.
Every command returns an exit code; :func:`main` is the console-script entry
point declared in ``pyproject.toml``.

Errors are printed as a short message plus an actionable hint — tracebacks only
appear with ``--verbose``, because a build tool that dumps a stack trace at a
user who typed a wrong package name is not helpful.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import shutil
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .compiler.pipeline import BuildPipeline
from .compiler.scaffold import create_project
from .core.config import CONFIG_FILENAME, ProjectConfig, load_config
from .errors import PyMobileError
from .logging import configure, get_logger, supports_color

__all__ = ["main", "build_parser"]

_log = get_logger("cli")


# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------
class _Out:
    """Minimal styled console output."""

    def __init__(self) -> None:
        self.color = supports_color(sys.stdout)

    def _paint(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def ok(self, message: str) -> None:
        # stdout is block-buffered when piped while stderr is not, so progress
        # lines are flushed to keep them in order with warnings and errors.
        print(self._paint("✓", "32") + f" {message}", flush=True)

    def info(self, message: str) -> None:
        print(self._paint("•", "36") + f" {message}", flush=True)

    def warn(self, message: str) -> None:
        print(self._paint("!", "33") + f" {message}", file=sys.stderr)

    def error(self, message: str) -> None:
        print(self._paint("✗", "31") + f" {message}", file=sys.stderr)

    def hint(self, message: str) -> None:
        print(f"  {self._paint('hint:', '2;37')} {message}", file=sys.stderr)

    def field(self, label: str, value: object) -> None:
        print(f"  {label:<14} {value}", flush=True)


_out = _Out()


def _invocation() -> str:
    """How the user launched us: ``pymobile`` or ``python -m pymobile``.

    pip's Scripts directory is frequently missing from PATH on Windows, so
    echoing back a bare ``pymobile ...`` would print a command that does not
    work for that user.
    """
    launched_as_module = Path(sys.argv[0]).name in ("__main__.py", "cli.py")
    if launched_as_module:
        return f"{Path(sys.executable).name} -m pymobile"
    return "pymobile"


def _export_command(name: str, value: object) -> str:
    """Render an environment-variable assignment for the host shell."""
    if platform.system() == "Windows":
        return f'$env:{name} = "{value}"'
    return f"export {name}={value}"


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_init(args: argparse.Namespace) -> int:
    """Create a new project."""
    directory = Path(args.directory).resolve()
    name = args.name or directory.name.replace("-", " ").replace("_", " ").title()
    result = create_project(directory, name, package=args.package, force=args.force)
    _out.ok(f"created project {name!r} in {result.directory}")
    for path in result.files:
        _out.field("", path.relative_to(result.directory))
    print()
    _out.info(f"cd {result.directory.name} && {_invocation()} build --native")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """Compile the project into an APK."""
    config = _load(args)
    if args.icon:
        config.icon = args.icon
    if args.output:
        config.output_dir = args.output
    config.optimize = getattr(args, "optimize", False)
    if getattr(args, "minimal_stdlib", False):
        config.minimal_stdlib = True
    if getattr(args, "no_ssl", False):
        config.no_ssl = True
    config.validate()

    if args.clean:
        _clean(config)

    native = getattr(args, "native", False)
    if native:
        _out.info("native build: this may take a few minutes on the first run")
    pipeline = BuildPipeline(
        config,
        use_cache=not args.no_cache and not args.clean,
        native=native,
        on_stage=lambda stage: _out.info(f"{stage}…") if args.verbose else None,
    )
    result = pipeline.run()

    for warning in result.warnings:
        _out.warn(warning)

    if result.cached:
        size = (
            f"{result.size / (1024 * 1024):.1f} MB"
            if result.size >= 1024 * 1024
            else f"{result.size_kb:.1f} KB"
        )
        _out.ok(f"up to date: {result.apk.name} ({size})")
        _out.hint("use --clean to force a full rebuild")
        return 0

    _out.ok(result.summary())
    _out.field("apk", result.apk)
    _out.field("icon", "default" if result.icon_is_default else config.icon)
    if result.native:
        _out.field("install", f"adb install -r {result.apk.name}")
    if args.verbose:
        for timing in result.timings:
            _out.field(timing.name, f"{timing.seconds * 1000:.0f} ms")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Import the entry point and render the first screen on the desktop."""
    config = _load(args)
    entry = _entrypoint(config)

    if getattr(args, "web", False):
        return _run_web(config, entry, args)
    if getattr(args, "gui", False):
        return _run_gui(config, entry)

    _out.info(f"running {entry.name} in desktop preview mode")
    _execute(config, entry)

    from .core.bridge import get_bridge
    from .core.ui.preview import render_ascii

    # last_tree lives on the stub bridges; the abstract Bridge has no such
    # attribute, so read it defensively.
    tree = getattr(get_bridge(), "last_tree", None)
    if tree is None:
        raise PyMobileError(
            "The app rendered nothing.",
            hint="Make sure the entry point calls App(...).run(SomeScreen()).",
        )
    print(render_ascii(tree, title=config.name))
    _out.hint("use --gui for a clickable window")
    return 0


def _run_gui(config: ProjectConfig, entry: Path) -> int:
    """Run the app in an interactive Tkinter window."""
    from .core.bridge import GuiBridge, set_bridge
    from .core.ui.gui import GuiPreview, tkinter_available

    if not tkinter_available():
        raise PyMobileError(
            "Tkinter is not available in this Python installation",
            hint="Install it (Debian/Ubuntu: `sudo apt install python3-tk`), "
            "or use `pymobile preview` for a text picture.",
        )

    from .core.app import App

    bridge = GuiBridge(verbose=False)
    set_bridge(bridge)
    _execute(config, entry)
    app = App.current()
    if app is None:
        raise PyMobileError(
            "No running application was found in the entry point.",
            hint="Make sure it calls App(...).run(SomeScreen()) before returning.",
        )

    _out.ok(f"{config.name} is running — close the window to stop")
    try:
        preview = GuiPreview(app, title=config.name)
        bridge.attach(preview)
        preview.run()
    except Exception as error:  # pragma: no cover - display problems
        raise PyMobileError(
            f"Could not open the preview window: {error}",
            hint="On a headless machine use `pymobile preview` instead.",
        ) from error
    return 0


def _run_web(config: ProjectConfig, entry: Path, args: argparse.Namespace) -> int:
    """Serve the app to a browser."""
    from .core.app import App
    from .core.bridge import WebBridge, set_bridge
    from .core.ui.web import WebPreview

    bridge = WebBridge(verbose=False)
    set_bridge(bridge)
    _execute(config, entry)
    app = App.current()
    if app is None:
        raise PyMobileError(
            "No running application was found in the entry point.",
            hint="Make sure it calls App(...).run(SomeScreen()) before returning.",
        )

    preview = WebPreview(app, host=args.host, port=args.port)
    bridge.attach(preview)
    _out.ok(f"{config.name} is running at http://{args.host}:{preview.port}")
    _out.info("press Ctrl+C to stop")
    with contextlib.suppress(KeyboardInterrupt):  # Ctrl+C is how you stop it
        preview.serve_forever()
    _out.ok("stopped")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Re-render the app whenever a source file changes."""
    from .core.watcher import FileWatcher

    config = _load(args)
    entry = _entrypoint(config)
    roots = [config.source_path]

    _out.info(f"watching {config.source_path} — press Ctrl+C to stop")
    _reload(config, entry, args)

    watcher = FileWatcher(roots, interval=args.interval)
    try:
        while True:
            changed = watcher.wait()
            names = ", ".join(path.name for path in changed[:3])
            if len(changed) > 3:
                names += f" (+{len(changed) - 3})"
            print()
            _out.info(f"changed: {names}")
            _reload(config, entry, args)
    except KeyboardInterrupt:  # pragma: no cover - interactive
        print()
        _out.ok("stopped watching")
        return 0


def _reload(config: ProjectConfig, entry: Path, args: argparse.Namespace) -> None:
    """Run the entry point once and show the result.

    Every reload starts from a clean module table for the project's own
    modules, so editing an imported helper takes effect too — a plain re-exec
    of main.py would keep the stale version cached in sys.modules.
    """
    from .core.bridge import StubBridge, set_bridge
    from .core.ui.preview import render_ascii, render_png

    started = time.perf_counter()
    bridge = StubBridge(verbose=False)
    set_bridge(bridge)
    _purge_project_modules(config.source_path)

    try:
        _execute(config, entry)
    except Exception as error:
        _out.error(f"{type(error).__name__}: {error}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return

    tree = bridge.last_tree
    if tree is None:
        _out.warn("the app rendered nothing")
        return

    elapsed = (time.perf_counter() - started) * 1000
    if args.png:
        render_png(tree, args.png)
        _out.ok(f"wrote {args.png} in {elapsed:.0f} ms")
    else:
        print(render_ascii(tree, show_ids=args.ids, title=config.name))
        _out.ok(f"rendered in {elapsed:.0f} ms")


def _purge_project_modules(source: Path) -> None:
    """Forget modules imported from the project so the next run re-reads them.

    Dropping the ``sys.modules`` entry is not enough on its own: CPython
    validates a cached ``.pyc`` against the source's mtime *and size*, and on
    filesystems with a coarse clock (tmpfs, overlayfs, network shares) a quick
    edit that happens to keep the length can match both. The import then
    silently returns yesterday's bytecode, and the reload appears to do
    nothing. Removing the project's caches keeps that from happening.
    """
    import importlib
    import shutil

    source = source.resolve()
    for name, module in list(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        try:
            path = Path(origin).resolve()
        except (OSError, ValueError):
            continue
        if path.is_relative_to(source) and not path.name.startswith("__main__"):
            del sys.modules[name]

    for cache in source.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    importlib.invalidate_caches()


def _entrypoint(config: ProjectConfig) -> Path:
    """Resolve and validate the configured entry point."""
    entry = config.entrypoint_path
    if not entry.exists():
        raise PyMobileError(
            f"Entry point not found: {entry}",
            hint="Check `entrypoint` in your configuration.",
        )
    return entry


def _execute(config: ProjectConfig, entry: Path) -> dict[str, object]:
    """Execute the entry point and return its namespace.

    The running :class:`~pymobile.core.app.App` is looked up afterwards and
    exposed as ``__pymobile_app__`` so callers do not have to guess the name
    the developer gave their application object.
    """
    if str(config.source_path) not in sys.path:
        sys.path.insert(0, str(config.source_path))
    namespace: dict[str, object] = {"__name__": "__main__", "__file__": str(entry)}
    exec(compile(entry.read_text(encoding="utf-8"), str(entry), "exec"), namespace)

    from .core.app import App

    # The app is usually created inside a main() function, so it is found
    # through the registry rather than by scanning the module namespace.
    namespace["__pymobile_app__"] = App.current()
    return namespace


def cmd_preview(args: argparse.Namespace) -> int:
    """Render the app's first screen as a picture on this machine."""
    from .core.bridge import StubBridge, set_bridge
    from .core.ui.preview import render_ascii, render_png

    config = _load(args)
    entry = _entrypoint(config)

    bridge = StubBridge(verbose=False)
    set_bridge(bridge)
    _execute(config, entry)

    tree = bridge.last_tree
    if tree is None:
        raise PyMobileError(
            "The app rendered nothing.",
            hint="Make sure the entry point calls App(...).run(SomeScreen()).",
        )

    if args.png:
        path = render_png(tree, args.png)
        _out.ok(f"wrote preview to {path}")
    else:
        print(render_ascii(tree, show_ids=args.ids, title=config.name))
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Print the resolved configuration."""
    config = _load(args)
    if args.json:
        print(json.dumps(config.to_dict(), indent=2, sort_keys=True))
        return 0

    _out.info(f"{config.name} {config.version} ({config.package})")
    _out.field("entrypoint", config.entrypoint_path)
    _out.field("source", config.source_path)
    _out.field("output", config.output_path)
    _out.field("apk", config.apk_name)
    _out.field("sdk", f"min {config.min_sdk} / target {config.target_sdk}")
    _out.field("abis", ", ".join(config.abis))
    _out.field("icon", config.icon or "default")
    _out.field("optimize", config.optimize)
    print("  permissions")
    for permission in sorted(config.permissions):
        _out.field("", permission)
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Remove build artifacts."""
    config = _load(args)
    removed = _clean(config)
    _out.ok(f"removed {removed}" if removed else "nothing to clean")
    return 0


def cmd_setup_sdk(args: argparse.Namespace) -> int:
    """Download and install the Android toolchain."""
    from .compiler.sdk_installer import default_sdk_home, install_sdk

    target_path = Path(args.path) if args.path else default_sdk_home()
    with_ndk = getattr(args, "with_ndk", False)
    size = "~2.7 GB" if with_ndk else "~800 MB"

    # Check whether the SDK directory already exists and has cached content
    already_installed = target_path.exists() and any(target_path.iterdir())

    if already_installed:
        _out.info(f"using cached Android toolchain ({target_path})")
    else:
        _out.info(f"installing the Android toolchain ({size}, one time)...")

    if not with_ndk:
        _out.info("using the prebuilt native bridge; pass --with-ndk to build it from source")

    sdk = install_sdk(Path(args.path) if args.path else None, with_ndk=with_ndk)

    if already_installed:
        _out.ok(f"toolchain verified: {sdk}")
    else:
        _out.ok(f"toolchain ready: {sdk}")

    _out.info(f"now run: {_invocation()} build --native")
    if not os.environ.get("ANDROID_HOME"):
        _out.hint(f"optional: {_export_command('ANDROID_HOME', sdk)}")

    _ = default_sdk_home
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check the environment and configuration."""
    problems = 0
    _out.info(f"pymobile {__version__} on Python {sys.version.split()[0]}")

    try:
        import PIL  # noqa: F401

        _out.ok("Pillow available — icons will be resized for every density")
    except ImportError:
        _out.warn("Pillow missing — icons are copied without resizing")
        _out.hint("pip install Pillow")

    try:
        config = _load(args)
    except PyMobileError as exc:
        _out.warn(f"no usable project here: {exc}")
        return 0

    _out.ok(f"configuration valid: {config.name} ({config.package})")
    if not config.entrypoint_path.exists():
        _out.error(f"entry point missing: {config.entrypoint_path}")
        problems += 1
    else:
        _out.ok(f"entry point found: {config.entrypoint}")

    icon = config.icon_path
    if icon is not None and not icon.exists():
        _out.error(f"icon missing: {icon}")
        problems += 1
    elif icon is not None:
        _out.ok(f"custom icon: {icon.name}")
    else:
        _out.ok("using the default icon")

    from .compiler.toolchain import ToolchainError, find_toolchain

    try:
        toolchain = find_toolchain()
        toolchain.verify()
        _out.ok(f"Android toolchain ready (build-tools {toolchain.build_tools.name})")
        if toolchain.has_ndk:
            _out.ok("NDK present — the native bridge can be rebuilt from source")
        else:
            _out.ok("using the prebuilt native bridge (no NDK needed)")
        _out.info(f"native APK builds available: {_invocation()} build --native")
    except (ToolchainError, PyMobileError) as exc:
        _out.warn(f"Android SDK not usable — only structural builds are available: {exc}")
        _out.hint("run `pymobile setup-sdk` to install it automatically")

    if problems:
        _out.error(f"{problems} problem(s) found")
        return 1
    _out.ok("everything looks good")
    return 0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _load(args: argparse.Namespace) -> ProjectConfig:
    """Load the project configuration honouring ``--config``."""
    return load_config(getattr(args, "config", None) or Path.cwd())


def _clean(config: ProjectConfig) -> str:
    """Delete the output directory; returns what was removed."""
    output = config.output_path
    if output.exists():
        shutil.rmtree(output)
        return str(output)
    return ""


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser.

    ``--verbose`` and ``--config`` are attached both globally and to every
    sub-command, so ``pymobile -v build`` and ``pymobile build -v`` both work —
    users should not have to remember where a flag belongs.
    """
    # SUPPRESS keeps unset flags out of the namespace, so a sub-command does
    # not silently reset a value given before the sub-command name.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="show detailed output",
    )
    common.add_argument(
        "-c",
        "--config",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help=f"path to {CONFIG_FILENAME} or a project directory",
    )

    parser = argparse.ArgumentParser(
        prog="pymobile",
        description="Build Android applications with Python.",
        epilog="Docs: https://github.com/Maksum867/py-mobile",
        parents=[common],
    )
    parser.add_argument("--version", action="version", version=f"pymobile {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    init = sub.add_parser("init", help="create a new project", parents=[common])
    init.add_argument("directory", nargs="?", default=".", help="target directory")
    init.add_argument("-n", "--name", help="application name")
    init.add_argument("-p", "--package", help="package id, e.g. com.example.app")
    init.add_argument("-f", "--force", action="store_true", help="write into a non-empty directory")
    init.set_defaults(func=cmd_init)

    build = sub.add_parser("build", help="compile the project into an APK", parents=[common])
    build.add_argument("-o", "--output", help="output directory")
    build.add_argument("-i", "--icon", help="path to a custom launcher icon")
    build.add_argument(
        "--native",
        action="store_true",
        help="build a real, signed, installable APK (needs the Android SDK/NDK)",
    )
    build.add_argument("--clean", action="store_true", help="rebuild from scratch")
    build.add_argument("--no-cache", action="store_true", help="ignore the incremental cache")
    build.add_argument("--optimize", action="store_true", help="ship bytecode instead of sources")
    build.add_argument(
        "--minimal-stdlib",
        action="store_true",
        help="drop desktop-only stdlib packages (pydoc, unittest, venv, ...): ~1.7 MB",
    )
    build.add_argument(
        "--no-ssl",
        action="store_true",
        help="omit OpenSSL and the CA bundle: ~4 MB smaller, but no HTTPS",
    )
    build.set_defaults(func=cmd_build)

    run = sub.add_parser("run", help="preview the app on this machine", parents=[common])
    run.add_argument(
        "--gui",
        action="store_true",
        help="open a clickable window instead of printing to the console",
    )
    run.add_argument(
        "--web",
        action="store_true",
        help="serve a clickable preview in the browser (works over SSH)",
    )
    run.add_argument("--port", type=int, default=8765, help="port for --web (default: 8765)")
    run.add_argument("--host", default="127.0.0.1", help="interface for --web")
    run.set_defaults(func=cmd_run)

    watch = sub.add_parser(
        "watch", help="re-render automatically when a source file changes", parents=[common]
    )
    watch.add_argument("--png", metavar="PATH", help="write a PNG on every reload")
    watch.add_argument("--ids", action="store_true", help="annotate widgets with their id")
    watch.add_argument(
        "--interval",
        type=float,
        default=0.2,
        metavar="SECONDS",
        help="how often to poll for changes (default: 0.2)",
    )
    watch.set_defaults(func=cmd_watch)

    preview = sub.add_parser(
        "preview", help="draw the first screen as a desktop picture", parents=[common]
    )
    preview.add_argument("--png", metavar="PATH", help="write a PNG instead of text")
    preview.add_argument("--ids", action="store_true", help="annotate widgets with their id")
    preview.set_defaults(func=cmd_preview)

    info = sub.add_parser("info", help="show the resolved configuration", parents=[common])
    info.add_argument("--json", action="store_true", help="machine-readable output")
    info.set_defaults(func=cmd_info)

    clean = sub.add_parser("clean", help="remove build artifacts", parents=[common])
    clean.set_defaults(func=cmd_clean)

    setup = sub.add_parser(
        "setup-sdk", help="download the Android SDK/NDK for native builds", parents=[common]
    )
    setup.add_argument("--path", help="install directory (default: ~/.andro)")
    setup.add_argument(
        "--with-ndk",
        action="store_true",
        help="also download the NDK (~2 GB), only needed to rebuild the native bridge",
    )
    setup.set_defaults(func=cmd_setup_sdk)

    doctor = sub.add_parser("doctor", help="check the environment", parents=[common])
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    # restore the defaults suppressed above
    args.verbose = getattr(args, "verbose", False)
    args.config = getattr(args, "config", None)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    configure("debug" if args.verbose else "warning")

    try:
        return int(args.func(args))
    except PyMobileError as exc:
        _out.error(str(exc))
        if exc.hint:
            _out.hint(exc.hint)
        if args.verbose:
            raise
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive
        _out.warn("interrupted")
        return 130
    except Exception as exc:
        _out.error(f"unexpected error: {exc}")
        if args.verbose:
            raise
        _out.hint("re-run with --verbose to see the full traceback")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
