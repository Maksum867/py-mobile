"""A browser-based interactive preview.

The Tk preview needs a display; this one needs a browser, which is what a
remote machine, a container or a Codespace actually has. It serves the running
application over HTTP: the widget tree is rendered as HTML, interactions are
posted back, and the page polls for a new tree so a timer tick or a background
update appears on its own.

Nothing is compiled or bundled — the page is a few hundred bytes of hand-written
HTML and JavaScript built from the same serialised tree the phone receives, so
the preview cannot drift from the real renderer.
"""

from __future__ import annotations

import json
import threading
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

from ...logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..app import App

__all__ = ["WebPreview", "render_html", "serve"]

_log = get_logger("ui.web")

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: {color_scheme}; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: {page_bg}; color: {text}; font: 15px/1.45 system-ui, sans-serif; }}
  .phone {{ max-width: 420px; margin: 24px auto; background: {phone_bg}; min-height: 80vh;
           border-radius: 22px; box-shadow: 0 6px 32px rgba(0,0,0,.18); overflow: hidden;
           display: flex; flex-direction: column; color: {text}; }}
  .bar {{ background: {bar_bg}; border-bottom: 1px solid {line}; padding: 10px 16px;
          display: flex; align-items: center; gap: 12px; font-weight: 600; }}
  .bar button {{ font: inherit; font-weight: 500; border: 0; background: none;
                 color: {primary}; cursor: pointer; padding: 0; }}
  .screen {{ padding: 16px; flex: 1; }}
  .status {{ background: {bar_bg}; border-top: 1px solid {line}; padding: 6px 16px;
             min-height: 28px; color: {muted}; font-size: 13px; }}
  .row {{ display: flex; }}
  .col {{ display: flex; flex-direction: column; }}
  .grid {{ display: grid; }}
  button.w {{ font: inherit; padding: 9px 14px; border-radius: 8px; cursor: pointer;
              border: 1px solid {line}; background: {bar_bg}; color: {text}; width: 100%; }}
  button.w:disabled {{ opacity: .45; cursor: not-allowed; }}
  input.w, textarea.w, select.w {{ font: inherit; padding: 8px 10px; border: 1px solid {line};
             border-radius: 8px; width: 100%; background: {phone_bg}; color: {text}; }}
  progress.w {{ width: 100%; height: 10px; }}
  hr.w {{ border: 0; border-top: 1px solid {line}; margin: 8px 0; width: 100%; }}
  .muted {{ color: {muted}; }}
  table.w {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  table.w th, table.w td {{ border: 1px solid {line}; padding: 6px 8px; text-align: left; }}
  a.w {{ color: {primary}; }}
  .avatar {{ display: inline-flex; align-items: center; justify-content: center;
             border-radius: 50%; font-weight: 600; }}
  .seg {{ display: flex; gap: 0; }}
  .seg button {{ flex: 1; border-radius: 0; }}
</style>
</head>
<body>
<div class="phone">
  <div class="bar"><span id="title">{title}</span>
    <button id="back" style="display:none" onclick="send('system','back','')">← back</button>
  </div>
  <div class="screen" id="screen">{body}</div>
  <div class="status" id="status"></div>
</div>
<script>
let version = {version};
async function send(id, kind, value) {{
  const r = await fetch('/event', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{id, kind, value}})
  }});
  apply(await r.json());
}}
function apply(state) {{
  if (state.version === version) return;
  version = state.version;
  const active = document.activeElement;
  const keep = active && active.dataset ? active.dataset.wid : null;
  const start = active && active.selectionStart;
  document.getElementById('screen').innerHTML = state.body;
  document.getElementById('title').textContent = state.title;
  document.getElementById('back').style.display = state.depth > 1 ? '' : 'none';
  document.getElementById('status').textContent = state.status || '';
  if (keep) {{  // typing must survive a redraw
    const again = document.querySelector('[data-wid="' + keep + '"]');
    if (again) {{ again.focus(); if (start != null && again.setSelectionRange)
      again.setSelectionRange(start, start); }}
  }}
}}
async function poll() {{
  try {{ apply(await (await fetch('/state?v=' + version)).json()); }}
  catch (e) {{ document.getElementById('status').textContent = 'disconnected'; }}
  setTimeout(poll, 400);
}}
poll();
</script>
</body>
</html>
"""


def _style_css(style: dict[str, Any]) -> str:
    """Translate a serialised Style into inline CSS."""
    parts: list[str] = []
    colour = style.get("color")
    if isinstance(colour, str):
        parts.append(f"color:{_css_colour(colour)}")
    background = style.get("background")
    if isinstance(background, str):
        parts.append(f"background:{_css_colour(background)}")
    if style.get("font_size"):
        parts.append(f"font-size:{style['font_size']}px")
    if style.get("bold"):
        parts.append("font-weight:700")
    if style.get("italic"):
        parts.append("font-style:italic")
    for name, prop in (("padding", "padding"), ("margin", "margin")):
        box = style.get(name)
        if isinstance(box, list) and len(box) == 4:
            left, top, right, bottom = box
            parts.append(f"{prop}:{top}px {right}px {bottom}px {left}px")
    if style.get("corner_radius"):
        parts.append(f"border-radius:{style['corner_radius']}px")
    for key, prop in (
        ("min_width", "min-width"),
        ("max_width", "max-width"),
        ("min_height", "min-height"),
        ("max_height", "max-height"),
    ):
        if style.get(key) is not None:
            parts.append(f"{prop}:{style[key]}px")
    if style.get("aspect_ratio"):
        parts.append(f"aspect-ratio:{style['aspect_ratio']:.4f}")
    for key, prop in (("width", "width"), ("height", "height")):
        value = style.get(key)
        if isinstance(value, int):
            parts.append(f"{prop}:{value}px")
        elif isinstance(value, str) and value in ("match", "fill", "match_parent"):
            parts.append(f"{prop}:100%")
    if style.get("elevation"):
        depth = int(style["elevation"])
        parts.append(f"box-shadow:0 {depth}px {depth * 2}px rgba(0,0,0,.2)")
    return ";".join(parts)


def _css_colour(value: str) -> str:
    """#AARRGGBB is an Android convention; CSS wants #RRGGBBAA."""
    if len(value) == 9 and value.startswith("#"):
        return f"#{value[3:]}{value[1:3]}"
    return value


