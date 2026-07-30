# PyMobile Guide

A practical guide, from your first app to a signed APK. Every code example here
has been executed and verified.

---

## Contents

1. [Install](#1-install)
2. [Your first app in three minutes](#2-your-first-app-in-three-minutes)
3. [The mental model](#3-the-mental-model)
4. [UI components](#4-ui-components)
5. [Layout and styling](#5-layout-and-styling)
6. [Screens and navigation](#6-screens-and-navigation)
7. [Updating the interface](#7-updating-the-interface)
8. [Android APIs](#8-android-apis)
9. [HTTP requests](#9-http-requests)
10. [Events](#10-events)
11. [Configuration](#11-configuration)
12. [Building an APK](#12-building-an-apk)
13. [Application icon](#13-application-icon)
14. [Testing your app](#14-testing-your-app)
15. [Error handling](#15-error-handling)
16. [Extending the framework](#16-extending-the-framework)
17. [CLI reference](#17-cli-reference)
18. [FAQ](#18-faq)

---

## 1. Install

```bash
pip install pymobile-framework
```

The distribution is named `py-mobile` because `pymobile` on PyPI belongs to an
unrelated project. The import name and the CLI command remain `pymobile`.

Then, once per machine:

```bash
pymobile setup-sdk          # ~800 MB: JDK 17 + Android SDK
pymobile doctor             # verify the environment
```

The NDK is not required — a prebuilt native bridge ships with the package.

**If the `pymobile` command is not found** (common on Windows when pip's
scripts directory is not on `PATH`), use the module form, which always works:

```bash
python -m pymobile build --native
```

---

## 2. Your first app in three minutes

```bash
pymobile init myapp --name "My App" -p com.example.myapp
cd myapp
pymobile run                # preview on your machine
pymobile build --native     # → build/my-app-0.1.0.apk
```

`init` creates:

```
myapp/
├── main.py         # entry point
├── pymobile.toml   # configuration
├── README.md
├── .gitignore
└── assets/         # your resources
```

A complete minimal app:

```python
from pymobile import App, Column, Label, Screen, Widget


class Home(Screen):
    title = "Home"

    def build(self) -> Widget:
        return Column(Label("Hello, Android!"))


App("My App").run(Home())
```

---

## 3. The mental model

Three ideas make everything else predictable.

**1. Widgets are a description, not native views.** `Label("Hello")` draws
nothing; it is a node that serialises into a plain tree (`to_dict()`). A Java
renderer turns that tree into real Android views.

**2. Everything platform-specific goes through a `Bridge`.**

```
Your code → App → Bridge ─┬─→ AndroidBridge (on device, through JNI)
                          └─→ StubBridge    (on desktop: records calls)
```

**3. Hence the practical payoff:** your app runs and is fully testable on a
desktop, with no emulator. `pymobile run` works exactly this way. You never
write `if android:` — the framework picks the implementation.

```python
app = App("Demo")
print(app.platform)      # 'desktop' or 'android'
print(app.bridge.name)   # 'stub' or 'android'
```

---

## 4. UI components

Eight components. Each accepts `id`, `style`, `visible` and `enabled`.

### Label — text

```python
title = Label("Heading", style=Style(font_size=24, bold=True))
title.set_text("New text")
```

### Button

```python
Button("Save", on_press=self.save)
Button("Disabled", on_press=self.save, enabled=False)   # taps are ignored
```

### TextInput

```python
TextInput(
    placeholder="Your name",
    max_length=50,              # extra characters are trimmed
    on_change=lambda value: print(value),
)
TextInput(password=True)        # masked input
TextInput(multiline=True)       # multi-line field
```

`on_change` fires only on a **real** change: calling `set_value()` with the same
text does not trigger the callback.

### Switch

```python
switch = Switch(checked=True, on_toggle=lambda state: print(state))
switch.toggle()          # returns the new state
switch.set_checked(False)
```

### ProgressBar

```python
bar = ProgressBar(40, maximum=100)
bar.set_value(150)       # clamped to maximum
print(bar.fraction)      # 1.0
ProgressBar(indeterminate=True)
```

### Image, Spacer

```python
Image("assets/logo.png", fit="cover")   # contain | cover | fill | none
Spacer(16)
```

---

## 5. Layout and styling

### Containers

```python
Column(a, b, c, spacing=12)               # vertical
Row(a, b, spacing=8, align=Align.CENTER)  # horizontal
Grid(a, b, c, d, columns=2, spacing=12)   # equal-width cells
ScrollView(long_content)                  # scrollable
Stack(background, foreground)             # layered, last on top
SafeArea(content)                         # clear of the notch/status bar
```

They nest freely:

```python
SafeArea(Column(
    Label("Heading"),
    Divider(),
    Grid(card_a, card_b, card_c, card_d, columns=2, spacing=12),
    Row(Expanded(Button("Yes")), Expanded(Button("No")), spacing=8),
    ScrollView(Column(*[Label(f"Row {i}") for i in range(50)])),
    spacing=12,
))
```

`Grid` keeps columns the same width whatever the cell contents — the thing a
`Row` of `weight=1` children cannot promise. `Expanded(child, flex=2)` claims a
share of the leftover space, and `Divider()` draws a hairline between sections.

Alignment: `align` runs along the container's axis, `cross_align` across it
(`START`, `CENTER`, `END`, `SPACE_BETWEEN`, plus `STRETCH` for `cross_align`).

### Style

```python
Style(
    font_size=18, bold=True, color=Color.PRIMARY,
    background=Color.SURFACE,
    padding=EdgeInsets.all(16),
    margin=EdgeInsets.symmetric(horizontal=8, vertical=4),
    corner_radius=8, elevation=2,
    min_width=120, max_width=200,     # constraints
    aspect_ratio=16 / 9,
)
```

Built-in colours: `PRIMARY`, `ACCENT`, `BACKGROUND`, `SURFACE`, `TEXT`,
`TEXT_MUTED`, `SUCCESS`, `WARNING`, `ERROR`, `TRANSPARENT`.

Styles are immutable, so a base style is safe to share:

```python
BASE = Style(font_size=16, color=Color.TEXT)
Label("Normal", style=BASE)
Label("Error", style=BASE.merge(color=Color.ERROR, bold=True))
```

Invalid values are rejected immediately: `Style(color="red")` raises
`ValueError` — use `#RGB`, `#RRGGBB` or `#AARRGGBB`.

---

## 6. Screens and navigation

A screen builds a tree in `build()` and has lifecycle hooks.

```python
class Settings(Screen):
    title = "Settings"

    def build(self) -> Widget:
        return Column(
            Label("Second screen"),
            Button("Back", on_press=lambda: self.app.pop()),
        )

    def on_mount(self):   ...   # once, after build(), when pushed onto the stack
    def on_show(self):    ...   # every time it becomes visible
    def on_hide(self):    ...   # when another screen covers it
    def on_unmount(self): ...   # once, when popped
```

### Navigation is a stack

```python
app.push(Settings())   # forward: on_hide(current) → build() → on_mount → on_show
app.pop()              # back:    on_hide → on_unmount → on_show(previous)

app.navigator.replace(Other())  # swap the top screen
app.navigator.reset(Home())     # clear the stack and start over
app.navigator.depth             # stack depth
app.screen                      # current screen
```

The root screen is never popped: `pop()` returns `None` instead of breaking the
app. The hardware back button is wired up automatically.

**Note.** Do not push the same screen object twice — that raises
`PyMobileError`. Create a new instance: `app.push(Settings())`.

---

## 7. Updating the interface

Change a widget; the screen redraws itself.

```python
class Home(Screen):
    def __init__(self):
        super().__init__()
        self.taps = 0

    def build(self) -> Widget:
        self.counter = Label("Taps: 0")      # id becomes "counter"
        return Column(self.counter, Button("Tap", on_press=self.on_tap))

    def on_tap(self) -> None:
        self.taps += 1
        self.counter.text = f"Taps: {self.taps}"     # done — no render() call
```

`widget.text = "…"` and `widget.set_text("…")` are the same thing. It works for
`text`, `value`, `checked`, `visible` and `enabled`.

Redraws are coalesced, so a handler that changes six widgets still draws one
frame, and setting a value that has not changed draws nothing.

- **`self.refresh()`** — rebuild through `build()`. Needed when the
  **structure** changes (an element appears or disappears).
- **`app.render()`** — force a frame right now. Rarely needed.
- **`app.batch()`** — group a loop of updates into one frame.

```python
def on_load(self) -> None:
    self.items = fetch_items()
    self.refresh()          # the number of rows changed

with self.app.batch():
    for label, value in zip(self.labels, values):
        label.text = value
```

Find a widget by `id` without keeping a reference. Widgets assigned to `self`
in `build()` take the attribute name as their id:

```python
self.counter = Label("0")      # id == "counter"
...
self.find("counter").text = "5"
```

### Events that clean up after themselves

```python
class TimerScreen(Screen):
    def on_mount(self) -> None:
        self.on("pomodoro:tick", self.on_tick)   # cancelled on unmount
```

Use `self.on()` rather than `self.app.on()`: the handler of a popped screen
would otherwise keep firing and keep the screen in memory.

---

## 8. Android APIs

### Notifications

```python
app.notify("Done", "File saved")              # returns an id
app.notify("Downloading", ongoing=True)        # cannot be swiped away
app.notifications.cancel(notification_id)
```

The channel is created once automatically. Android 13+ requires the
`POST_NOTIFICATIONS` permission — the compiler warns if it is missing.

### Vibration

```python
app.vibrate(100)                              # one shot, milliseconds
app.vibration.preset("success")               # built-in patterns
app.vibration.pattern([0, 100, 50, 100])      # [wait, buzz, wait, buzz]
app.vibration.cancel()
```

Presets: `tick`, `click`, `double`, `success`, `error`, `heartbeat`.

Pulses shorter than about 50 ms are not felt on most hardware, so short values
are stretched automatically.

### Permissions

```python
from pymobile import Permission

app.permissions.has(Permission.CAMERA)              # check
app.permissions.request(Permission.CAMERA)          # {'android.permission.CAMERA': True}
app.require_permissions(Permission.CAMERA)          # raises if declined
app.permissions.missing([Permission.CAMERA, "VIBRATE"])
```

Three spellings are accepted: `"CAMERA"`, `"android.permission.CAMERA"` and
`Permission.CAMERA`. Already-granted permissions are not requested again.

**A permission must be declared twice:** in `pymobile.toml` (so it reaches the
manifest) and requested at runtime. Android silently denies an undeclared
permission — no dialog appears at all. The compiler warns about this case.

---

## 9. HTTP requests

A client built on the standard library: no dependencies, smaller APK.

```python
from pymobile import HttpClient

client = HttpClient(
    base_url="https://api.example.com",
    headers={"Authorization": "Bearer ..."},
    timeout=10,
    retries=2,        # exponential backoff
)

client.get("/items", params={"page": 2})
client.post("/items", json={"name": "Widget"})
client.put("/items/1", json={"name": "Updated"})
client.delete("/items/1")
```

Working with the response:

```python
response = client.get("/items")
response.status      # 200
response.ok          # True for 2xx
response.json()      # parsed JSON
response.text        # text
response.elapsed     # seconds
```

**Important:** 4xx and 5xx statuses do **not** raise — they are valid responses.
An exception is raised only on transport failure.

```python
response = client.get("/missing")
if not response.ok:
    print("not found:", response.status)   # 404

response.raise_for_status()   # this raises NetworkError for 4xx/5xx
```

Retries cover connection failures and 408/425/429/5xx.

HTTPS works out of the box: a root certificate bundle is packaged into the APK,
because Android has no cert file where OpenSSL looks for one.

`pymobile.toml` must list `android.permission.INTERNET`, otherwise requests fail
on device (the compiler warns).

---

## 10. Events

The event bus decouples UI from logic.

```python
app.on("app:start",     lambda e: print("started"))
app.on("screen:change", lambda e: print("screen:", e.source))
app.on("app:render",    lambda e: ...)
app.on("app:stop",      lambda e: ...)

# custom events
app.events.emit("cart:updated", source="CartScreen", count=3)
app.on("cart:updated", lambda e: print(e.get("count")))

subscription = app.on("x", handler)
subscription.cancel()
```

An exception in one handler is logged but never breaks the others.

---

## 11. Configuration

Everything lives in `pymobile.toml` (or a `[tool.pymobile]` table in
`pyproject.toml`).

```toml
[app]
name = "My App"
package = "com.example.myapp"   # reverse-DNS, lowercase only
version = "1.0.0"
version_code = 1                # integer, must increase for each Play release

entrypoint = "main.py"
source_dir = "."

min_sdk = 21                    # Android 5.0
target_sdk = 34
orientation = "portrait"        # portrait | landscape | sensor | user

# Every permission requested at runtime must appear here.
permissions = [
    "android.permission.INTERNET",
    "android.permission.VIBRATE",
    "android.permission.POST_NOTIFICATIONS",
]

icon = "assets/icon.png"        # optional

abis = ["arm64-v8a"]
output_dir = "build"
optimize = true                 # package bytecode instead of sources
strip_debug = true              # -OO: no docstrings or asserts
exclude = ["tests/**", "**/__pycache__/**"]
```

Inspect the resolved configuration:

```bash
pymobile info
pymobile info --json    # for scripts
```

Problems are caught **before** the build starts and always carry a hint:

```
✗ Invalid package name 'Bad_Package'
  hint: Use reverse-DNS with lowercase segments, e.g. com.example.myapp
```

---

## 12. Building an APK

```bash
pymobile build --native                  # incremental
pymobile build --native --clean          # full rebuild
pymobile build --native --icon a/i.png   # custom icon
pymobile build --native --output dist    # different directory
pymobile build --native -v               # per-stage timings
```

> `pymobile build` **without** `--native` produces a structural package for
> quick checks only — it does not install on a device.

Twelve independent stages:

```
validate → collect → compile → icons → toolchain → runtime
        → jni → dex → resources → assets → sign → verify
```

A second build with no changes finishes instantly:

```
✓ up to date: my-app-1.0.0.apk (16.6 MB)
```

The cache covers every input: sources, config and icon.

**Inside the APK:**

```
AndroidManifest.xml            # generated from the config
classes.dex                    # launcher activity and renderer
resources.arsc                 # compiled resources
lib/arm64-v8a/*.so             # CPython and the JNI bridge
assets/app/                    # your code
assets/python/                 # standard library + CA bundle
res/mipmap-*/icon.png          # icons, five densities
META-INF/                      # signature (v1+v2+v3)
```

Builds are reproducible: identical inputs give a byte-identical APK. The file is
written to a temporary path and moved into place, so an interrupted build never
leaves a corrupt artifact.

---

## 13. Application icon

```toml
icon = "assets/icon.png"
```

or, per build: `pymobile build --native --icon assets/icon.png`

Requirements: a square PNG/JPG/WebP, ideally 512×512. It is resized into five
densities: mdpi 48, hdpi 72, xhdpi 96, xxhdpi 144, xxxhdpi 192 px.

**With no icon configured**, the bundled default Android icon is used, so a
build never fails because an asset is missing.

Errors are explicit:

```
✗ Icon not found: /project/assets/logo.png
  hint: Check the `icon` path in pymobile.toml, or remove it to use the default.
```

---

## 14. Testing your app

`StubBridge` records every platform call, so no emulator is needed.

```python
from pymobile import App, Button, Column, Label, Screen, Widget
from pymobile.core.bridge import StubBridge


class Home(Screen):
    def build(self) -> Widget:
        return Column(Label("hi"), Button("Notify", on_press=self.notify, id="btn"))

    def notify(self) -> None:
        self.app.notify("Hello", "body")
        self.app.vibrate(50)


def test_button_posts_notification():
    bridge = StubBridge(verbose=False)
    app = App("Test", bridge=bridge)
    app.run(Home())

    app.screen.find("btn").press()

    assert bridge.calls_named("notify")
    spec = list(bridge.notifications.values())[0]
    assert spec.title == "Hello"
    assert bridge.calls_named("vibrate")[0].kwargs["milliseconds"] == 50


def test_permission_denied_path():
    denying = StubBridge(grant_permissions=False, verbose=False)
    app = App("Test", bridge=denying)
    assert app.permissions.request("CAMERA") == {"android.permission.CAMERA": False}
```

Useful members: `calls`, `calls_named("notify")`, `notifications`, `granted`,
`reset()`, and the `grant_permissions=False` constructor flag.

---

## 15. Error handling

Every exception derives from `PyMobileError` and carries `message` and `hint`.

```python
from pymobile.errors import PyMobileError, NetworkError, ConfigError

try:
    response = client.get("/items")
except NetworkError as error:
    print(error.message)   # what happened
    print(error.hint)      # how to fix it
except PyMobileError as error:
    ...                    # catch anything from the framework
```

| Exception | Raised when |
| --- | --- |
| `ConfigError` | `pymobile.toml` is missing or invalid |
| `NetworkError` | request failed, host unreachable, invalid JSON |
| `PermissionError_` | the user declined a permission |
| `ResourceError` | an icon or template could not be read |
| `BridgeError` | a call into Android failed |
| `PlatformError` | the feature is unavailable on this platform |

The CLI prints only the message and the hint. For a full traceback, add `-v`.

On device, all Python output goes to logcat:

```bash
adb logcat -s pymobile pymobile.stdout pymobile.stderr
```

---

## 16. Extending the framework

The architecture is built for additions that do not touch existing code.

**A new widget:**

```python
from pymobile.core.ui.widget import Widget

class Slider(Widget):
    type_name = "Slider"
    __slots__ = ("value", "minimum", "maximum")

    def __init__(self, value=0.0, *, minimum=0.0, maximum=100.0, **kwargs):
        super().__init__(**kwargs)
        self.value, self.minimum, self.maximum = value, minimum, maximum

    def props(self):
        return {**super().props(), "value": self.value,
                "minimum": self.minimum, "maximum": self.maximum}
```

Then add a `case "Slider"` branch to `ViewBuilder.java`.

**A new Android API:** add a method to `Bridge`, implement it in
`AndroidBridge` and `StubBridge`, and wrap it in a small class under
`core/api/`.

**A new build stage:** write a method and add it to the stage list in
`BuildPipeline.run()`; timing and logging come for free.

**A different platform:** implement `Bridge` once; nothing else changes.

---

## 17. CLI reference

| Command | Purpose |
| --- | --- |
| `pymobile init [dir]` | create a project (`-n` name, `-p` package, `-f` force) |
| `pymobile setup-sdk` | download the Android SDK (`--with-ndk` for C builds) |
| `pymobile build --native` | build a real, installable APK (`--minimal-stdlib`, `--no-ssl`) |
| `pymobile run` | run the app on your machine (`--gui` for a clickable window) |
| `pymobile watch` | re-render on every save (`--png`, `--ids`, `--interval`) |
| `pymobile preview` | draw the first screen as a picture (`--png`, `--ids`) |
| `pymobile info` | show the configuration (`--json`) |
| `pymobile clean` | remove build artifacts |
| `pymobile doctor` | check the environment and the project |

The global flags `-v` (verbose) and `-c PATH` (project path) work both before
and after the sub-command: `pymobile -v build` equals `pymobile build -v`.

---

## 18. FAQ

**Why doesn't the UI update?**
Assigning to a widget property redraws by itself; call `self.refresh()` if the
tree structure changed. See [section 7](#7-updating-the-interface).

**Why does `pymobile run` draw nothing?**
That is expected: on a desktop the `StubBridge` logs the tree instead of drawing
it. Use it to verify logic, not appearance.

**Why doesn't a 404 raise an exception?**
It is a valid HTTP response. Use `response.ok` or `response.raise_for_status()`.

**Why is no permission dialog shown?**
The permission is probably missing from `permissions` in `pymobile.toml`.
Android denies undeclared permissions without showing anything.

**Why doesn't the button react?**
Check `enabled` — a disabled button ignores taps.

**Why does `push()` raise an error?**
The same screen object cannot be pushed twice. Create a new instance.

**Where did my `print()` go on device?**
To logcat: `adb logcat -s pymobile.stdout`.

**How do I shrink the APK?**
Keep `optimize = true` and `strip_debug = true` (defaults), trim files via
`exclude`, and list a single ABI.

**Can the config live in `pyproject.toml`?**
Yes, in a `[tool.pymobile]` table. If both files exist, `pymobile.toml` wins.

---

## Next steps

- [README.md](https://github.com/Maksum867/py-mobile/blob/main/README.md) — overview and API summary
- [CHANGELOG.md](https://github.com/Maksum867/py-mobile/blob/main/CHANGELOG.md) — release history
- `pymobile/tests/` — 316 tests that double as usage examples
