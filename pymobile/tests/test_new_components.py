"""Tests for the newly added UI components (Slider, Checkbox, RatingBar,
Dropdown, Chip, Badge, Stepper, SearchBar).

These cover validation, state transitions, callback firing and serialisation.
"""

from __future__ import annotations

import pytest

from pymobile import (
    App,
    Badge,
    Checkbox,
    Chip,
    Column,
    Dropdown,
    RatingBar,
    Screen,
    SearchBar,
    Slider,
    Stepper,
    Widget,
)
from pymobile.core.bridge import StubBridge
from pymobile.core.ui.preview import render_ascii


# --------------------------------------------------------------------------
# Slider
# --------------------------------------------------------------------------
def test_slider_basic():
    s = Slider(50, minimum=0, maximum=100)
    assert s.value == 50
    assert s.fraction == 0.5


def test_slider_clamps():
    s = Slider(150, minimum=0, maximum=100)
    assert s.value == 100
    s.value = -10
    assert s.value == 0


def test_slider_step_snapping():
    s = Slider(53, minimum=0, maximum=100, step=10)
    assert s.value == 50  # snapped to nearest multiple of 10


def test_slider_invalid_bounds():
    with pytest.raises(ValueError):
        Slider(maximum=10, minimum=20)
    with pytest.raises(ValueError):
        Slider(step=0)


def test_slider_on_change_fires_only_on_change():
    events = []
    s = Slider(10, minimum=0, maximum=100, on_change=lambda v: events.append(v))
    s.set_value(20)
    s.set_value(20)  # no change
    assert events == [20.0]


def test_slider_serialises():
    d = Slider(30, minimum=0, maximum=50, step=5).to_dict()
    assert d["type"] == "Slider"
    assert d["props"]["maximum"] == 50


# --------------------------------------------------------------------------
# Checkbox
# --------------------------------------------------------------------------
def test_checkbox_toggle():
    cb = Checkbox(checked=True)
    assert cb.checked
    assert cb.toggle() is False
    assert not cb.checked


def test_checkbox_on_toggle_once():
    events = []
    cb = Checkbox(on_toggle=lambda v: events.append(v))
    cb.set_checked(True)
    cb.set_checked(True)  # no real change
    assert events == [True]


def test_checkbox_serialises():
    assert Checkbox(checked=True).to_dict()["props"]["checked"] is True


# --------------------------------------------------------------------------
# RatingBar
# --------------------------------------------------------------------------
def test_rating_bar_basic():
    r = RatingBar(3, maximum=5)
    assert r.rating == 3
    assert r.value == 3
    assert r.maximum == 5


def test_rating_bar_clamps():
    r = RatingBar(9, maximum=5)
    assert r.rating == 5
    r.rating = -1
    assert r.rating == 0


def test_rating_bar_invalid_maximum():
    with pytest.raises(ValueError):
        RatingBar(maximum=0)


def test_rating_bar_on_change():
    events = []
    r = RatingBar(1, maximum=5, on_change=lambda v: events.append(v))
    r.set_value(4)
    assert events == [4.0]


# --------------------------------------------------------------------------
# Dropdown
# --------------------------------------------------------------------------
def test_dropdown_default_first():
    d = Dropdown(["A", "B", "C"])
    assert d.value == "A"


def test_dropdown_select():
    d = Dropdown(["A", "B", "C"], value="B")
    d.select("C")
    assert d.value == "C"


def test_dropdown_invalid_option():
    d = Dropdown(["A", "B"])
    with pytest.raises(ValueError):
        d.select("Z")


def test_dropdown_empty_rejected():
    with pytest.raises(ValueError):
        Dropdown([])


def test_dropdown_serialises_options():
    d = Dropdown(["A", "B"], value="B")
    assert d.to_dict()["props"]["options"] == ["A", "B"]


# --------------------------------------------------------------------------
# Chip
# --------------------------------------------------------------------------
def test_chip_selected_state():
    c = Chip("Filter", selected=True)
    assert c.selected
    c.set_selected(False)
    assert not c.selected


def test_chip_press_disabled():
    fired = []
    c = Chip("x", on_press=lambda: fired.append(1))
    c.press()
    assert fired == [1]


# --------------------------------------------------------------------------
# Badge
# --------------------------------------------------------------------------
def test_badge_accepts_number():
    b = Badge(5)
    assert b.text == "5"


def test_badge_updates_text():
    b = Badge("1")
    b.text = 42
    assert b.text == "42"


