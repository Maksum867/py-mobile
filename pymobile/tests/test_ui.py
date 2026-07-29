"""Tests for widgets, layouts, styling and navigation."""

from __future__ import annotations

import pytest

from pymobile import (
    App,
    Button,
    Color,
    Column,
    EdgeInsets,
    Image,
    Label,
    ProgressBar,
    Row,
    Screen,
    ScrollView,
    Spacer,
    Style,
    Switch,
    TextInput,
    Widget,
)
from pymobile.core.ui.screen import Navigator
from pymobile.errors import PyMobileError


class TestWidgets:
    def test_label_serialises_text(self) -> None:
        label = Label("hi", id="greeting")
        node = label.to_dict()
        assert node["type"] == "Label"
        assert node["id"] == "greeting"
        assert node["props"]["text"] == "hi"

    def test_ids_are_unique(self) -> None:
        assert Label("a").id != Label("b").id

    def test_button_press_invokes_callback(self) -> None:
        calls: list[int] = []
        button = Button("go", on_press=lambda: calls.append(1))
        button.press()
        assert calls == [1]

    def test_disabled_button_ignores_press(self) -> None:
        calls: list[int] = []
        button = Button("go", on_press=lambda: calls.append(1), enabled=False)
        button.press()
        assert calls == []

    def test_button_set_text_updates_label(self) -> None:
        button = Button("Start")
        button.set_text("Pause")
        assert button.text == "Pause"
        assert button.props()["text"] == "Pause"

    def test_text_input_notifies_on_change(self) -> None:
        seen: list[str] = []
        field = TextInput(on_change=seen.append)
        field.set_value("abc")
        field.set_value("abc")  # unchanged -> no callback
        assert seen == ["abc"]

    def test_text_input_respects_max_length(self) -> None:
        field = TextInput(max_length=3)
        field.set_value("abcdef")
        assert field.value == "abc"

    def test_text_input_rejects_bad_max_length(self) -> None:
        with pytest.raises(ValueError, match="max_length"):
            TextInput(max_length=0)

    def test_switch_toggle(self) -> None:
        states: list[bool] = []
        switch = Switch(on_toggle=states.append)
        assert switch.toggle() is True
        switch.set_checked(True)  # no change -> no callback
        assert states == [True]

    def test_progress_bar_clamps(self) -> None:
        bar = ProgressBar(150, maximum=100)
        assert bar.value == 100
        bar.set_value(-5)
        assert bar.value == 0
        assert bar.fraction == 0

    def test_progress_bar_rejects_bad_maximum(self) -> None:
        with pytest.raises(ValueError, match="maximum"):
            ProgressBar(maximum=0)

    def test_image_validates_input(self) -> None:
        with pytest.raises(ValueError, match="source"):
            Image("")
        with pytest.raises(ValueError, match="fit"):
            Image("a.png", fit="stretch")

    def test_spacer_rejects_negative_size(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            Spacer(-1)


class TestContainers:
    def test_children_are_attached(self) -> None:
        child = Label("x")
        column = Column(child)
        assert child.parent is column
        assert list(column) == [child]
        assert len(column) == 1

    def test_double_parent_is_rejected(self) -> None:
        child = Label("x")
        Column(child)
        with pytest.raises(ValueError, match="already has a parent"):
            Row(child)

    def test_self_nesting_is_rejected(self) -> None:
        column = Column()
        with pytest.raises(ValueError, match="itself"):
            column.add(column)

    def test_remove_and_clear(self) -> None:
        child = Label("x")
        column = Column(child)
        column.remove(child)
        assert child.parent is None
        assert len(column) == 0
        column.clear()  # no-op, must not raise

    def test_walk_and_find(self) -> None:
        target = Label("deep", id="deep")
        tree = Column(Row(ScrollView(target)))
        assert tree.find("deep") is target
        assert tree.find("nope") is None
        assert len(list(tree.walk())) == 4

    def test_layout_props_serialised(self) -> None:
        node = Column(Label("a"), spacing=8).to_dict()
        assert node["props"]["spacing"] == 8
        assert len(node["children"]) == 1

    def test_negative_spacing_rejected(self) -> None:
        with pytest.raises(ValueError, match="spacing"):
            Column(spacing=-1)


class TestStyle:
    def test_only_set_fields_serialise(self) -> None:
        assert Style().to_dict() == {}
        assert Style(font_size=14, bold=True).to_dict() == {"font_size": 14, "bold": True}

    def test_insets_serialise_as_list(self) -> None:
        style = Style(padding=EdgeInsets.all(4))
        assert style.to_dict()["padding"] == [4, 4, 4, 4]

    def test_empty_insets_are_dropped(self) -> None:
        assert Style(padding=EdgeInsets()).to_dict() == {}

    def test_symmetric_insets(self) -> None:
        insets = EdgeInsets.symmetric(horizontal=8, vertical=2)
        assert insets.to_list() == [8, 2, 8, 2]

    def test_invalid_color_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid color"):
            Style(color="red")

    def test_named_colors_are_valid(self) -> None:
        assert Style(background=Color.PRIMARY).to_dict()["background"] == Color.PRIMARY

    def test_merge_returns_copy(self) -> None:
        base = Style(font_size=12)
        merged = base.merge(font_size=20)
        assert base.font_size == 12
        assert merged.font_size == 20

    def test_invalid_font_size(self) -> None:
        with pytest.raises(ValueError, match="font_size"):
            Style(font_size=0)


class _Home(Screen):
    title = "Home"

    def build(self) -> Widget:
        return Column(Label("home"))


class _Details(Screen):
    title = "Details"

    def __init__(self) -> None:
        super().__init__()
        self.log: list[str] = []

    def build(self) -> Widget:
        return Column(Label("details"))

    def on_mount(self) -> None:
        self.log.append("mount")

    def on_show(self) -> None:
        self.log.append("show")

    def on_hide(self) -> None:
        self.log.append("hide")

    def on_unmount(self) -> None:
        self.log.append("unmount")


class TestScreen:
    def test_build_is_required(self) -> None:
        with pytest.raises(NotImplementedError):
            Screen().root

    def test_root_is_cached(self) -> None:
        screen = _Home()
        assert screen.root is screen.root

    def test_serialisation_includes_title(self) -> None:
        assert _Home().to_dict()["screen"] == "Home"

    def test_find_delegates_to_root(self) -> None:
        screen = _Home()
        assert screen.find(screen.root.children[0].id) is not None


class TestNavigator:
    def test_push_and_pop(self) -> None:
        nav = Navigator()
        home, details = _Home(), _Details()
        nav.push(home)
        nav.push(details)
        assert nav.depth == 2
        assert nav.current is details
        popped = nav.pop()
        assert popped is details
        assert nav.stack[-1] is home

    def test_cannot_pop_last_screen(self) -> None:
        nav = Navigator()
        nav.push(_Home())
        assert nav.pop() is None
        assert nav.depth == 1

    def test_lifecycle_order(self) -> None:
        nav = Navigator()
        nav.push(_Home())
        details = _Details()
        nav.push(details)
        nav.pop()
        assert details.log == ["mount", "show", "hide", "unmount"]

    def test_duplicate_push_rejected(self) -> None:
        nav = Navigator()
        home = _Home()
        nav.push(home)
        with pytest.raises(PyMobileError, match="already on the stack"):
            nav.push(home)

    def test_replace_swaps_top(self) -> None:
        nav = Navigator()
        nav.push(_Home())
        details = _Details()
        nav.replace(details)
        assert nav.depth == 1
        assert nav.current is details

    def test_reset_clears_stack(self) -> None:
        nav = Navigator()
        nav.push(_Home())
        nav.push(_Details())
        nav.reset(_Home())
        assert nav.depth == 1

    def test_stack_is_immutable_view(self) -> None:
        nav = Navigator()
        nav.push(_Home())
        assert isinstance(nav.stack, tuple)


class TestRefresh:
    def test_refresh_rebuilds_and_renders(self, bridge) -> None:  # type: ignore[no-untyped-def]
        app = App("Demo", bridge=bridge)
        screen = _Home()
        app.run(screen)
        first = screen.root
        screen.refresh()
        assert screen.root is not first
        assert len(bridge.calls_named("render")) >= 2
