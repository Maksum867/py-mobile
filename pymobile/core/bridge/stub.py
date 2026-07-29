"""Desktop implementation of :class:`~pymobile.core.bridge.base.Bridge`.

Instead of failing away from a device, the stub *records* every call and logs
it. That gives two things for free: a usable desktop preview mode, and a test
double the whole suite is built on.
"""

from __future__ import annotations

from typing import Any

from ...logging import get_logger
from .base import Bridge, BridgeCall, NotificationSpec

__all__ = ["StubBridge"]

_log = get_logger("bridge.stub")


class StubBridge(Bridge):
    """Records platform calls in memory; grants permissions by policy."""

    name = "stub"

    def __init__(
        self,
        *,
        grant_permissions: bool = True,
        verbose: bool = True,
        language: str = "",
    ) -> None:
        self.calls: list[BridgeCall] = []
        self.notifications: dict[int, NotificationSpec] = {}
        self.granted: set[str] = set()
        self.grant_permissions = grant_permissions
        self.verbose = verbose
        self.last_tree: dict[str, Any] | None = None
        #: Language reported by :meth:`device_language`; empty means "ask the
        #: environment", which is what a desktop preview should do.
        self.language = language

    # -- helpers -----------------------------------------------------------
    def _record(self, name: str, **kwargs: Any) -> None:
        self.calls.append(BridgeCall(name, kwargs))
        if self.verbose:
            _log.info("%s(%s)", name, ", ".join(f"{k}={v!r}" for k, v in kwargs.items()))

    def calls_named(self, name: str) -> list[BridgeCall]:
        """Every recorded call with the given name."""
        return [call for call in self.calls if call.name == name]

    def reset(self) -> None:
        """Forget recorded state (handy between tests)."""
        self.calls.clear()
        self.notifications.clear()
        self.granted.clear()
        self.last_tree = None

    def is_available(self) -> bool:
        return True

    # -- notifications -----------------------------------------------------
    def ensure_channel(self, channel_id: str, channel_name: str, importance: int) -> None:
        self._record(
            "ensure_channel",
            channel_id=channel_id,
            channel_name=channel_name,
            importance=importance,
        )

    def notify(self, spec: NotificationSpec) -> None:
        self.notifications[spec.notification_id] = spec
        self._record("notify", id=spec.notification_id, title=spec.title, body=spec.body)

    def cancel_notification(self, notification_id: int) -> None:
        self.notifications.pop(notification_id, None)
        self._record("cancel_notification", id=notification_id)

    # -- vibration ---------------------------------------------------------
    def vibrate(self, milliseconds: int, amplitude: int) -> None:
        self._record("vibrate", milliseconds=milliseconds, amplitude=amplitude)

    def vibrate_pattern(self, pattern: list[int], repeat: int) -> None:
        self._record("vibrate_pattern", pattern=list(pattern), repeat=repeat)

    def cancel_vibration(self) -> None:
        self._record("cancel_vibration")

    # -- permissions -------------------------------------------------------
    def has_permission(self, permission: str) -> bool:
        return permission in self.granted

    def request_permissions(self, permissions: list[str]) -> dict[str, bool]:
        self._record("request_permissions", permissions=list(permissions))
        result: dict[str, bool] = {}
        for permission in permissions:
            granted = self.grant_permissions
            if granted:
                self.granted.add(permission)
            result[permission] = granted
        return result

    # -- ui ----------------------------------------------------------------
    def toast(self, message: str, long: bool) -> None:
        self._record("toast", message=message, long=long)

    def render(self, tree: dict[str, Any]) -> None:
        self.last_tree = tree
        self._record("render", root=tree.get("type"), children=len(tree.get("children", ())))

    # -- locale ------------------------------------------------------------
    def device_language(self) -> str:
        return self.language