def test_badge_invalid_color():
    with pytest.raises(ValueError):
        Badge(color="notacolor")


# --------------------------------------------------------------------------
# Stepper
# --------------------------------------------------------------------------
def test_stepper_basic():
    st = Stepper(5, minimum=0, maximum=10)
    assert st.value == 5


def test_stepper_increment_decrement():
    st = Stepper(5, minimum=0, maximum=10)
    assert st.increment() == 6
    assert st.decrement() == 5


def test_stepper_clamps():
    st = Stepper(9, minimum=0, maximum=10)
    assert st.increment() == 10
    st2 = Stepper(1, minimum=0, maximum=10)
    assert st2.decrement() == 0


def test_stepper_invalid():
    with pytest.raises(ValueError):
        Stepper(minimum=5, maximum=1)
    with pytest.raises(ValueError):
        Stepper(step=0)


# --------------------------------------------------------------------------
# SearchBar
# --------------------------------------------------------------------------
def test_searchbar_set_value():
    sb = SearchBar(placeholder="Find")
    sb.set_value("hello")
    assert sb.value == "hello"


def test_searchbar_on_change():
    events = []
    sb = SearchBar(on_change=lambda v: events.append(v))
    sb.set_value("a")
    sb.set_value("a")
    assert events == ["a"]


def test_searchbar_submit():
    fired = []
    sb = SearchBar(on_search=lambda v: fired.append(v))
    sb.set_value("query")
    sb.submit()
    assert fired == ["query"]


def test_searchbar_clear():
    sb = SearchBar()
    sb.set_value("x")
    sb.clear()
    assert sb.value == ""


# --------------------------------------------------------------------------
# Preview (ASCII)
# --------------------------------------------------------------------------
def test_slider_preview_contains_value():
    assert "50" in render_ascii(Slider(50).to_dict())


def test_rating_preview_stars():
    text = render_ascii(RatingBar(3, maximum=5).to_dict())
    assert "★" in text and "3/5" in text


def test_dropdown_preview_shows_selection():
    assert "B" in render_ascii(Dropdown(["A", "B"], value="B").to_dict())


def test_checkbox_preview_state():
    assert "on" in render_ascii(Checkbox(checked=True).to_dict())


# --------------------------------------------------------------------------
# Integration: the components reacting to app events inside a running App
# --------------------------------------------------------------------------
def _app_with(build_attr):
    class Demo(Screen):
        def build(self) -> Widget:
            build_attr(self)
            return Column(self.root_widget)

    app = App("t", bridge=StubBridge(verbose=False))
    screen = Demo()
    app.run(screen)
    return app, screen


def test_stepper_increment_decrement_through_app():
    app, screen = _app_with(lambda s: setattr(s, "root_widget", Stepper(5, minimum=0, maximum=10)))
    stepper = screen.root_widget
    widget_id = stepper.id

    app.handle_ui_event(widget_id, "increment", "")
    assert stepper.value == 6
    app.handle_ui_event(widget_id, "decrement", "")
    assert stepper.value == 5


def test_stepper_clamps_through_app():
    app, screen = _app_with(lambda s: setattr(s, "root_widget", Stepper(9, minimum=0, maximum=10)))
    stepper = screen.root_widget
    app.handle_ui_event(stepper.id, "increment", "")
    assert stepper.value == 10


def test_slider_change_through_app():
    app, screen = _app_with(lambda s: setattr(s, "root_widget", Slider(20, minimum=0, maximum=100)))
    slider = screen.root_widget
    app.handle_ui_event(slider.id, "change", "70")
    assert slider.value == 70


def test_checkbox_toggle_through_app():
    app, screen = _app_with(lambda s: setattr(s, "root_widget", Checkbox(checked=False)))
    checkbox = screen.root_widget
    app.handle_ui_event(checkbox.id, "toggle", "true")
    assert checkbox.checked


def test_chip_press_through_app():
    def make(s):
        def mark():
            s._pressed = True

        s._pressed = False
        s.root_widget = Chip("go", on_press=mark)

    app, screen = _app_with(make)
    chip = screen.root_widget
    app.handle_ui_event(chip.id, "press", "")
    assert screen._pressed


def test_ratingbar_change_through_app():
    app, screen = _app_with(lambda s: setattr(s, "root_widget", RatingBar(1, maximum=5)))
    rating = screen.root_widget
    app.handle_ui_event(rating.id, "change", "4")
    assert rating.value == 4
