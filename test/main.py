"""Test — built with PyMobile."""

from __future__ import annotations

from pymobile import App, Button, Column, EdgeInsets, Label, Screen, Style, Widget
from pymobile.core.ui import Align, Color


class HomeScreen(Screen):
    """The first screen of the application."""

    title = "Test"

    def __init__(self) -> None:
        super().__init__()
        self.taps = 0
        self.counter = Label("Taps: 0", style=Style(font_size=18, color=Color.TEXT))

    def build(self) -> Widget:
        return Column(
            Label(
                "Test",
                style=Style(font_size=26, bold=True, color=Color.PRIMARY),
            ),
            Label(
                "Edit main.py and rebuild with `pymobile build`.",
                style=Style(color=Color.TEXT_MUTED),
            ),
            self.counter,
            Button("Tap me", on_press=self.on_tap),
            Button("Notify me", on_press=self.on_notify),
            spacing=12,
            align=Align.CENTER,
            style=Style(padding=EdgeInsets.all(24), background=Color.BACKGROUND),
        )

    def on_tap(self) -> None:
        """Increment the counter and give haptic feedback."""
        self.taps += 1
        self.counter.set_text(f"Taps: {self.taps}")
        if self.app is not None:
            self.app.vibrate(30)
            self.app.render()

    def on_notify(self) -> None:
        """Post a local notification."""
        if self.app is not None:
            self.app.notify("Test", f"You tapped {self.taps} time(s).")


def main() -> None:
    """Application entry point."""
    app = App("Test")
    app.run(HomeScreen())


if __name__ == "__main__":
    main()
