"""Render a widget tree to a picture on the desktop.

The phone has a Java renderer; the desktop has no native views, so this
module turns the serialised tree into something you can actually look at.
Two backends are offered:

* :func:`render_ascii` — a dependency-free text picture, always available.
* :func:`render_png`   — a real raster image, used when Pillow is installed
  (the same optional extra the icon resizer uses).

Both accept either a live :class:`~pymobile.core.ui.widget.Widget` or a
serialised ``to_dict`` node, so the same code serves the CLI, tests and
notebooks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

__all__ = ["render_ascii", "render_png", "ascii_picture", "snapshot_path", "assert_snapshot"]

_BAR_WIDTH = 16
_DIVIDER_WIDTH = 24


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def render_ascii(widget_or_tree: Any, *, show_ids: bool = False, title: str = "") -> str:
    """Return a text picture of the widget tree."""
    node = _as_node(widget_or_tree)
    lines = _node_lines(node, show_ids=show_ids)
    if not lines:
        lines = ["<empty screen>"]
    width = max(len(line) for line in lines)
    body = "\n".join(line.rstrip() for line in lines)
    if title:
        bar = "─" * (width + 2)
        return f"┌{bar}┐\n│ {title.ljust(width)} │\n├{bar}┤\n{body}\n└{bar}┘"
    return body


def ascii_picture(widget_or_tree: Any, **kwargs: Any) -> str:  # alias
    """Backwards-friendly alias for :func:`render_ascii`."""
    return render_ascii(widget_or_tree, **kwargs)


#: TrueType faces that ship with common systems and cover Latin, Cyrillic and
#: Greek. Pillow's built-in bitmap font is ASCII-only, which turns every
#: non-English interface into a row of boxes.
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "/usr/share/fonts/google-noto/NotoSansMono-Regular.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _preview_font(image_font: Any, scale: int) -> Any:
    """Return a Unicode-capable font, falling back to Pillow's default.

    ``PYMOBILE_PREVIEW_FONT`` overrides the search with an explicit .ttf path.
    """
    override = os.environ.get("PYMOBILE_PREVIEW_FONT")
    candidates = (override, *_FONT_CANDIDATES) if override else _FONT_CANDIDATES
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            try:
                return image_font.truetype(candidate, scale + 2)
            except Exception:  # pragma: no cover - unreadable/odd font file
                continue
    try:  # last resort: ASCII-only, but better than no picture at all
        return image_font.load_default()
    except Exception:  # pragma: no cover - very old Pillow
        return None


def render_png(widget_or_tree: Any, path: str, *, scale: int = 12) -> str:
    """Draw the tree to ``path`` as PNG using Pillow.

    Raises :class:`RuntimeError` with an install hint when Pillow is missing,
    so callers can fall back to :func:`render_ascii`.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on the extra
        raise RuntimeError(
            "PNG preview needs Pillow; install it with `pip install Pillow`."
        ) from exc

    lines = _node_lines(_as_node(widget_or_tree), show_ids=False)
    if not lines:
        lines = ["<empty screen>"]
    font = _preview_font(ImageFont, scale)
    line_height = scale + 6
    width = max(len(line) for line in lines) * (scale // 2 + 1) + 24
    height = len(lines) * line_height + 24
    image = Image.new("RGB", (width, height), "#101418")
    draw = ImageDraw.Draw(image)
    y = 12
    for line in lines:
        draw.text((12, y), line, fill="#e6e6e6", font=font)
        y += line_height
    image.save(path)
    return path


# ---------------------------------------------------------------------------
# tree -> list of equal-height text rows
# ---------------------------------------------------------------------------
def _as_node(widget_or_tree: Any) -> dict[str, Any]:
    node = widget_or_tree.to_dict() if hasattr(widget_or_tree, "to_dict") else widget_or_tree
    if not isinstance(node, dict):
        raise TypeError(f"cannot preview {type(widget_or_tree).__name__}")
    return node


def _node_lines(node: dict[str, Any], *, show_ids: bool = False) -> list[str]:
    if not node.get("visible", True):
        return []

    node_type = node.get("type", "")
    children = node.get("children", ())

    if node_type == "Row" or (
        node_type == "ScrollView" and node.get("props", {}).get("horizontal")
    ):
        rows = _join_horizontal([_node_lines(child, show_ids=show_ids) for child in children])
    elif node_type == "Grid":
        rows = _grid_lines(node, show_ids=show_ids)
    elif node_type in ("Expanded", "Flexible"):
        # A flex wrapper draws exactly as its child; the space it claims is a
        # device-side concept with no meaning in a text picture.
        rows = _join_vertical([_node_lines(child, show_ids=show_ids) for child in children])
    elif node_type in (
        "Column",
        "ScrollView",
        "Stack",
        "Container",
        "SafeArea",
        "RadioGroup",
        "List",
    ):
        rows = _join_vertical([_node_lines(child, show_ids=show_ids) for child in children])
    else:
        rows = _leaf_lines(node)

    if show_ids and rows:
        tag = f"({node.get('id', '?')}) "
        rows = [tag + rows[0], *rows[1:]]
    return rows


def _join_vertical(blocks: list[list[str]]) -> list[str]:
    out: list[str] = []
    for block in blocks:
        out.extend(block)
    return out


def _grid_lines(node: dict[str, Any], *, show_ids: bool = False) -> list[str]:
    """Draw a Grid as real rows of equal-width columns.

    Column widths are computed across the whole grid rather than per row, so
    the text picture shows the same alignment the device does — that is the
    entire reason ``Grid`` exists instead of nested ``Row``s.
    """
    children = list(node.get("children", ()))
    columns = max(1, int(node.get("props", {}).get("columns", 2)))
    cells = [_node_lines(child, show_ids=show_ids) for child in children]

    widths = [0] * columns
    for index, cell in enumerate(cells):
        column = index % columns
        widths[column] = max(widths[column], max((len(line) for line in cell), default=0))

    out: list[str] = []
    for start in range(0, len(cells), columns):
        band = cells[start : start + columns]
        height = max((len(cell) for cell in band), default=0)
        for line_index in range(height):
            parts = []
            for column, cell in enumerate(band):
                text = cell[line_index] if line_index < len(cell) else ""
                parts.append(text.ljust(widths[column]))
            out.append("  ".join(parts).rstrip())
    return out


def _join_horizontal(blocks: list[list[str]]) -> list[str]:
    blocks = [block for block in blocks if block]
    if not blocks:
        return []
    height = max(len(block) for block in blocks)
    widths = [max((len(line) for line in block), default=0) for block in blocks]
    out: list[str] = []
    for row in range(height):
        parts = []
        for block, width in zip(blocks, widths, strict=True):
            cell = block[row] if row < len(block) else ""
            parts.append(cell.ljust(width))
        out.append((" " * 2).join(parts).rstrip())
    return out


def _leaf_lines(node: dict[str, Any]) -> list[str]:
    node_type = node.get("type", "")
    props = node.get("props", {})
    disabled = not node.get("enabled", True)

    if node_type == "Label":
        text = str(props.get("text", ""))
        return [text] if text else [" "]

    if node_type == "Button":
        label = str(props.get("text", "")) or "button"
        return [f"({label})" if not disabled else f"({label}) ✗"]

    if node_type == "TextInput":
        value = props.get("value") or props.get("placeholder") or ""
        masked = props.get("password")
        shown = "•" * len(value) if masked else str(value)
        return [f"⎡{shown or '…'}⎦"]

    if node_type == "Switch":
        return ["[●] on" if props.get("checked") else "[○] off"]

    if node_type == "ProgressBar":
        if props.get("indeterminate"):
            return ["[" + "≈" * _BAR_WIDTH + "]"]
        maximum = props.get("maximum", 100) or 100
        fraction = max(0.0, min(float(props.get("value", 0)) / maximum, 1.0))
        filled = round(_BAR_WIDTH * fraction)
        bar = "█" * filled + "░" * (_BAR_WIDTH - filled)
        return [f"[{bar}] {round(fraction * 100)}%"]

    if node_type == "Image":
        return [f"[🖼 {props.get('source', '')}]"]

    if node_type == "Spacer":
        return [" "]

    if node_type == "Divider":
        return ["│" if props.get("vertical") else "─" * _DIVIDER_WIDTH]

    if node_type == "Slider":
        minimum = float(props.get("minimum", 0))
        maximum = float(props.get("maximum", 100))
        value = max(minimum, min(float(props.get("value", 0)), maximum))
        span = max(maximum - minimum, 1e-9)
        pos = round((value - minimum) / span * (_BAR_WIDTH - 1))
        slider_bar: list[str] = list("─" * _BAR_WIDTH)
        slider_bar[pos] = "●"
        return [f"[{''.join(slider_bar)}] {value:g}"]

    if node_type == "Checkbox":
        return ["[✓] on" if props.get("checked") else "[ ] off"]

    if node_type == "RatingBar":
        rating = max(0.0, min(float(props.get("rating", 0)), int(props.get("maximum", 5))))
        maximum = int(props.get("maximum", 5))
        rating_filled = "★" * round(rating)
        empty = "☆" * max(0, maximum - round(rating))
        return [f"{rating_filled}{empty} {rating:g}/{maximum}"]

    if node_type == "Dropdown":
        return [f"[{props.get('value', '')} ▾]"]

    if node_type == "Chip":
        label = str(props.get("text", "")) or "chip"
        mark = "● " if props.get("selected") else ""
        return [f"({mark}{label})" if not disabled else f"({mark}{label}) ✗"]

    if node_type == "Badge":
        return [f"{{ {props.get('text', '')} }}"]

    if node_type == "Stepper":
        value = props.get("value", 0)
        return [f"(-) {value} (+)"]

    if node_type == "SearchBar":
        value = str(props.get("value", "")) or str(props.get("placeholder", "Search…"))
        return [f"⎡🔍 {value}⎦"]

    if node_type == "RadioButton":
        mark = "◉" if props.get("selected") else "○"
        return [f"{mark} {props.get('text', '')}"]

    if node_type == "SegmentedButtons":
        options = [str(o) for o in props.get("options", [])]
        value = props.get("value", "")
        parts = [f"|{o}|" if o == value else f" {o} " for o in options]
        return [" ".join(parts)]

    if node_type == "ProgressText":
        return [f"[{props.get('text', '')}]"]

    if node_type == "Link":
        text = str(props.get("text", "")) or "link"
        return [f"<{text}>"]

    if node_type == "DataTable":
        headers = [str(h) for h in props.get("headers", [])]
        rows = [[str(c) for c in r] for r in props.get("rows", [])]
        if not headers:
            return ["<table>"]
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(cell))
        header = " | ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
        lines = [header, "-" * len(header)]
        for row in rows:
            padded = [
                cell.ljust(widths[i]) if i < len(widths) else cell for i, cell in enumerate(row)
            ]
            lines.append(" | ".join(padded))
        return lines

    if node_type == "Avatar":
        if props.get("source"):
            return [f"[🖼 {props.get('source', '')}]"]
        return [f"[{props.get('text', '')[:2].upper()}]"]

    if node_type == "ListTile":
        title = str(props.get("title", ""))
        subtitle = str(props.get("subtitle", ""))
        trailing = str(props.get("trailing", ""))
        base = title
        if subtitle:
            base += f" — {subtitle}"
        if trailing:
            base += f"  {trailing}"
        return [f"▸ {base}" if not disabled else f"  {base}"]

    return [f"<{node_type}>"]


