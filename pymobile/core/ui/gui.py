"""An interactive desktop preview built on Tkinter.

The ASCII preview answers "does the layout look right"; this one answers
"does the app *work*". It renders the serialised widget tree into real Tk
widgets, so buttons can be clicked, switches flipped and text typed — and the
Python callbacks behind them run exactly as they would on a phone, including
navigation between screens.

Like the Android renderer, a new tree is patched into the existing widgets
whenever the structure is unchanged. Rebuilding wholesale would destroy the
focused Entry on every keystroke, which is precisely the bug the device
renderer already learned to avoid.

Tkinter ships with CPython, so this costs no dependency. It is a developer
tool: no attempt is made to look like Material Design, only to be faithful
about structure, state and interaction.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    import tkinter as tk

    from ..app import App

__all__ = ["GuiPreview", "run_gui", "tkinter_available", "skeleton"]

_log = get_logger("ui.gui")

#: Roughly a phone in portrait, in points.
_WINDOW = (400, 760)

_PALETTE = {
    "bg": "#FFFFFF",
    "chrome": "#F1F3F5",
    "text": "#212121",
    "muted": "#757575",
    "line": "#DFE3E8",
}

#: Containers that simply stack their children vertically in the preview.
_VERTICAL = ("Column", "Container", "SafeArea", "Stack", "Expanded", "Flexible")


def tkinter_available() -> bool:
    """Whether Tkinter can be imported (a display is a separate question)."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return True


def skeleton(node: dict[str, Any]) -> tuple[Any, ...]:
    """Structural fingerprint of a tree: type, id and shape, but no values.

    Two trees with the same skeleton can be patched into one another; anything
    else needs a rebuild.
    """
    return (
        node.get("type"),
        node.get("id"),
        node.get("visible", True),
        tuple(skeleton(child) for child in node.get("children", ())),
    )