def _alignment(value: str | None) -> str:
    return {
        "center": "center",
        "end": "flex-end",
        "space_between": "space-between",
        "stretch": "stretch",
        "start": "flex-start",
    }.get(value or "", "flex-start")


def render_html(node: dict[str, Any]) -> str:
    """Render one serialised widget node (and its children) as HTML."""
    if not node.get("visible", True):
        return ""

    kind = node.get("type", "Label")
    props = node.get("props", {})
    style = node.get("style", {})
    css = _style_css(style)
    widget_id = escape(str(node.get("id", "")), quote=True)
    disabled = "" if node.get("enabled", True) else " disabled"
    children = node.get("children", ())
    inner = "".join(render_html(child) for child in children)

    if kind in ("Column", "Container", "SafeArea", "Stack", "RadioGroup", "List"):
        gap = props.get("spacing", 0)
        align = _alignment(props.get("cross_align"))
        extra = f"gap:{gap}px;align-items:{align};{css}"
        return f'<div class="col" style="{extra}">{inner}</div>'

    if kind == "ScrollView":
        gap = props.get("spacing", 0)
        horizontal = props.get("horizontal")
        flow = "row" if horizontal else "column"
        overflow = "overflow-x:auto" if horizontal else "overflow-y:auto;max-height:60vh"
        return (
            f'<div class="col" style="flex-direction:{flow};gap:{gap}px;{overflow};{css}">'
            f"{inner}</div>"
        )

    if kind == "Row":
        gap = props.get("spacing", 0)
        justify = _alignment(props.get("align"))
        align = _alignment(props.get("cross_align")) if props.get("cross_align") else "center"
        return (
            f'<div class="row" style="gap:{gap}px;justify-content:{justify};'
            f'align-items:{align};{css}">{inner}</div>'
        )

    if kind == "Grid":
        columns = max(1, int(props.get("columns", 2)))
        row_gap = props.get("row_spacing", 0)
        column_gap = props.get("column_spacing", 0)
        return (
            f'<div class="grid" style="grid-template-columns:repeat({columns},1fr);'
            f'row-gap:{row_gap}px;column-gap:{column_gap}px;{css}">{inner}</div>'
        )

    if kind in ("Expanded", "Flexible"):
        flex = int(props.get("flex", 1))
        basis = "0" if props.get("fit", "tight") == "tight" else "auto"
        return f'<div style="flex:{flex} {flex} {basis};min-width:0;{css}">{inner}</div>'

    if kind == "Divider":
        if props.get("vertical"):
            width = props.get("thickness", 1)
            return (
                f'<div style="width:{width}px;align-self:stretch;background:rgba(0,0,0,.12)"></div>'
            )
        return f'<hr class="w" style="{css}">'

    if kind == "Label":
        # The id is carried through so the browser inspector shows which
        # widget a node is — the same readable ids find() uses.
        text = escape(str(props.get("text", "")))
        return f'<div data-wid="{widget_id}" style="{css}">{text}</div>'

    if kind == "Button":
        label = escape(str(props.get("text", "")))
        return (
            f'<button class="w" data-wid="{widget_id}"{disabled} style="{css}" '
            f"onclick=\"send('{widget_id}','press','')\">{label}</button>"
        )

    if kind == "TextInput":
        value = escape(str(props.get("value", "")), quote=True)
        placeholder = escape(str(props.get("placeholder", "")), quote=True)
        kind_attr = "password" if props.get("password") else "text"
        if props.get("multiline"):
            body = escape(str(props.get("value", "")))
            return (
                f'<textarea class="w" data-wid="{widget_id}" placeholder="{placeholder}"'
                f'{disabled} style="{css}" '
                f"oninput=\"send('{widget_id}','change',this.value)\">{body}</textarea>"
            )
        return (
            f'<input class="w" type="{kind_attr}" data-wid="{widget_id}" value="{value}" '
            f'placeholder="{placeholder}"{disabled} style="{css}" '
            f"oninput=\"send('{widget_id}','change',this.value)\">"
        )

    if kind == "Switch":
        checked = " checked" if props.get("checked") else ""
        return (
            f'<label style="display:flex;gap:8px;align-items:center;{css}">'
            f'<input type="checkbox" data-wid="{widget_id}"{checked}{disabled} '
            f"onchange=\"send('{widget_id}','toggle',this.checked?'true':'false')\">"
            f'<span class="muted">{"on" if props.get("checked") else "off"}</span></label>'
        )

    if kind == "ProgressBar":
        if props.get("indeterminate"):
            return f'<progress class="w" style="{css}"></progress>'
        maximum = props.get("maximum", 100) or 100
        value = props.get("value", 0)
        return f'<progress class="w" max="{maximum}" value="{value}" style="{css}"></progress>'

    if kind == "Image":
        return f'<div class="muted" style="{css}">🖼 {escape(str(props.get("source", "")))}</div>'

    if kind == "Spacer":
        return f'<div style="height:{props.get("size", 8)}px;flex:0 0 auto"></div>'

    if kind == "Slider":
        minimum = props.get("minimum", 0)
        maximum = props.get("maximum", 100)
        value = props.get("value", 0)
        return (
            f'<input class="w" type="range" data-wid="{widget_id}" min="{minimum}" '
            f'max="{maximum}" value="{value}"{disabled} style="{css}" '
            f"oninput=\"send('{widget_id}','change',this.value)\">"
        )

    if kind == "Checkbox":
        checked = " checked" if props.get("checked") else ""
        return (
            f'<label style="display:flex;gap:8px;align-items:center;{css}">'
            f'<input type="checkbox" data-wid="{widget_id}"{checked}{disabled} '
            f"onchange=\"send('{widget_id}','toggle',this.checked?'true':'false')\">"
            f"</label>"
        )

    if kind == "RatingBar":
        rating = props.get("rating", 0)
        maximum = int(props.get("maximum", 5) or 5)
        stars = "".join(
            f'<button type="button" data-wid="{widget_id}"{disabled} '
            f"onclick=\"send('{widget_id}','change','{i}')\">"
            f"{'★' if i <= float(rating or 0) else '☆'}</button>"
            for i in range(1, maximum + 1)
        )
        return f'<div style="display:flex;gap:2px;{css}">{stars}</div>'

    if kind == "Dropdown":
        options = props.get("options") or []
        selected = str(props.get("value", ""))
        items = "".join(
            f'<option value="{escape(str(opt), quote=True)}"'
            f'{" selected" if str(opt) == selected else ""}>{escape(str(opt))}</option>'
            for opt in options
        )
        return (
            f'<select class="w" data-wid="{widget_id}"{disabled} style="{css}" '
            f"onchange=\"send('{widget_id}','change',this.value)\">{items}</select>"
        )

    if kind == "Chip":
        label = escape(str(props.get("text", "")))
        selected = " font-weight:700;" if props.get("selected") else ""
        return (
            f'<button class="w" data-wid="{widget_id}"{disabled} '
            f'style="border-radius:999px;{selected}{css}" '
            f"onclick=\"send('{widget_id}','press','')\">{label}</button>"
        )

    if kind == "Badge":
        label = escape(str(props.get("text", "")))
        bg = _css_colour(str(props.get("background", "#3F51B5")))
        fg = _css_colour(str(props.get("color", "#FFFFFF")))
        return (
            f'<span data-wid="{widget_id}" style="display:inline-block;padding:2px 8px;'
            f'border-radius:999px;background:{bg};color:{fg};font-size:12px;{css}">'
            f"{label}</span>"
        )

    if kind == "Stepper":
        value = escape(str(props.get("value", 0)))
        return (
            f'<div data-wid="{widget_id}" style="display:flex;gap:8px;align-items:center;{css}">'
            f'<button class="w" style="width:auto"{disabled} '
            f"onclick=\"send('{widget_id}','decrement','')\">-</button>"
            f"<span>{value}</span>"
            f'<button class="w" style="width:auto"{disabled} '
            f"onclick=\"send('{widget_id}','increment','')\">+</button>"
            f"</div>"
        )

    if kind == "SearchBar":
        value = escape(str(props.get("value", "")), quote=True)
        placeholder = escape(str(props.get("placeholder", "")), quote=True)
        return (
            f'<input class="w" type="search" data-wid="{widget_id}" value="{value}" '
            f'placeholder="{placeholder}"{disabled} style="{css}" '
            f"oninput=\"send('{widget_id}','change',this.value)\" "
            f"onkeydown=\"if(event.key==='Enter')send('{widget_id}','search',this.value)\">"
        )

    if kind == "RadioButton":
        checked = " checked" if props.get("selected") else ""
        label = escape(str(props.get("text", "")))
        return (
            f'<label style="display:flex;gap:8px;align-items:center;{css}">'
            f'<input type="radio" data-wid="{widget_id}"{checked}{disabled} '
            f"onchange=\"send('{widget_id}','press','')\">"
            f"<span>{label}</span></label>"
        )

    if kind == "SegmentedButtons":
        options = props.get("options") or []
        selected = str(props.get("value", ""))
        buttons = "".join(
            f'<button class="w" data-wid="{widget_id}"{disabled} '
            f'style="{"font-weight:700;" if str(opt) == selected else ""}" '
            f"onclick=\"send('{widget_id}','change','{escape(str(opt), quote=True)}')\">"
            f"{escape(str(opt))}</button>"
            for opt in options
        )
        return f'<div class="seg" style="{css}">{buttons}</div>'

    if kind == "ProgressText":
        text = escape(str(props.get("text", "")))
        maximum = props.get("maximum", 100) or 100
        value = props.get("value", 0)
        return (
            f'<div data-wid="{widget_id}" style="{css}">'
            f'<progress class="w" max="{maximum}" value="{value}"></progress>'
            f'<div class="muted">{text}</div></div>'
        )

    if kind == "Link":
        label = escape(str(props.get("text", "")))
        url = escape(str(props.get("url", "")), quote=True)
        return (
            f'<a class="w" data-wid="{widget_id}" href="{url or "#"}" '
            f'style="{css}" '
            f"onclick=\"event.preventDefault();send('{widget_id}','press','')\">{label}</a>"
        )

    if kind == "DataTable":
        headers = "".join(f"<th>{escape(str(h))}</th>" for h in (props.get("headers") or []))
        rows = "".join(
            "<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in row) + "</tr>"
            for row in (props.get("rows") or [])
        )
        return (
            f'<table class="w" data-wid="{widget_id}" style="{css}">'
            f"<thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"
        )

    if kind == "Avatar":
        text = escape(str(props.get("text", "") or "?"))
        size = int(props.get("size", 48) or 48)
        bg = _css_colour(str(props.get("background", "#3F51B5")))
        fg = _css_colour(str(props.get("color", "#FFFFFF")))
        return (
            f'<div class="avatar" data-wid="{widget_id}" '
            f'style="width:{size}px;height:{size}px;background:{bg};color:{fg};{css}">'
            f"{text}</div>"
        )

    if kind == "ListTile":
        title = escape(str(props.get("title", "")))
        subtitle = escape(str(props.get("subtitle", "")))
        trailing = escape(str(props.get("trailing", "")))
        return (
            f'<button class="w" data-wid="{widget_id}"{disabled} style="text-align:left;{css}" '
            f"onclick=\"send('{widget_id}','press','')\">"
            f"<div>{title}</div>"
            f'<div class="muted">{subtitle}</div>'
            f'<div class="muted">{trailing}</div></button>'
        )

    return f'<div class="muted">&lt;{escape(kind)}&gt;</div>'


