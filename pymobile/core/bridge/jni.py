"""On-device implementation backed by ``pyjnius``.

Imports of ``jnius`` are deliberately lazy and wrapped: the module must remain
importable on a developer machine where no JVM exists. Java classes are
resolved once and cached, because ``autoclass`` lookups are not free.
"""

from __future__ import annotations

import time
from functools import cached_property
from typing import Any, ClassVar

from ...errors import BridgeError
from ...logging import get_logger
from .base import Bridge, NotificationSpec

__all__ = ["JNIBridge"]

_log = get_logger("bridge.jni")

# android.app.NotificationManager.IMPORTANCE_DEFAULT
IMPORTANCE_DEFAULT = 3
# android.os.VibrationEffect.DEFAULT_AMPLITUDE
DEFAULT_AMPLITUDE = -1

#: How long to wait for the user to answer a permission dialog before giving
#: up. Matches the timeout used by the native bridge (MainActivity).
_PERMISSION_TIMEOUT = 120.0
#: Polling interval while waiting for the permission dialog to close.
_PERMISSION_POLL = 0.2


class JNIBridge(Bridge):
    """Talks to the Android runtime through JNI."""

    name = "jni"

    def __init__(self) -> None:
        self._classes: dict[str, Any] = {}

    # -- plumbing ----------------------------------------------------------
    def _autoclass(self, path: str) -> Any:
        """Resolve and cache a Java class."""
        cached = self._classes.get(path)
        if cached is not None:
            return cached
        try:
            from jnius import autoclass  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - device-only path
            raise BridgeError(
                "pyjnius is not available in this runtime",
                hint="Install the 'android' extra, or run on a real device/emulator.",
            ) from exc
        klass = autoclass(path)
        self._classes[path] = klass
        return klass

    @cached_property
    def _activity(self) -> Any:  # pragma: no cover - device-only path
        """The current Android Activity."""
        try:
            return self._autoclass("org.kivy.android.PythonActivity").mActivity
        except Exception:
            return self._autoclass("org.kivy.android.PythonService").mService

    @cached_property
    def _context(self) -> Any:  # pragma: no cover - device-only path
        return self._activity.getApplicationContext()

    def is_available(self) -> bool:
        try:
            import jnius  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            return False
        return True

    # -- notifications -----------------------------------------------------
    def ensure_channel(  # pragma: no cover - device-only path
        self, channel_id: str, channel_name: str, importance: int = IMPORTANCE_DEFAULT
    ) -> None:
        build_version = self._autoclass("android.os.Build$VERSION")
        if build_version.SDK_INT < 26:  # channels landed in Oreo
            return
        channel_cls = self._autoclass("android.app.NotificationChannel")
        manager = self._context.getSystemService(
            self._autoclass("android.content.Context").NOTIFICATION_SERVICE
        )
        channel = channel_cls(channel_id, channel_name, importance)
        manager.createNotificationChannel(channel)

    def notify(self, spec: NotificationSpec) -> None:  # pragma: no cover - device-only path
        self.ensure_channel(spec.channel_id, spec.channel_name, IMPORTANCE_DEFAULT)
        builder_cls = self._autoclass("android.app.Notification$Builder")
        build_version = self._autoclass("android.os.Build$VERSION")
        context = self._context
        builder = (
            builder_cls(context, spec.channel_id)
            if build_version.SDK_INT >= 26
            else builder_cls(context)
        )
        builder.setContentTitle(spec.title)
        builder.setContentText(spec.body)
        builder.setOngoing(spec.ongoing)
        builder.setAutoCancel(not spec.ongoing)
        builder.setSmallIcon(self._icon_id(spec.small_icon))
        manager = context.getSystemService(
            self._autoclass("android.content.Context").NOTIFICATION_SERVICE
        )
        manager.notify(spec.notification_id, builder.build())

    def _icon_id(self, name: str | None) -> int:  # pragma: no cover - device-only path
        """Resolve a drawable name to a resource id, falling back to the app icon."""
        resources = self._context.getResources()
        package = self._context.getPackageName()
        for candidate, kind in ((name, "drawable"), ("icon", "mipmap"), ("icon", "drawable")):
            if not candidate:
                continue
            found = resources.getIdentifier(candidate, kind, package)
            if found:
                return int(found)
        return int(self._autoclass("android.R$drawable").ic_dialog_info)

    def cancel_notification(self, notification_id: int) -> None:  # pragma: no cover
        manager = self._context.getSystemService(
            self._autoclass("android.content.Context").NOTIFICATION_SERVICE
        )
        manager.cancel(notification_id)

    # -- vibration ---------------------------------------------------------
    @cached_property
    def _vibrator(self) -> Any:  # pragma: no cover - device-only path
        context_cls = self._autoclass("android.content.Context")
        build_version = self._autoclass("android.os.Build$VERSION")
        if build_version.SDK_INT >= 31:
            manager = self._context.getSystemService(context_cls.VIBRATOR_MANAGER_SERVICE)
            return manager.getDefaultVibrator()
        return self._context.getSystemService(context_cls.VIBRATOR_SERVICE)

    def vibrate(  # pragma: no cover - device-only path
        self, milliseconds: int, amplitude: int = DEFAULT_AMPLITUDE
    ) -> None:
        build_version = self._autoclass("android.os.Build$VERSION")
        if build_version.SDK_INT >= 26:
            effect_cls = self._autoclass("android.os.VibrationEffect")
            self._vibrator.vibrate(effect_cls.createOneShot(milliseconds, amplitude))
        else:
            self._vibrator.vibrate(milliseconds)

    def vibrate_pattern(  # pragma: no cover - device-only path
        self, pattern: list[int], repeat: int = -1
    ) -> None:
        build_version = self._autoclass("android.os.Build$VERSION")
        if build_version.SDK_INT >= 26:
            effect_cls = self._autoclass("android.os.VibrationEffect")
            self._vibrator.vibrate(effect_cls.createWaveform(pattern, repeat))
        else:
            self._vibrator.vibrate(pattern, repeat)

    def cancel_vibration(self) -> None:  # pragma: no cover - device-only path
        self._vibrator.cancel()

    # -- permissions -------------------------------------------------------
    def has_permission(self, permission: str) -> bool:  # pragma: no cover - device-only path
        package_manager = self._autoclass("android.content.pm.PackageManager")
        result = self._context.checkSelfPermission(permission)
        return int(result) == int(package_manager.PERMISSION_GRANTED)

    def request_permissions(  # pragma: no cover - device-only path
        self, permissions: list[str]
    ) -> dict[str, bool]:
        """Show the system dialog and block until the user answers.

        ``requestPermissions`` is asynchronous: the outcome is delivered to the
        activity's ``onRequestPermissionsResult`` once the dialog closes.
        Re-reading the permission right after the call would therefore always
        report "denied" (the race fixed for the native bridge already). The
        dialog is modal and commits every result at once, so we wait until any
        pending permission changes state — or ``_PERMISSION_TIMEOUT`` seconds
        pass, matching the native bridge — and then read the final answers.
        """
        build_version = self._autoclass("android.os.Build$VERSION")
        if build_version.SDK_INT < 23:
            return {name: True for name in permissions}

        pending = [name for name in permissions if not self.has_permission(name)]
        results = {name: True for name in permissions if name not in pending}
        if not pending:
            return results

        # A grant flips has_permission(); a denial cannot be read from it, but
        # Android then reports shouldShowRequestPermissionRationale()==True.
        # Either signal means the modal dialog was answered, so we stop
        # polling and read the final answers.
        request_permissions = getattr(self._activity, "requestPermissions", None)
        if request_permissions is None:
            # A Service-backed context (the _activity fallback) cannot show a
            # dialog; report the current state instead of crashing.
            return {name: self.has_permission(name) for name in permissions}

        granted_before = {name: self.has_permission(name) for name in pending}
        rationale_before = {name: self._show_rationale(name) for name in pending}
        request_permissions(pending, 0)
        deadline = time.monotonic() + _PERMISSION_TIMEOUT
        while time.monotonic() < deadline:
            answered = any(
                self.has_permission(name) != granted_before[name]
                or self._show_rationale(name) != rationale_before[name]
                for name in pending
            )
            if answered:
                break
            time.sleep(_PERMISSION_POLL)

        results.update({name: self.has_permission(name) for name in pending})
        return results

    def _show_rationale(self, permission: str) -> bool:  # pragma: no cover - device-only
        """Whether the user previously denied ``permission`` (API 23+).

        ``shouldShowRequestPermissionRationale`` lives on Activity, so a
        Service-backed context simply reports False and the caller falls back
        to polling on the granted flag alone.
        """
        try:
            return bool(self._activity.shouldShowRequestPermissionRationale(permission))
        except Exception:  # pragma: no cover - missing method / Service context
            return False

    # -- ui ----------------------------------------------------------------
    def toast(self, message: str, long: bool = False) -> None:  # pragma: no cover
        toast_cls = self._autoclass("android.widget.Toast")
        duration = toast_cls.LENGTH_LONG if long else toast_cls.LENGTH_SHORT
        self._run_on_ui(lambda: toast_cls.makeText(self._context, message, duration).show())

    def render(self, tree: dict[str, Any]) -> None:  # pragma: no cover - device-only path
        """Send the widget tree to the native renderer.

        This bridge is only chosen for apps embedded in a python-for-android
        bootstrap, which does not carry the PyMobile Java renderer, so there
        is nothing to draw into. Failing loudly beats shipping an app that
        boots to a blank screen with only a debug-log line to hint why.
        """
        raise BridgeError(
            "The JNI (pyjnius) bridge cannot render the UI",
            hint="Build the APK with `pymobile build --native` so the compiled "
            "renderer is included in the package.",
        )

    def _run_on_ui(self, action: Any) -> None:  # pragma: no cover - device-only path
        from jnius import PythonJavaClass, java_method  # type: ignore[import-not-found]

        class _Runnable(PythonJavaClass):  # type: ignore[misc]
            # pyjnius reads these class attributes; ClassVar keeps linters happy.
            __javainterfaces__: ClassVar[list[str]] = ["java/lang/Runnable"]
            __javacontext__: ClassVar[str] = "app"

            @java_method("()V")  # type: ignore[untyped-decorator]
            def run(self) -> None:
                action()

        self._activity.runOnUiThread(_Runnable())