# ---------------------------------------------------------------------------
# Snapshot testing helpers (golden-file comparison for ASCII previews)
# ---------------------------------------------------------------------------
def snapshot_path(test_file: str, name: str = "screen", *, ext: str = ".txt") -> Path:
    """Conventional snapshot file location next to a test module.

    ``test_file`` is ``__file__`` from the calling test; the snapshot is written
    to a ``snapshots/`` folder beside it, named ``<module>__<name>.txt``.
    """
    source = Path(test_file).resolve()
    module = source.stem
    return source.parent / "snapshots" / f"{module}__{name}{ext}"


def assert_snapshot(
    widget_or_tree: Any,
    test_file: str,
    name: str = "screen",
    *,
    show_ids: bool = False,
    title: str = "",
    update: bool = False,
) -> str:
    """Compare an ASCII render of ``widget_or_tree`` against a golden snapshot.

    On the first run (or with ``update=True``) the snapshot file is written and
    the test passes; on later runs the render must equal the stored golden text,
    otherwise an :class:`AssertionError` is raised with a diff. This makes it
    trivial to pin a screen's layout in tests and catch unintended changes.

    Returns the rendered text so it can be reused.
    """
    rendered = render_ascii(widget_or_tree, show_ids=show_ids, title=title)
    path = snapshot_path(test_file, name)
    if update or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        return rendered
    golden = path.read_text(encoding="utf-8")
    if rendered != golden:
        import difflib

        diff = "\n".join(
            difflib.unified_diff(
                golden.splitlines(),
                rendered.splitlines(),
                fromfile="snapshot",
                tofile="rendered",
                lineterm="",
            )
        )
        raise AssertionError(
            f"Snapshot {path.name} changed:\n{diff}\nRun with update=True to accept the new output."
        )
    return rendered