class GuiPreview:
    """Renders an :class:`~pymobile.core.app.App` into a Tk window.

    The app keeps driving itself: this class only supplies a bridge that
    turns rendered trees into Tk widgets and feeds interactions back in.
    """

    def __init__(self, app: App, *, title: str = "", scale: float = 1.0) -> None:
        import tkinter as tk

        self.app = app
        self._tk = tk
        self.root = tk.Tk()
        self.root.title(title or app.name)
        width, height = (int(value * scale) for value in _WINDOW)
        self.root.geometry(f"{width}x{height}")
        self.root.configure(bg=_PALETTE["chrome"])
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        header = tk.Frame(self.root, bg=_PALETTE["chrome"])
        header.pack(fill="x")
        self._title = tk.Label(
            header,
            text=app.name,
            bg=_PALETTE["chrome"],
            fg=_PALETTE["text"],
            font=("TkDefaultFont", 10, "bold"),
            anchor="w",
            padx=12,
            pady=6,
        )
        self._title.pack(side="left")
        self._back = tk.Button(header, text="← back", command=self.back, relief="flat")
        # Packed and forgotten dynamically, so it only shows when it works.

        self._canvas = tk.Frame(self.root, bg=_PALETTE["bg"])
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._status = tk.Label(
            self.root,
            text="",
            bg=_PALETTE["chrome"],
            fg=_PALETTE["muted"],
            font=("TkDefaultFont", 9),
            anchor="w",
            padx=12,
            pady=4,
        )
        self._status.pack(fill="x")

        #: Leaf widgets by widget id, used to patch instead of rebuild.
        self._widgets: dict[str, Any] = {}
        self._variables: dict[str, Any] = {}
        self._skeleton: tuple[Any, ...] | None = None
        self._patching = False
        self._closing = False

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        """Tear the window down."""
        self._close()

    def _close(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            self.app.stop()
        finally:
            self.root.quit()
            self.root.destroy()

    def run(self) -> None:
        """Enter the Tk main loop until the window is closed."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:  # pragma: no cover - interactive
            self._close()

    # -- rendering ---------------------------------------------------------
    def render(self, tree: dict[str, Any]) -> None:
        """Show a freshly rendered tree.

        Timers fire on scheduler threads, and Tk may only be touched from the
        thread owning the window, so the work is handed to the event loop.
        """
        if self._closing:
            return
        self.root.after(0, lambda: self._apply(tree))

    def _apply(self, tree: dict[str, Any]) -> None:
        if self._closing:
            return
        depth = self.app.navigator.depth
        self._title.configure(text=str(tree.get("screen") or self.app.name))
        if depth > 1:
            self._back.pack(side="right", padx=8)
        else:
            self._back.pack_forget()

        shape = skeleton(tree)
        try:
            if shape == self._skeleton:
                self._patch(tree)
            else:
                self._rebuild(tree)
                self._skeleton = shape
        except Exception as error:  # pragma: no cover - defensive
            _log.exception("preview render failed")
            self._status.configure(text=f"⚠ render error: {error}")

    def _rebuild(self, tree: dict[str, Any]) -> None:
        """Throw the view away and build it again from scratch."""
        for child in self._canvas.winfo_children():
            child.destroy()
        self._widgets.clear()
        self._variables.clear()
        self._build(self._canvas, tree)

    def _patch(self, node: dict[str, Any]) -> None:
        """Update the values of existing widgets in place."""
        self._patching = True
        try:
            self._patch_node(node)
        finally:
            self._patching = False

    def _patch_node(self, node: dict[str, Any]) -> None:
        widget = self._widgets.get(str(node.get("id", "")))
        props = node.get("props", {})
        kind = node.get("type")

        if widget is not None:
            state = "normal" if node.get("enabled", True) else "disabled"
            if kind in ("Button", "TextInput", "Switch"):
                widget.configure(state=state)
            if kind in ("Label", "Button"):
                widget.configure(text=str(props.get("text", "")))
            elif kind == "ProgressBar":
                if not props.get("indeterminate"):
                    widget.configure(value=float(props.get("value", 0)))
            elif kind == "Switch":
                variable = self._variables.get(node["id"])
                checked = bool(props.get("checked"))
                if variable is not None and variable.get() != checked:
                    variable.set(checked)
                widget.configure(text="on" if checked else "off")
            elif kind == "TextInput":
                variable = self._variables.get(node["id"])
                value = str(props.get("value", ""))
                # Never write into the field being typed in: it would move the
                # caret to the end after every keystroke.
                focused = self.root.focus_get() is widget
                if variable is not None and not focused and variable.get() != value:
                    variable.set(value)

        for child in node.get("children", ()):
            self._patch_node(child)

    def toast(self, message: str) -> None:
        """Show a transient message in the status strip."""
        if self._closing:
            return
        self.root.after(0, lambda: self._status.configure(text=f"🔔 {message}"))
        self.root.after(2500, self._clear_toast)

    def _clear_toast(self) -> None:
        if not self._closing:
            self._status.configure(text="")

    # -- widget construction ----------------------------------------------
    def _build(self, parent: tk.Misc, node: dict[str, Any]) -> None:
        """Create the Tk widget for ``node`` and pack it into ``parent``."""
        if not node.get("visible", True):
            return

        tk = self._tk
        kind = node.get("type", "Label")
        props = node.get("props", {})
        style = node.get("style", {})
        enabled = node.get("enabled", True)
        widget_id = str(node.get("id", ""))
        background = self._background(style)
        pad = 2

        if kind == "ScrollView":
            if props.get("horizontal"):
                # No horizontal scrolling in the preview; a plain row keeps the
                # arrangement honest, which is what the picture is for.
                self._build_row(parent, node, background)
            else:
                self._build_scroll(parent, node, background)
            return

        if kind in _VERTICAL:
            frame = tk.Frame(parent, bg=background)
            frame.pack(fill="both" if kind != "Column" else "x", expand=kind != "Column", pady=pad)
            self._build_children(frame, node, background)
            return

        if kind == "Row":
            self._build_row(parent, node, background)
            return

        if kind == "Grid":
            self._build_grid(parent, node, props, background)
            return

        if kind == "Divider":
            thickness = max(1, int(props.get("thickness", 1)))
            colour = _PALETTE["line"]
            tk.Frame(parent, height=thickness, bg=colour).pack(fill="x", pady=6)
            return

        if kind == "Label":
            label = tk.Label(
                parent,
                text=str(props.get("text", "")),
                bg=background,
                fg=self._colour(style.get("color"), _PALETTE["text"]),
                font=self._font(style),
                justify="left",
                anchor="w",
                wraplength=340,
            )
            label.pack(fill="x", pady=pad)
            self._widgets[widget_id] = label
            return

        if kind == "Button":
            button = tk.Button(
                parent,
                text=str(props.get("text", "")),
                font=self._font(style),
                state="normal" if enabled else "disabled",
                command=lambda: self._dispatch(widget_id, "press", ""),
            )
            button.pack(fill="x", pady=pad)
            self._widgets[widget_id] = button
            return

        if kind == "TextInput":
            variable = tk.StringVar(value=str(props.get("value", "")))
            entry = tk.Entry(
                parent,
                textvariable=variable,
                font=self._font(style),
                show="•" if props.get("password") else "",
                state="normal" if enabled else "disabled",
            )
            entry.pack(fill="x", pady=pad)
            variable.trace_add(
                "write",
                lambda *_: self._dispatch(widget_id, "change", variable.get()),
            )
            self._widgets[widget_id] = entry
            self._variables[widget_id] = variable
            if props.get("placeholder") and not props.get("value"):
                self._show_placeholder(entry, str(props["placeholder"]))
            return

        if kind == "Switch":
            variable = tk.BooleanVar(value=bool(props.get("checked")))
            toggle = tk.Checkbutton(
                parent,
                variable=variable,
                text="on" if variable.get() else "off",
                bg=background,
                anchor="w",
                state="normal" if enabled else "disabled",
                command=lambda: self._dispatch(
                    widget_id, "toggle", "true" if variable.get() else "false"
                ),
            )
            toggle.pack(fill="x", pady=pad)
            self._widgets[widget_id] = toggle
            self._variables[widget_id] = variable
            return

        if kind == "ProgressBar":
            from tkinter import ttk

            maximum = float(props.get("maximum", 100)) or 100.0
            bar = ttk.Progressbar(
                parent,
                maximum=maximum,
                value=float(props.get("value", 0)),
                mode="indeterminate" if props.get("indeterminate") else "determinate",
            )
            bar.pack(fill="x", pady=pad)
            if props.get("indeterminate"):
                bar.start(60)
            self._widgets[widget_id] = bar
            return

        if kind == "Image":
            image = tk.Label(
                parent,
                text=f"🖼 {props.get('source', '')}",
                fg=_PALETTE["muted"],
                bg=background,
                anchor="w",
            )
            image.pack(fill="x", pady=pad)
            self._widgets[widget_id] = image
            return

        if kind == "Spacer":
            tk.Frame(parent, height=int(props.get("size", 8)), bg=background).pack()
            return

        tk.Label(parent, text=f"<{kind}>", fg=_PALETTE["muted"], bg=background).pack(anchor="w")

    def _build_children(self, frame: tk.Misc, node: dict[str, Any], background: str) -> None:
        """Stack children vertically, honouring the container's spacing."""
        spacing = int(node.get("props", {}).get("spacing", 0))
        for index, child in enumerate(node.get("children", ())):
            if index and spacing:
                self._tk.Frame(frame, height=spacing, bg=background).pack()
            self._build(frame, child)

    def _build_row(self, parent: tk.Misc, node: dict[str, Any], background: str) -> None:
        """A horizontal band; Expanded/Flexible children share the leftovers."""
        tk = self._tk
        frame = tk.Frame(parent, bg=background)
        frame.pack(fill="x", pady=2)
        spacing = int(node.get("props", {}).get("spacing", 0))
        for index, child in enumerate(node.get("children", ())):
            flex = self._flex_of(child)
            cell = tk.Frame(frame, bg=background)
            cell.pack(
                side="left",
                expand=bool(flex),
                fill="both" if flex else "none",
                padx=(spacing if index else 0, 0),
            )
            self._build(cell, child)

    def _build_grid(
        self, parent: tk.Misc, node: dict[str, Any], props: dict[str, Any], background: str
    ) -> None:
        """Lay a Grid out with Tk's own grid geometry manager."""
        tk = self._tk
        columns = max(1, int(props.get("columns", 2)))
        row_spacing = int(props.get("row_spacing", 0))
        column_spacing = int(props.get("column_spacing", 0))

        frame = tk.Frame(parent, bg=background)
        frame.pack(fill="x", pady=2)
        for column in range(columns):
            # uniform= is what makes the columns genuinely equal in width.
            frame.columnconfigure(column, weight=1, uniform="pymobile-grid")

        for index, child in enumerate(node.get("children", ())):
            row, column = divmod(index, columns)
            cell = tk.Frame(frame, bg=background)
            cell.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else column_spacing, 0),
                pady=(0 if row == 0 else row_spacing, 0),
            )
            self._build(cell, child)

    def _build_scroll(self, parent: tk.Misc, node: dict[str, Any], background: str) -> None:
        """A scrollable region: a Canvas holding a Frame, plus a scrollbar."""
        tk = self._tk
        holder = tk.Frame(parent, bg=background)
        holder.pack(fill="both", expand=True)

        canvas = tk.Canvas(holder, bg=background, highlightthickness=0)
        scrollbar = tk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=background)

        window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        content.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Keep the inner frame as wide as the viewport, or children packed with
        # fill="x" would collapse to their natural width.
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))

        self._build_children(content, node, background)

    def _show_placeholder(self, entry: tk.Entry, text: str) -> None:
        """Grey placeholder text that disappears on focus."""
        entry.insert(0, text)
        entry.configure(fg=_PALETTE["muted"])

        def on_focus_in(_event: object) -> None:
            if entry.get() == text:
                entry.delete(0, "end")
                entry.configure(fg=_PALETTE["text"])

        entry.bind("<FocusIn>", on_focus_in)

    # -- helpers -----------------------------------------------------------
    def _flex_of(self, node: dict[str, Any]) -> int:
        """The flex share a row child claims, or 0 for a fixed-size child."""
        if node.get("type") in ("Expanded", "Flexible"):
            return int(node.get("props", {}).get("flex", 1))
        weight = node.get("style", {}).get("weight")
        return int(weight) if weight else 0

    def _font(self, style: dict[str, Any]) -> tuple[str, int, str]:
        size = int(style.get("font_size", 11))
        weight = "bold" if style.get("bold") else "normal"
        return ("TkDefaultFont", max(7, size), weight)

    def _colour(self, value: Any, fallback: str) -> str:
        """Translate a framework colour into one Tk understands."""
        if not isinstance(value, str) or not value.startswith("#"):
            return fallback
        # Tk knows #RGB and #RRGGBB but not Android's #AARRGGBB.
        return f"#{value[3:]}" if len(value) == 9 else value

    def _background(self, style: dict[str, Any]) -> str:
        return self._colour(style.get("background"), _PALETTE["bg"])

    def _dispatch(self, widget_id: str, kind: str, value: str) -> None:
        """Feed an interaction back into the application."""
        # Writing a value during a patch must not look like user input.
        if self._closing or self._patching or not widget_id:
            return
        try:
            self.app.handle_ui_event(widget_id, kind, value)
        except Exception as error:  # pragma: no cover - user callback failed
            _log.exception("handler for %s failed", widget_id)
            self._status.configure(text=f"⚠ {type(error).__name__}: {error}")

    def back(self) -> None:
        """Emulate the hardware back button."""
        self._dispatch("system", "back", "")


def run_gui(
    app: App,
    *,
    title: str = "",
    scale: float = 1.0,
    on_ready: Callable[[GuiPreview], None] | None = None,
) -> GuiPreview:
    """Show ``app`` in an interactive window and block until it is closed."""
    preview = GuiPreview(app, title=title, scale=scale)
    if on_ready is not None:
        on_ready(preview)
    preview.run()
    return preview
