"""Tests for the new non-UI features: async HTTP, app.storage, dark theme."""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from pymobile import App, HttpClient, Storage, Theme, default_storage_path
from pymobile.core.bridge import StubBridge
from pymobile.core.net import HttpFuture
from pymobile.errors import NetworkError


# --------------------------------------------------------------------------
# Async HTTP
# --------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"async": true}')

    def do_POST(self):
        self.send_response(201)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_PUT(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_DELETE(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def http_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_async_get_returns_future(http_server):
    client = HttpClient(base_url=http_server, retries=0, backoff=0)
    future = client.get_async("/")
    assert isinstance(future, HttpFuture)
    response = future.get(timeout=5)
    assert response.ok
    assert response.json() == {"async": True}


def test_async_blocks_ui_thread(http_server):
    """The sync verb returns immediately; the async verb runs off-thread."""
    client = HttpClient(base_url=http_server, retries=0, backoff=0)
    future = client.get_async("/")
    assert not future.done  # may still be in flight
    assert future.get(timeout=5).status == 200


def test_async_callback(http_server):
    client = HttpClient(base_url=http_server, retries=0, backoff=0)
    done = []
    future = client.get_async("/")
    future.then(lambda resp: done.append(resp.status))
    assert future.get(timeout=5).status == 200
    # give the callback thread a moment to fire
    for _ in range(100):
        if done:
            break
        time.sleep(0.01)
    assert done == [200]


def test_async_cancel_suppresses_callback(http_server):
    client = HttpClient(base_url=http_server, retries=0, backoff=0)
    done = []
    future = client.get_async("/")
    future.cancel()
    future.then(lambda resp: done.append(resp.status))
    assert future.cancelled
    future.get(timeout=5)  # the request still completes
    time.sleep(0.05)
    assert done == []


def test_async_all_verbs(http_server):
    client = HttpClient(base_url=http_server, retries=0, backoff=0)
    assert client.post_async("/").get(timeout=5).status == 201
    assert client.put_async("/").get(timeout=5).status == 200
    assert client.delete_async("/").get(timeout=5).status == 200


def test_async_bad_url_fails_via_get():
    client = HttpClient()
    future = client.get_async("http://127.0.0.1:1/none")
    with pytest.raises(NetworkError):
        future.get(timeout=5)


# --------------------------------------------------------------------------
# app.storage
# --------------------------------------------------------------------------
def test_storage_set_get_delete(tmp_path):
    s = Storage(tmp_path / "s.json")
    s.set("name", "Oksana")
    assert s.get("name") == "Oksana"
    assert s["name"] == "Oksana"
    assert s.delete("name") is True
    assert s.delete("name") is False
    assert s.get("name") is None
    assert s.get("missing", 42) == 42


def test_storage_persists_across_instances(tmp_path):
    path = tmp_path / "s.json"
    Storage(path).set("taps", 5)
    s2 = Storage(path)
    assert s2["taps"] == 5
    assert s2.contains("taps")


def test_storage_mapping_api(tmp_path):
    s = Storage(tmp_path / "s.json")
    s["a"] = 1
    s["b"] = 2
    assert len(s) == 2
    assert set(s.keys()) == {"a", "b"}
    assert dict(s.items()) == {"a": 1, "b": 2}
    del s["a"]
    assert "a" not in s
    with pytest.raises(KeyError):
        del s["nope"]


def test_storage_clear(tmp_path):
    s = Storage(tmp_path / "s.json")
    s["a"] = 1
    s.clear()
    assert len(s) == 0
    assert not s.contains("a")


def test_storage_empty_key_rejected(tmp_path):
    s = Storage(tmp_path / "s.json")
    with pytest.raises(ValueError):
        s.set("", 1)


def test_storage_corrupt_file_starts_fresh(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("not json{{{", encoding="utf-8")
    s = Storage(path)
    assert s.get("a") is None
    s["ok"] = True
    assert Storage(path)["ok"] is True  # rewrite fixed the file


def test_storage_path_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PYMOBILE_STORAGE_DIR", str(tmp_path))
    assert default_storage_path() == tmp_path / "pymobile_store.json"


def test_app_exposes_storage(tmp_path):
    path = tmp_path / "app.json"
    app = App("t", bridge=StubBridge(verbose=False), storage_path=str(path))
    app.storage["visited"] = 1
    assert App("t", bridge=StubBridge(verbose=False), storage_path=str(path)).storage["visited"] == 1


# --------------------------------------------------------------------------
# Dark theme
# --------------------------------------------------------------------------
def test_theme_defaults_to_light():
    assert App().theme.name == "light"
    assert App().theme.is_dark is False


def test_theme_dark():
    app = App(theme="dark")
    assert app.theme.is_dark
    assert app.theme.color("BACKGROUND") == "#121212"
    assert app.theme["TEXT"] == "#EEEEEE"


def test_theme_object_accepted():
    app = App(theme=Theme.dark())
    assert app.theme.name == "dark"


def test_theme_partial_custom():
    t = Theme("custom", {"BACKGROUND": "#000000", "TEXT": "#FFFFFF"})
    assert t.color("BACKGROUND") == "#000000"
    assert t.color("PRIMARY") == "#3F51B5"  # falls back to built-in


def test_theme_unknown_color_raises():
    with pytest.raises(ValueError):
        Theme.dark().color("NOTACOLOR")


def test_theme_invalid_hex_raises():
    with pytest.raises(ValueError):
        Theme("bad", {"PRIMARY": "nothex"})


def test_theme_invalid_name_raises():
    with pytest.raises(ValueError):
        App(theme="neon")


def test_set_theme_redraws_screen():
    from pymobile import Column, Label, Screen, Widget

    class Demo(Screen):
        def build(self) -> Widget:
            return Column(Label("hi"))

    app = App("t", bridge=StubBridge(verbose=False))
    app.run(Demo())
    app.set_theme("dark")
    assert app.theme.is_dark
    # theme change refreshed the screen without crashing
    assert app.screen is not None


def test_light_preset_matches_builtin():
    assert Theme.light().color("PRIMARY") == "#3F51B5"
