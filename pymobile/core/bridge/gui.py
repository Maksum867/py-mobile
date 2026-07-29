"""Bridge that draws into the interactive desktop preview.

It is a :class:`~pymobile.core.bridge.stub.StubBridge` — every call is still
recorded, so tests and the ASCII preview keep working — that additionally
forwards rendered trees and toasts to a Tk window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...logging import get_logger
from .stub import StubBridge

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..ui.gui import GuiPreview
    from ..ui.web import WebPreview

__all__ = ["GuiBridge", "WebBridge"]

_log = get_logger("bridge.gui")


class GuiBridge(StubBridge):
    """Renders widget trees into a Tkinter window."""

    name = "gui"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._preview: GuiPreview | None = None

    def attach(self, preview: GuiPreview) -> None:
        """Point the bridge at a window and draw whatever is already there."""
        self._preview = preview
        if self.last_tree is not None:
            preview.render(self.last_tree)

    def render(self, tree: dict[str, Any]) -> None:
        super().render(tree)
        if self._preview is not None:
            self._preview.render(tree)

    def toast(self, message: str, long: bool = False) -> None:
        super().toast(message, long)
        if self._preview is not None:
            self._preview.toast(message)

    def vibrate(self, milliseconds: int, amplitude: int = -1) -> None:
        super().vibrate(milliseconds, amplitude)
        if self._preview is not None:
            self._preview.toast(f"vibrate {milliseconds} ms")


class WebBridge(StubBridge):
    """Renders widget trees into a browser page."""

    name = "web"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._preview: WebPreview | None = None

    def attach(self, preview: WebPreview) -> None:
        """Point the bridge at a preview and publish the current tree."""
        self._preview = preview
        if self.last_tree is not None:
            preview.update(self.last_tree)

    def render(self, tree: dict[str, Any]) -> None:
        super().render(tree)
        if self._preview is not None:
            self._preview.update(tree)

    def toast(self, message: str, long: bool = False) -> None:
        super().toast(message, long)
        if self._preview is not None:
            self._preview.toast(message)

    def vibrate(self, milliseconds: int, amplitude: int = -1) -> None:
        super().vibrate(milliseconds, amplitude)
        if self._preview is not None:
            self._preview.toast(f"vibrate {milliseconds} ms")
