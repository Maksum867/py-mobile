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

from typing import Any

__all__ = ["render_ascii", "render_png", "ascii_picture"]

_BAR_WIDTH = 16


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
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover - very old Pillow
        font = None
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

    if node_type == "Row":
        rows = _join_horizontal(
            [_node_lines(child, show_ids=show_ids) for child in children]
        )
    elif node_type in ("Column", "ScrollView", "Stack", "Container"):
        rows = _join_vertical(
            [_node_lines(child, show_ids=show_ids) for child in children]
        )
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

    return [f"<{node_type}>"]
