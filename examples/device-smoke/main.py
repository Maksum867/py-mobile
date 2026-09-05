"""Device smoke test: prints a boot marker CI greps for in logcat."""

from __future__ import annotations

from pymobile import Align, App, Button, Color, Column, EdgeInsets, Label, Screen, Style, Widget

BOOT_MARKER = "PYMOBILE_DEVICE_SMOKE_BOOT"


class SmokeScreen(Screen):
    """One screen that proves the interpreter, the bridge and the renderer work."""

    title = "Device smoke"

    def __init__(self) -> None:
        super().__init__()
        self.taps = 0

    def build(self) -> Widget:
        self.status = Label(
            "waiting for a tap",
            style=Style(font_size=16, color=Color.TEXT_MUTED),
        )
        return Column(
            Label(
                "PyMobile device smoke",
                style=Style(font_size=22, bold=True, color=Color.PRIMARY),
            ),
            Label(
                f"platform: {self.app.platform} / bridge: {self.app.bridge.name}",
                style=Style(font_size=13, color=Color.TEXT_MUTED),
            ),
            self.status,
            Button("Tap me", on_press=self.on_tap),
            spacing=12,
            align=Align.CENTER,
            style=Style(padding=EdgeInsets.all(24)),
        )

    def on_show(self) -> None:
        # The marker goes to stdout, which the runtime forwards to logcat under
        # the pymobile.stdout tag. CI greps for it to prove the app really ran
        # on the device rather than merely installing.
        print(BOOT_MARKER)

    def on_tap(self) -> None:
        self.taps += 1
        self.status.text = f"taps: {self.taps}"
        print(f"{BOOT_MARKER}_TAP {self.taps}")


def main() -> None:
    # Printed before the UI exists: if the run fails, this line separates
    # "the interpreter never started" from "the screen never rendered".
    print("PYMOBILE_DEVICE_SMOKE_PY_START")
    app = App(
        "PyMobile Device Smoke",
        package="org.pymobile.devicesmoke",
        version="0.1.0",
    )
    app.run(SmokeScreen())


if __name__ == "__main__":
    main()
