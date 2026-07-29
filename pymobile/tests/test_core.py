"""Tests for the app object, event bus, platform detection and bridges."""

from __future__ import annotations

import time

import pytest

from pymobile import App, Column, Label, Screen, Widget
from pymobile.core.bridge import StubBridge, get_bridge, reset_bridge, set_bridge
from pymobile.core.events import Event, EventBus
from pymobile.core.platform import Platform, current_platform, is_android, is_desktop
from pymobile.core.scheduler import Scheduler
from pymobile.errors import PyMobileError


class _Home(Screen):
    title = "Home"

    def build(self) -> Widget:
        return Column(Label("home"))


class TestEventBus:
    def test_emit_delivers_payload(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.on("ping", received.append)
        bus.emit("ping", source="test", value=42)
        assert received[0].get("value") == 42
        assert received[0].source == "test"

    def test_handlers_run_in_order(self) -> None:
        bus = EventBus()
        order: list[int] = []
        bus.on("x", lambda _e: order.append(1))
        bus.on("x", lambda _e: order.append(2))
        bus.emit("x")
        assert order == [1, 2]

    def test_subscription_cancel(self) -> None:
        bus = EventBus()
        seen: list[Event] = []
        subscription = bus.on("x", seen.append)
        subscription.cancel()
        subscription.cancel()  # idempotent
        bus.emit("x")
        assert seen == []
        assert "x" not in bus

    def test_failing_handler_does_not_break_dispatch(self) -> None:
        bus = EventBus()
        seen: list[Event] = []

        def boom(_event: Event) -> None:
            raise RuntimeError("bad handler")

        bus.on("x", boom)
        bus.on("x", seen.append)
        bus.emit("x")
        assert len(seen) == 1

    def test_off_unknown_handler_is_safe(self) -> None:
        bus = EventBus()
        bus.off("nothing", lambda _e: None)

    def test_len_and_clear(self) -> None:
        bus = EventBus()
        bus.on("a", lambda _e: None)
        bus.on("b", lambda _e: None)
        assert len(bus) == 2
        bus.clear()
        assert len(bus) == 0

    def test_event_default(self) -> None:
        assert Event("x").get("missing", "fallback") == "fallback"


class TestPlatform:
    def test_desktop_by_default(self) -> None:
        current_platform.cache_clear()
        assert is_desktop()
        assert not is_android()

    def test_android_detected_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        current_platform.cache_clear()
        monkeypatch.setenv("ANDROID_ARGUMENT", "/data/app")
        assert current_platform() is Platform.ANDROID
        current_platform.cache_clear()

    def test_force_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        current_platform.cache_clear()
        monkeypatch.setenv("PYMOBILE_FORCE_PLATFORM", "android")
        assert is_android()
        current_platform.cache_clear()


class TestBridgeSelection:
    def test_default_bridge_on_desktop(self) -> None:
        reset_bridge()
        current_platform.cache_clear()
        assert isinstance(get_bridge(), StubBridge)

    def test_bridge_is_cached(self) -> None:
        reset_bridge()
        assert get_bridge() is get_bridge()

    def test_set_and_reset(self) -> None:
        custom = StubBridge(verbose=False)
        set_bridge(custom)
        assert get_bridge() is custom
        reset_bridge()
        assert get_bridge() is not custom

    def test_stub_records_calls(self) -> None:
        stub = StubBridge(verbose=False)
        stub.toast("hello", False)
        assert stub.calls_named("toast")[0].kwargs["message"] == "hello"
        stub.reset()
        assert stub.calls == []


class TestApp:
    def test_run_renders_first_screen(self, bridge: StubBridge) -> None:
        app = App("Demo", bridge=bridge)
        app.run(_Home())
        assert app.running
        assert app.screen is not None
        assert bridge.calls_named("render")

    def test_platform_reported(self, bridge: StubBridge) -> None:
        assert App("Demo", bridge=bridge).platform in ("desktop", "android")

    def test_navigation_renders(self, bridge: StubBridge) -> None:
        app = App("Demo", bridge=bridge)
        app.run(_Home())
        before = len(bridge.calls_named("render"))
        app.push(_Home())
        assert len(bridge.calls_named("render")) == before + 1
        app.pop()

    def test_navigation_before_run_fails(self, bridge: StubBridge) -> None:
        app = App("Demo", bridge=bridge)
        with pytest.raises(PyMobileError, match=r"before App\.run"):
            app.push(_Home())

    def test_render_without_screen_returns_none(self, bridge: StubBridge) -> None:
        assert App("Demo", bridge=bridge).render() is None

    def test_events_emitted(self, bridge: StubBridge) -> None:
        app = App("Demo", bridge=bridge)
        seen: list[str] = []
        app.on("app:start", lambda e: seen.append(e.name))
        app.on("screen:change", lambda e: seen.append(e.name))
        app.run(_Home())
        assert "app:start" in seen
        assert "screen:change" in seen

    def test_stop_is_idempotent(self, bridge: StubBridge) -> None:
        app = App("Demo", bridge=bridge)
        app.run(_Home())
        app.stop()
        app.stop()
        assert not app.running

    def test_convenience_helpers(self, bridge: StubBridge) -> None:
        app = App("Demo", bridge=bridge)
        app.run(_Home())
        app.notify("title", "body")
        app.vibrate(50)
        app.toast("hi")
        assert bridge.calls_named("notify")
        assert bridge.calls_named("vibrate")
        assert bridge.calls_named("toast")


class TestScheduler:
    """Timers, including the drift correction added in 0.3.0."""

    def test_timeout_fires_once(self) -> None:
        scheduler = Scheduler()
        calls: list[int] = []
        scheduler.set_timeout(10, lambda: calls.append(1))
        time.sleep(0.08)
        scheduler.cancel_all()
        assert calls == [1]

    def test_interval_repeats(self) -> None:
        scheduler = Scheduler()
        calls: list[int] = []
        handle = scheduler.set_interval(20, lambda: calls.append(1))
        time.sleep(0.15)
        handle.cancel()
        assert len(calls) >= 3

    def test_cancel_stops_further_calls(self) -> None:
        scheduler = Scheduler()
        calls: list[int] = []
        handle = scheduler.set_interval(20, lambda: calls.append(1))
        time.sleep(0.05)
        handle.cancel()
        seen = len(calls)
        time.sleep(0.1)
        assert len(calls) == seen
        assert handle.cancelled

    def test_cancel_is_idempotent(self) -> None:
        handle = Scheduler().set_timeout(1000, lambda: None)
        handle.cancel()
        handle.cancel()

    def test_bad_intervals_rejected(self) -> None:
        scheduler = Scheduler()
        with pytest.raises(ValueError, match="interval_ms"):
            scheduler.set_interval(0, lambda: None)
        with pytest.raises(ValueError, match="delay_ms"):
            scheduler.set_timeout(-1, lambda: None)

    def test_failing_callback_does_not_stop_the_interval(self) -> None:
        scheduler = Scheduler()
        calls: list[int] = []

        def boom() -> None:
            calls.append(1)
            raise RuntimeError("bad tick")

        handle = scheduler.set_interval(20, boom)
        time.sleep(0.12)
        handle.cancel()
        assert len(calls) >= 2

    def test_ticks_do_not_drift(self) -> None:
        """A slow callback must not push the next tick further out.

        Without correction a 30 ms interval whose callback takes 15 ms fires
        every ~45 ms, and an hour later the clock is minutes slow.
        """
        scheduler = Scheduler()
        stamps: list[float] = []
        started = time.monotonic()

        def tick() -> None:
            stamps.append(time.monotonic() - started)
            time.sleep(0.015)

        handle = scheduler.set_interval(30, tick)
        time.sleep(0.5)
        handle.cancel()

        assert len(stamps) >= 8
        # Each tick sits near its slot on the fixed timeline, not at n*45 ms.
        for index, stamp in enumerate(stamps[:8], start=1):
            assert abs(stamp - index * 0.030) < 0.020, stamps

    def test_drift_correction_can_be_disabled(self) -> None:
        scheduler = Scheduler()
        stamps: list[float] = []
        started = time.monotonic()

        def tick() -> None:
            stamps.append(time.monotonic() - started)
            time.sleep(0.015)

        handle = scheduler.set_interval(30, tick, drift_correction=False)
        time.sleep(0.4)
        handle.cancel()
        # Pauses are measured between runs, so the lag accumulates by design.
        assert len(stamps) >= 4
        assert stamps[3] > 4 * 0.030

    def test_app_cancels_timers_on_stop(self, bridge: StubBridge) -> None:
        app = App("Demo", bridge=bridge)
        app.run(_Home())
        calls: list[int] = []
        app.set_interval(20, lambda: calls.append(1))
        app.stop()
        seen = len(calls)
        time.sleep(0.1)
        assert len(calls) == seen
