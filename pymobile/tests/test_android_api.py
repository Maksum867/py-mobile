"""Tests for notifications, vibration and permissions."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from pymobile.core.api.notifications import IMPORTANCE_HIGH, Notifications
from pymobile.core.api.permissions import Permission, PermissionManager, normalize
from pymobile.core.api.vibration import PRESETS, Vibration
from pymobile.core.bridge import StubBridge
from pymobile.errors import BridgeError, PermissionError_


class TestNotifications:
    def test_notify_returns_incrementing_ids(self, bridge: StubBridge) -> None:
        notifications = Notifications(bridge)
        assert notifications.notify("A") == 1
        assert notifications.notify("B") == 2

    def test_explicit_id_is_used(self, bridge: StubBridge) -> None:
        assert Notifications(bridge).notify("A", notification_id=99) == 99

    def test_channel_created_once(self, bridge: StubBridge) -> None:
        notifications = Notifications(bridge)
        notifications.notify("A")
        notifications.notify("B")
        assert len(bridge.calls_named("ensure_channel")) == 1

    def test_channel_importance_forwarded(self, bridge: StubBridge) -> None:
        Notifications(bridge, importance=IMPORTANCE_HIGH).notify("A")
        assert bridge.calls_named("ensure_channel")[0].kwargs["importance"] == IMPORTANCE_HIGH

    def test_empty_title_rejected(self, bridge: StubBridge) -> None:
        with pytest.raises(ValueError, match="title"):
            Notifications(bridge).notify("")

    def test_cancel_removes_notification(self, bridge: StubBridge) -> None:
        notifications = Notifications(bridge)
        identifier = notifications.notify("A")
        notifications.cancel(identifier)
        assert identifier not in bridge.notifications

    def test_spec_carries_body_and_flags(self, bridge: StubBridge) -> None:
        notifications = Notifications(bridge)
        identifier = notifications.notify("T", "B", ongoing=True, icon="star")
        spec = bridge.notifications[identifier]
        assert (spec.body, spec.ongoing, spec.small_icon) == ("B", True, "star")


class TestVibration:
    def test_vibrate_forwards_duration(self, bridge: StubBridge) -> None:
        Vibration(bridge).vibrate(250)
        assert bridge.calls_named("vibrate")[0].kwargs["milliseconds"] == 250

    def test_non_positive_duration_rejected(self, bridge: StubBridge) -> None:
        with pytest.raises(ValueError, match="positive"):
            Vibration(bridge).vibrate(0)

    def test_amplitude_validated(self, bridge: StubBridge) -> None:
        with pytest.raises(ValueError, match="amplitude"):
            Vibration(bridge).vibrate(100, amplitude=999)

    def test_default_amplitude_allowed(self, bridge: StubBridge) -> None:
        Vibration(bridge).vibrate(100, amplitude=-1)
        assert bridge.calls_named("vibrate")

    def test_pattern_forwarded(self, bridge: StubBridge) -> None:
        Vibration(bridge).pattern([0, 100, 50, 100])
        assert bridge.calls_named("vibrate_pattern")[0].kwargs["pattern"] == [0, 100, 50, 100]

    def test_empty_pattern_rejected(self, bridge: StubBridge) -> None:
        with pytest.raises(ValueError, match="empty"):
            Vibration(bridge).pattern([])

    def test_negative_pattern_rejected(self, bridge: StubBridge) -> None:
        with pytest.raises(ValueError, match="negative"):
            Vibration(bridge).pattern([0, -5])

    def test_repeat_bounds_checked(self, bridge: StubBridge) -> None:
        with pytest.raises(ValueError, match="repeat"):
            Vibration(bridge).pattern([0, 10], repeat=5)

    @pytest.mark.parametrize("name", sorted(PRESETS))
    def test_every_preset_plays(self, bridge: StubBridge, name: str) -> None:
        Vibration(bridge).preset(name)
        assert bridge.calls_named("vibrate_pattern")

    def test_unknown_preset_lists_options(self, bridge: StubBridge) -> None:
        with pytest.raises(ValueError, match="available:"):
            Vibration(bridge).preset("nope")

    def test_cancel(self, bridge: StubBridge) -> None:
        Vibration(bridge).cancel()
        assert bridge.calls_named("cancel_vibration")


class TestPermissions:
    def test_normalize_variants(self) -> None:
        assert normalize("CAMERA") == "android.permission.CAMERA"
        assert normalize("android.permission.CAMERA") == "android.permission.CAMERA"
        assert normalize(Permission.CAMERA) == "android.permission.CAMERA"

    def test_normalize_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            normalize("  ")

    def test_short_and_runtime_flags(self) -> None:
        assert Permission.CAMERA.short == "CAMERA"
        assert Permission.CAMERA.runtime
        assert not Permission.INTERNET.runtime

    def test_request_grants(self, bridge: StubBridge) -> None:
        manager = PermissionManager(bridge)
        assert manager.request(Permission.CAMERA) == {"android.permission.CAMERA": True}
        assert manager.has(Permission.CAMERA)

    def test_already_granted_is_not_requested_again(self, bridge: StubBridge) -> None:
        manager = PermissionManager(bridge)
        manager.request(Permission.CAMERA)
        manager.request(Permission.CAMERA)
        assert len(bridge.calls_named("request_permissions")) == 1

    def test_empty_request(self, bridge: StubBridge) -> None:
        assert PermissionManager(bridge).request() == {}

    def test_missing_lists_ungranted(self, bridge: StubBridge) -> None:
        manager = PermissionManager(bridge)
        missing = manager.missing([Permission.CAMERA, Permission.VIBRATE])
        assert len(missing) == 2

    def test_require_raises_when_denied(self) -> None:
        denying = StubBridge(grant_permissions=False, verbose=False)
        with pytest.raises(PermissionError_) as info:
            PermissionManager(denying).require(Permission.CAMERA)
        assert info.value.permission == "android.permission.CAMERA"

    def test_manifest_entries_sorted_unique(self) -> None:
        entries = PermissionManager.manifest_entries(
            [Permission.VIBRATE, "CAMERA", "android.permission.VIBRATE"]
        )
        assert entries == ["android.permission.CAMERA", "android.permission.VIBRATE"]


class _JniFakeVersion:
    SDK_INT = 30


class _JniFakeActivity:
    """Records the dialog call; the real answer is faked by the bridge state."""

    def __init__(self) -> None:
        self.called = False

    def requestPermissions(self, permissions: list[str], request_code: int) -> None:
        self.called = True

    def shouldShowRequestPermissionRationale(self, permission: str) -> bool:
        return False


class TestJniBridgePermissions:
    """The pyjnius fallback must wait for the dialog, not report an instant denial."""

    @staticmethod
    def _bridge(monkeypatch: pytest.MonkeyPatch, state: dict[str, bool]) -> Any:
        import pymobile.core.bridge.jni as jni_module
        from pymobile.core.bridge.jni import JNIBridge

        monkeypatch.setattr(jni_module, "_PERMISSION_POLL", 0.01)

        class Fake(JNIBridge):
            def __init__(self) -> None:
                super().__init__()
                self.state = dict(state)
                self.rationale: dict[str, bool] = {}
                self.activity = _JniFakeActivity()

            def _autoclass(self, path: str) -> Any:
                if path == "android.os.Build$VERSION":
                    return _JniFakeVersion
                if path == "org.kivy.android.PythonActivity":
                    return type("PythonActivity", (), {"mActivity": self.activity})
                raise AssertionError(path)

            def has_permission(self, permission: str) -> bool:
                return self.state.get(permission, False)

            def _show_rationale(self, permission: str) -> bool:
                return self.rationale.get(permission, False)

        return Fake()

    def test_granted_permissions_return_without_dialog(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bridge = self._bridge(monkeypatch, state={"android.permission.CAMERA": True})
        assert bridge.request_permissions(["android.permission.CAMERA"]) == {
            "android.permission.CAMERA": True
        }
        assert not bridge.activity.called

    def test_waits_for_grant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bridge = self._bridge(monkeypatch, state={"android.permission.CAMERA": False})

        def grant() -> None:
            time.sleep(0.2)
            bridge.state["android.permission.CAMERA"] = True

        threading.Thread(target=grant, daemon=True).start()
        started = time.monotonic()
        assert bridge.request_permissions(["android.permission.CAMERA"]) == {
            "android.permission.CAMERA": True
        }
        assert time.monotonic() - started < 5

    def test_waits_for_denial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bridge = self._bridge(monkeypatch, state={"android.permission.CAMERA": False})

        def deny() -> None:
            time.sleep(0.2)
            bridge.rationale["android.permission.CAMERA"] = True

        threading.Thread(target=deny, daemon=True).start()
        started = time.monotonic()
        assert bridge.request_permissions(["android.permission.CAMERA"]) == {
            "android.permission.CAMERA": False
        }
        assert time.monotonic() - started < 5

    def test_times_out_when_unanswered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pymobile.core.bridge.jni as jni_module

        monkeypatch.setattr(jni_module, "_PERMISSION_TIMEOUT", 0.3)
        bridge = self._bridge(monkeypatch, state={"android.permission.CAMERA": False})
        started = time.monotonic()
        assert bridge.request_permissions(["android.permission.CAMERA"]) == {
            "android.permission.CAMERA": False
        }
        assert time.monotonic() - started < 5


class TestJniBridgeRender:
    """The pyjnius fallback cannot draw the UI and must say so loudly."""

    def test_render_fails_loudly(self) -> None:
        from pymobile.core.bridge.jni import JNIBridge

        with pytest.raises(BridgeError, match="cannot render"):
            JNIBridge().render({"type": "Label"})