class WebPreview:
    """Serves an application to a browser and feeds interactions back."""

    def __init__(self, app: App, *, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.app = app
        self.host = host
        self.port = port
        self._tree: dict[str, Any] = {}
        self._status = ""
        self._version = 0
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None

    # -- state -------------------------------------------------------------
    def update(self, tree: dict[str, Any]) -> None:
        """Publish a newly rendered tree to connected browsers."""
        with self._lock:
            self._tree = tree
            self._version += 1

    def toast(self, message: str) -> None:
        """Show a message in the status strip."""
        with self._lock:
            self._status = message
            self._version += 1

    def state(self) -> dict[str, Any]:
        """The payload the page polls for."""
        with self._lock:
            tree = self._tree
            status = self._status
            version = self._version
        return {
            "version": version,
            "title": str(tree.get("screen") or self.app.name),
            "body": render_html(tree) if tree else "",
            "depth": self.app.navigator.depth,
            "status": status,
        }

    def _theme_vars(self) -> dict[str, str]:
        """Chrome colours that follow ``App(theme=...)``."""
        theme = getattr(self.app, "theme", None)
        dark = bool(getattr(theme, "is_dark", False))
        colour = getattr(theme, "color", None)

        def pick(name: str, light: str, dark_value: str) -> str:
            if colour is not None:
                try:
                    return str(colour(name))
                except Exception:
                    pass
            return dark_value if dark else light

        return {
            "color_scheme": "dark" if dark else "light",
            "page_bg": "#121212" if dark else "#eceff1",
            "phone_bg": pick("BACKGROUND", "#fff", "#121212"),
            "bar_bg": pick("SURFACE", "#f7f8fa", "#1e1e1e"),
            "text": pick("TEXT", "#212121", "#EEEEEE"),
            "muted": pick("TEXT_MUTED", "#607d8b", "#9e9e9e"),
            "primary": pick("PRIMARY", "#3F51B5", "#9fa8da"),
            "line": "#333" if dark else "#e3e7ea",
        }

    def page(self) -> str:
        """The full HTML document."""
        state = self.state()
        return _PAGE.format(
            title=escape(state["title"]),
            body=state["body"],
            version=state["version"],
            **self._theme_vars(),
        )

    def dispatch(self, widget_id: str, kind: str, value: str) -> None:
        """Apply a browser interaction to the application."""
        try:
            self.app.handle_ui_event(widget_id, kind, value)
        except Exception as error:  # pragma: no cover - user callback failed
            _log.exception("handler for %s failed", widget_id)
            self.toast(f"{type(error).__name__}: {error}")

    # -- server ------------------------------------------------------------
    def serve_forever(self) -> None:
        """Run the HTTP server until interrupted."""
        server = self._build_server()
        _log.info("serving on http://%s:%d", self.host, server.server_port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:  # pragma: no cover - interactive
            pass
        finally:
            server.shutdown()
            server.server_close()

    def start_background(self) -> int:
        """Start serving on a daemon thread and return the bound port."""
        server = self._build_server()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return int(server.server_port)

    def stop(self) -> None:
        """Shut the server down."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def _build_server(self) -> ThreadingHTTPServer:
        preview = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: Any) -> None:
                """Silence the default per-request stderr logging."""

            def _reply(self, body: bytes, content_type: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path.startswith("/state"):
                    payload = json.dumps(preview.state()).encode("utf-8")
                    self._reply(payload, "application/json; charset=utf-8")
                    return
                self._reply(preview.page().encode("utf-8"), "text/html; charset=utf-8")

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    event = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    event = {}
                preview.dispatch(
                    str(event.get("id", "")),
                    str(event.get("kind", "")),
                    str(event.get("value", "")),
                )
                payload = json.dumps(preview.state()).encode("utf-8")
                self._reply(payload, "application/json; charset=utf-8")

        server = ThreadingHTTPServer((self.host, self.port), Handler)
        server.daemon_threads = True
        self._server = server
        self.port = int(server.server_port)
        return server


def serve(app: App, *, host: str = "0.0.0.0", port: int = 8765) -> WebPreview:
    """Serve ``app`` in a browser, blocking until interrupted."""
    preview = WebPreview(app, host=host, port=port)
    preview.serve_forever()
    return preview
