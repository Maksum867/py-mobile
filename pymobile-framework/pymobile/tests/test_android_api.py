"""Tests for notifications, vibration and permissions."""

from __future__ import annotations

import pytest

from pymobile.core.api.notifications import IMPORTANCE_HIGH, Notifications
from pymobile.core.api.permissions import Permission, PermissionManager, normalize
from pymobile.core.api.vibration import PRESETS, Vibration
from pymobile.core.bridge import StubBridge
from pymobile.errors import PermissionError_


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
