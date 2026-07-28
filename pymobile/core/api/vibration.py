"""Device vibration.

Wraps the bridge with argument validation and a couple of named presets, so
apps do not repeat magic millisecond arrays.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..bridge import Bridge, get_bridge

__all__ = ["Vibration", "DEFAULT_AMPLITUDE", "MAX_AMPLITUDE"]

DEFAULT_AMPLITUDE = -1
MAX_AMPLITUDE = 255

# name -> alternating [wait, vibrate, wait, vibrate, ...] milliseconds
# Pulses under ~50 ms are not felt on most hardware, so the shortest presets
# start there rather than at the textbook 20/40 ms.
PRESETS: dict[str, tuple[int, ...]] = {
    "tick": (0, 50),
    "click": (0, 70),
    "double": (0, 60, 90, 60),
    "success": (0, 50, 60, 50, 60, 90),
    "error": (0, 120, 80, 120),
    "heartbeat": (0, 60, 120, 60, 400, 60, 120, 60),
}


class Vibration:
    """Control the device vibrator."""

    __slots__ = ("_bridge",)

    def __init__(self, bridge: Bridge | None = None) -> None:
        self._bridge = bridge or get_bridge()

    def vibrate(self, milliseconds: int = 100, *, amplitude: int = DEFAULT_AMPLITUDE) -> None:
        """Vibrate once. ``amplitude`` is 1..255, or -1 for the device default."""
        if milliseconds <= 0:
            raise ValueError("milliseconds must be positive")
        if amplitude != DEFAULT_AMPLITUDE and not 1 <= amplitude <= MAX_AMPLITUDE:
            raise ValueError(f"amplitude must be -1 or within 1..{MAX_AMPLITUDE}")
        self._bridge.vibrate(int(milliseconds), int(amplitude))

    def pattern(self, pattern: Sequence[int], *, repeat: int = -1) -> None:
        """Play an alternating off/on pattern. ``repeat`` is an index or -1 for once."""
        values = [int(value) for value in pattern]
        if not values:
            raise ValueError("pattern must not be empty")
        if any(value < 0 for value in values):
            raise ValueError("pattern values must not be negative")
        if repeat < -1 or repeat >= len(values):
            raise ValueError("repeat must be -1 or a valid index into the pattern")
        self._bridge.vibrate_pattern(values, repeat)

    def preset(self, name: str) -> None:
        """Play one of the built-in patterns from :data:`PRESETS`."""
        try:
            values = PRESETS[name]
        except KeyError:
            known = ", ".join(sorted(PRESETS))
            raise ValueError(f"unknown preset {name!r}; available: {known}") from None
        self.pattern(values)

    def cancel(self) -> None:
        """Stop any ongoing vibration."""
        self._bridge.cancel_vibration()
