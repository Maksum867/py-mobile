"""Regression tests for public API contracts fixed after the 0.6.0 audit."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from pymobile import Dropdown, RatingBar, SegmentedButtons, Validator
from pymobile.core.api.storage import Storage
from pymobile.core.jobs import JobHandle, JobManager
from pymobile.core.net.http import HttpClient, HttpFuture, Response
from pymobile.core.ui.components import Image


def test_documented_validator_mapping_dsl() -> None:
    validator = Validator(
        {
            "email": ["required", "email"],
            "age": ["optional", "integer", {"between": [1, 120]}],
        }
    )
    assert validator.validate({"email": "a@example.com", "age": "42"}) == {}
    assert validator.validate({"email": "invalid", "age": 130}) == {
        "email": "must be a valid email address",
        "age": "must be between 1.0 and 120.0",
    }


def test_documented_selection_callbacks_are_compatibility_aliases() -> None:
    changed: list[str] = []
    Dropdown(["one", "two"], on_change=changed.append).set_value("two")
    SegmentedButtons(["light", "dark"], on_change=changed.append).set_value("dark")
    assert changed == ["two", "dark"]


def test_rating_value_alias_and_conflicting_aliases() -> None:
    assert RatingBar(value=3).value == 3
    with pytest.raises(ValueError, match="either rating or value"):
        RatingBar(2, value=3)


def test_image_accepts_local_file_url(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"not decoded by the widget")
    assert Image(image.as_uri()).source == image.as_uri()


def test_storage_rejects_non_string_keys(tmp_path: Path) -> None:
    store = Storage(tmp_path / "store.json")
    with pytest.raises(ValueError, match="non-empty string"):
        store.set(1, "bad")  # type: ignore[arg-type]


def test_completed_job_callback_can_cancel_without_deadlock() -> None:
    handle = JobHandle("job", lambda: None)
    handle._complete("done", None)
    handle.then(lambda _: handle.cancel())
    assert handle.cancelled


def test_completed_http_callback_can_cancel_without_deadlock() -> None:
    future = HttpFuture(HttpClient(), "GET", "https://example.test", {})
    future._complete(Response(200, {}, b"ok", "https://example.test"), None)
    future.then(lambda _: future.cancel())
    assert future.cancelled


def test_job_wait_times_out() -> None:
    handle = JobHandle("slow", lambda: None)
    with pytest.raises(TimeoutError, match="did not complete"):
        handle.wait(timeout=0.01)


def test_failed_repeating_job_completes_handle_with_error() -> None:
    manager = JobManager()

    def fail() -> None:
        raise RuntimeError("boom")

    handle = manager.every(1, fail)
    for _ in range(50):
        if handle.done:
            break
        time.sleep(0.01)
    assert handle.done
    with pytest.raises(RuntimeError, match="boom"):
        handle.wait()
    manager.shutdown()
