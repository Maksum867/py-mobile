<div align="center">

# PyMobile

**Build real Android apps in pure Python.**

Write a declarative UI, run one command, install the APK on your phone.

[![PyPI](https://img.shields.io/pypi/v/pymobile-framework.svg)](https://pypi.org/project/pymobile-framework/)
[![Python](https://img.shields.io/pypi/pyversions/pymobile-framework.svg)](https://pypi.org/project/pymobile-framework/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/Maksum867/py-mobile/blob/main/LICENSE)

</div>

---

```python
from pymobile import App, Button, Column, Label, Screen, Widget


class Home(Screen):
    title = "Hello"

    def __init__(self) -> None:
        super().__init__()
        self.taps = 0

    def build(self) -> Widget:
        self.counter = Label("Taps: 0")
        return Column(
            Label("Hello, Android!"),
            self.counter,
            Button("Tap me", on_press=self.on_tap),
            spacing=12,
        )

    def on_tap(self) -> None:
        self.taps += 1
        self.counter.text = f"Taps: {self.taps}"      # the screen redraws itself


App("Demo").run(Home())
```

```bash
pip install pymobile-framework
pymobile setup-sdk           # once per machine
pymobile build --native      # → build/demo-0.1.0.apk
```

That APK is signed, installable and runs a real CPython interpreter on the
device. No Java, no Gradle, no Android Studio.

---

## Table of contents

- [Why PyMobile](#why-pymobile)
- [Installation](#installation)
- [Your first app](#your-first-app)
- [How it works](#how-it-works)
- [UI components](#ui-components)
- [Layout](#layout)
- [Styling](#styling)
- [Screens and navigation](#screens-and-navigation)
- [Updating the screen](#updating-the-screen)
- [Notifications](#notifications)
- [Vibration](#vibration)
- [Permissions](#permissions)
- [HTTP requests](#http-requests)
- [Events](#events)
- [Timers](#timers)
- [Configuration reference](#configuration-reference)
- [Building an APK](#building-an-apk)
- [Application icon](#application-icon)
- [Installing on a phone](#installing-on-a-phone)
- [Debugging](#debugging)
- [Testing your app](#testing-your-app)
- [Error handling](#error-handling)
- [Desktop preview](#desktop-preview)
- [CLI reference](#cli-reference)
- [Extending the framework](#extending-the-framework)
- [Limitations](#limitations)
- [FAQ](#faq)
- [Contributing](#contributing)

---

## Why PyMobile

| | |
| --- | --- |
| **Real APKs** | Signed with v1+v2+v3 schemes, containing `classes.dex`, `resources.arsc` and an embedded CPython 3.14 for ARM64. |
| **Native views** | Widgets become genuine `TextView`, `Button`, `EditText`, `Switch`, `ProgressBar` and `LinearLayout` instances — not a web view or a custom canvas. |
| **Fast** | About five seconds per build. An unchanged rebuild is instant. |
| **Small setup** | ~800 MB of tooling, downloaded automatically. The NDK is not required. |
| **Testable** | Your whole app runs and is unit-testable on a desktop, with no emulator. |
| **No dependencies** | The runtime uses only the standard library, which keeps APKs small. |

Verified on a physical device running Android 14.

---

## Installation

**Requirements:** Python 3.10+, about 1 GB of free disk space, an Android 5.0+
device.

```bash
pip install pymobile-framework
```

> The distribution is named **`py-mobile`** because `pymobile` on PyPI belongs
> to an unrelated project. The import name and the CLI command are still
> `pymobile`.

Then install the Android toolchain, once per machine:

```bash
pymobile setup-sdk
```

This downloads JDK 17 and the Android SDK (~800 MB) into `~/.andro`. The NDK is
**not** downloaded: a prebuilt native bridge (22 KB) ships inside the package.
It is byte-identical for every application, so there is nothing to compile. If
you want to rebuild it from C source anyway:

```bash
pymobile setup-sdk --with-ndk    # adds ~2 GB
```

Already have Android Studio? Point PyMobile at your existing SDK instead:

```bash
export ANDROID_HOME=~/Android/Sdk          # macOS/Linux
$env:ANDROID_HOME = "C:\...\Android\Sdk"   # Windows PowerShell
```

You need `build-tools;34.0.0` and `platforms;android-34`.

### If the `pymobile` command is not found

Common on Windows when pip's scripts directory is not on `PATH`. This form
always works:

```bash
python -m pymobile build --native
```

Verify everything with:

```bash
pymobile doctor
```

---

## Your first app

```bash
pymobile init myapp --name "My App" -p com.example.myapp
cd myapp
pymobile run                # preview on your machine
pymobile build --native     # produce the APK
```

`init` generates:

```
myapp/
├── main.py           # your application
├── pymobile.toml     # configuration
├── README.md
├── .gitignore
└── assets/           # images, fonts, data files
```

The smallest possible app:

```python
from pymobile import App, Column, Label, Screen, Widget


class Home(Screen):
    def build(self) -> Widget:
        return Column(Label("Hello, Android!"))


App("My App").run(Home())
```

---

## How it works

Three ideas explain everything else.

**1. Widgets are descriptions, not views.** `Label("Hello")` draws nothing. It
is a node in a tree that serialises to JSON. A Java renderer converts that tree
into real Android views and patches them in place on every update.

**2. Everything platform-specific goes through a bridge.**

```
Your Python code
       ↓
    Bridge ──┬── AndroidBridge   on device, through JNI
             └── StubBridge      on desktop, records every call
```

**3. Therefore your app runs anywhere.** On a laptop the stub bridge logs what
would have happened; on a phone the same code vibrates and posts notifications.
You never write `if android:` — the framework picks the implementation.

```python
app = App("Demo")
print(app.platform)      # 'desktop' or 'android'
print(app.bridge.name)   # 'stub' or 'android'
```

**The build pipeline** runs twelve independent, individually timed stages:

```
validate → collect → compile → icons → toolchain → runtime
        → jni → dex → resources → assets → sign → verify
```

---

## UI components

Nine components. All of them accept `id`, `style`, `visible` and `enabled`.

### Label

Static or updatable text.

```python
label = Label("Heading", style=Style(font_size=24, bold=True))
label.set_text("New text")
```

### Button

```python
Button("Save", on_press=self.save)
Button("Unavailable", on_press=self.save, enabled=False)   # taps ignored
```

### TextInput

```python
TextInput(
    placeholder="Your name",
    max_length=50,             # extra characters are trimmed automatically
    on_change=lambda value: print(value),
)

TextInput(password=True)       # masked
TextInput(multiline=True)      # multi-line
```

`on_change` fires only on a genuine change — writing the same value again does
nothing. While the field has focus the framework never overwrites its contents,
so the keyboard stays open and the caret does not jump.

Methods: `set_value(text)`, `clear()`.

### Switch

```python
switch = Switch(checked=True, on_toggle=lambda state: print(state))
switch.toggle()            # returns the new state
switch.set_checked(False)
```

### ProgressBar

```python
bar = ProgressBar(40, maximum=100)
bar.set_value(150)         # clamped to maximum
bar.fraction               # 0.0 … 1.0

ProgressBar(indeterminate=True)    # spinner
```

### Image

```python
Image("assets/logo.png", fit="cover")   # contain | cover | fill | none
```

Paths are relative to your project directory.

### Spacer

```python
Spacer(16)     # 16 dp of empty space
```

### Divider

```python
Divider()                       # hairline between sections
Divider(inset=16, thickness=2)
```

---

## Layout

Containers, freely nestable.

```python
Column(a, b, c, spacing=12)                # vertical stack
Row(a, b, spacing=8, align=Align.CENTER)   # horizontal stack
Grid(a, b, c, d, columns=2, spacing=12)    # equal-width cells
ScrollView(content, spacing=8)             # scrollable region
Stack(background, foreground)              # layered, last on top
SafeArea(content)                          # clears the notch and status bar
```

### Grid

The container for cards, galleries and menus. Every cell in a column gets the
same width, so two stat cards stay aligned even when one holds `5` and the
other `2 h 45 m` — which is exactly what `Row(weight=1)` cannot guarantee.

```python
Grid(
    card("Completed", "12"),  card("Focus time", "5 h"),
    card("Breaks", "4"),      card("Average", "25 m"),
    columns=2,
    spacing=12,                       # or row_spacing= / column_spacing=
)
```

Rows fill left to right; the last row may be partially filled.

### Expanded and Flexible

Share out the space left over on the main axis.

```python
Row(
    Expanded(Button("Start")),            # half
    Expanded(Button("Reset"), flex=2),    # twice as wide
    spacing=8,
)
```

`Expanded` makes the child fill its share, `Flexible` lets it stay smaller.

### Divider

```python
Column(
    header,
    Divider(),                                   # hairline
    Divider(inset=16, thickness=2),              # inset, thicker
    Divider(vertical=True),                      # inside a Row
    body,
)
```

### SafeArea

```python
def build(self) -> Widget:
    return SafeArea(Column(...))                 # all edges
    return SafeArea(content, top=False)          # header bleeds upwards
```

Padding comes from the real window insets, so it is right on every device
instead of a hard-coded guess.

### Alignment

`align` positions children along the container's own axis; `cross_align`
positions them across it.

```python
Row(a, b, align=Align.SPACE_BETWEEN, cross_align=Align.CENTER)
Column(a, b, cross_align=Align.STRETCH)
```

Options: `Align.START`, `Align.CENTER`, `Align.END`, `Align.SPACE_BETWEEN`,
and `Align.STRETCH` for `cross_align`.

---

## Styling

```python
Style(
    font_size=18,
    bold=True,
    italic=False,
    color=Color.PRIMARY,
    background=Color.SURFACE,
    padding=EdgeInsets.all(16),
    margin=EdgeInsets.symmetric(horizontal=8, vertical=4),
    corner_radius=8,
    elevation=2,
    align=Align.CENTER,
)
```

### Spacing between specific neighbours

`spacing` on a container applies the same gap everywhere. When one gap must
differ, add a `margin` to the individual widget — the two are **added**, not
replaced:

```python
Column(
    header,
    Label("close to the header"),
    Label("pushed further down", style=Style(margin=EdgeInsets(top=24))),
    spacing=8,          # this one sits 8 + 24 dp below its neighbour
)
```

### Size constraints

```python
Style(min_width=120, max_width=200)     # a card that cannot collapse or sprawl
Style(aspect_ratio=16 / 9)              # keep a shape whatever the width
Style(min_height=44)                    # a comfortable tap target
Style(weight=1)                         # share of a Row/Column (see Expanded)
Style(width=120, height=48)             # a fixed size in dp
Style(width="match")                    # fill the parent ("wrap" also works)
Style(elevation=4)                      # a drop shadow (Android 5+)
```

Contradictory bounds raise immediately — `Style(min_width=200, max_width=120)`
is a `ValueError`, not a widget that silently clips to nothing on device.

Built-in colours: `PRIMARY`, `ACCENT`, `BACKGROUND`, `SURFACE`, `TEXT`,
`TEXT_MUTED`, `SUCCESS`, `WARNING`, `ERROR`, `TRANSPARENT`. Custom colours use
`#RGB`, `#RRGGBB` or `#AARRGGBB`.

Styles are immutable, so a base style is safe to share:

```python
BASE = Style(font_size=16, color=Color.TEXT)

Label("Normal", style=BASE)
Label("Error", style=BASE.merge(color=Color.ERROR, bold=True))
```

Invalid values fail fast: `Style(color="red")` raises `ValueError`.

`EdgeInsets` helpers: `EdgeInsets.all(8)`,
`EdgeInsets.symmetric(horizontal=8, vertical=4)`,
`EdgeInsets(left, top, right, bottom)`.

---

## Screens and navigation

A screen builds a widget tree and receives lifecycle callbacks.

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

Navigation is a stack:

```python
app.push(Settings())            # on_hide(current) → build() → on_mount → on_show
app.pop()                       # on_hide → on_unmount → on_show(previous)

app.navigator.replace(Other())  # swap the top screen
app.navigator.reset(Home())     # clear the stack, start fresh
app.navigator.depth             # how many screens are stacked
app.screen                      # the visible screen
```

The root screen is never popped — `pop()` returns `None` instead of leaving a
blank window. The hardware back button is wired up automatically.

> Do not push the same screen **object** twice; that raises `PyMobileError`.
> Create a new instance each time: `app.push(Settings())`.

Find a widget anywhere in the current screen:

```python
self.find("counter").set_text("5")     # matches Label(..., id="counter")
```

---

## Updating the screen

Change a widget and the screen redraws itself. There is no `render()` to
forget.

```python
class Home(Screen):
    def build(self) -> Widget:
        self.taps = 0
        self.counter = Label("Taps: 0")        # id becomes "counter"
        return Column(self.counter, Button("Tap", on_press=self.on_tap))

    def on_tap(self) -> None:
        self.taps += 1
        self.counter.text = f"Taps: {self.taps}"    # that is the whole update
```

`self.counter.text = ...` and `self.counter.set_text(...)` do the same thing.
Every stateful property works this way: `text`, `value`, `checked`, `visible`
and `enabled`.

Redraws are coalesced, so a handler that updates six widgets still produces a
single frame. Assigning a value that has not changed renders nothing at all,
and mutating a widget on a screen that is not visible is free.

Group updates explicitly when you build them in a loop:

```python
with app.batch():
    for label, value in zip(self.labels, values):
        label.text = value
# one render happens here
```

| Method | When to use |
| --- | --- |
| *(nothing)* | a property changed — handled for you |
| `self.refresh()` | the tree itself changed (rows added or removed) |
| `app.render()` | you want a frame pushed out right now |

```python
def on_data_loaded(self) -> None:
    self.items = fetch_items()
    self.refresh()          # the number of rows changed
```

`App("Demo", auto_render=False)` restores the old manual behaviour; in that
mode the first missed redraw logs a warning rather than leaving you guessing.

---

## Reacting to events

Subscribe from a screen and the handler is removed when the screen goes away:

```python
class TimerScreen(Screen):
    def on_mount(self) -> None:
        self.on("pomodoro:tick", self.on_tick)   # cancelled on unmount

    def on_tick(self, event) -> None:
        self.clock.text = event.get("remaining")
```

With `app.on()` the handler of a popped screen stays subscribed: it keeps
firing, keeps the screen alive, and runs twice as soon as the screen is pushed
again. `self.on()` avoids that. To bind a handler registered elsewhere, pass
the screen: `app.on("tick", handler, screen=self)`.

---

## Notifications

```python
app.notify("Done", "File saved")               # returns a notification id
app.notify("Syncing", "In progress…", ongoing=True)   # cannot be swiped away
app.notifications.cancel(notification_id)
```

The notification channel is created automatically. On Android 13+ you need the
`POST_NOTIFICATIONS` permission — see below.

---

## Vibration

```python
app.vibrate(100)                               # one shot, milliseconds
app.vibration.preset("success")
app.vibration.pattern([0, 100, 50, 100])       # [wait, buzz, wait, buzz]
app.vibration.cancel()
```

Presets: `tick`, `click`, `double`, `success`, `error`, `heartbeat`.

Pulses shorter than about 50 ms cannot be felt on most hardware, so short
values are stretched automatically and waveforms are sent with explicit
amplitudes — several devices silently ignore the default.

---

## Permissions

```python
from pymobile import Permission

app.permissions.has(Permission.CAMERA)              # bool
app.permissions.request(Permission.CAMERA)          # {'android.permission.CAMERA': True}
app.permissions.missing([Permission.CAMERA, "VIBRATE"])
app.require_permissions(Permission.CAMERA)          # raises PermissionError_ if denied
```

Three spellings are accepted: `"CAMERA"`, `"android.permission.CAMERA"` and
`Permission.CAMERA`.

### Three rules that save hours

**1. Declare every permission in `pymobile.toml`.** Android denies an
undeclared permission *silently* — no dialog appears at all. The compiler warns
you when code requests something the manifest lacks:

```
! requested in code but not declared in pymobile.toml: android.permission.CAMERA
  — Android will deny them without showing a dialog
```

**2. Ask after the first screen is visible.** A request issued before the
window exists is dropped by the system. Put it in `on_show()`, not before
`app.run()`:

```python
def on_show(self) -> None:
    if self.visits == 1:
        self.app.permissions.request(Permission.CAMERA)
```

**3. Two refusals disable the dialog forever.** Android then returns an instant
denial. PyMobile detects this and opens the app's settings page with an
explanation, instead of failing mutely.

---

## HTTP requests

A client built on the standard library — no third-party dependency, so nothing
extra lands in the APK.

```python
from pymobile import HttpClient

client = HttpClient(
    base_url="https://api.example.com",
    headers={"Authorization": "Bearer ..."},
    timeout=10,
    retries=2,           # exponential backoff
)

client.get("/items", params={"page": 2})
client.post("/items", json={"name": "Widget"})
client.put("/items/1", json={"name": "Updated"})
client.delete("/items/1")
```

The response object:

```python
response = client.get("/items")

response.status      # 200
response.ok          # True for 2xx
response.json()      # parsed JSON
response.text        # decoded text
response.content     # raw bytes
response.headers     # lowercase keys
response.elapsed     # seconds
```

**Error statuses are returned, not raised** — they are valid HTTP responses:

```python
response = client.get("/missing")
if not response.ok:
    print(response.status)        # 404

response.raise_for_status()       # raises NetworkError for 4xx/5xx
```

Retries cover connection failures and 408/425/429/5xx.

HTTPS works out of the box: a bundle of root certificates is packaged into the
APK, because Android provides no certificate file where OpenSSL looks for one.

Remember to list `android.permission.INTERNET` in your config.

---

## Languages

The device language plus a small catalogue, which is usually all a mobile app
needs. `gettext` and `.mo` files keep working — the standard library is
packaged in full.

```python
from pymobile import t, translations, device_language

translations.load_dir("locales")          # locales/en.json, locales/uk.json …
translations.use(device_language(default="en"))

Label(t("greeting", name="Оксана"))       # "Привіт, Оксана!"
```

```json
{
  "greeting": "Привіт, {name}!",
  "items": {
    "one":  "{count} елемент",
    "few":  "{count} елементи",
    "many": "{count} елементів"
  }
}
```

```python
t("items", count=1)     # 1 елемент
t("items", count=3)     # 3 елементи
t("items", count=5)     # 5 елементів
```

Plural forms cover `zero`, `one`, `few`, `many` and `other`, so Slavic rules
work, not only the English one. Lookup falls back from `pt-br` to `pt` and
then to the default language, and a missing key renders as the key itself
(logged once) rather than raising in the middle of a screen.

Switching language redraws whatever is on screen — `translations.use("uk")` is
enough, because `t()` runs inside `build()` and the screen is rebuilt for you.

`device_language()` reads the real system setting on Android — including
Android 13 per-app language overrides — and the usual environment variables on
a desktop. Force one during development with `PYMOBILE_LANGUAGE=uk`.

Already using xgettext? `translations.install_gettext("app", "locale")` reads
your compiled `.mo` catalogues instead.

---

## Events

A synchronous event bus decouples UI from application logic.

```python
# framework events
app.on("app:start",     lambda e: ...)
app.on("app:stop",      lambda e: ...)
app.on("app:render",    lambda e: ...)
app.on("screen:change", lambda e: print(e.source))

# your own events
app.events.emit("cart:updated", source="CartScreen", count=3)
app.on("cart:updated", lambda e: print(e.get("count")))

subscription = app.on("x", handler)
subscription.cancel()          # always unsubscribe in on_unmount()
```

An exception inside one handler is logged and never prevents the others from
running.

---

## Timers

Schedule work without importing `threading`. Callbacks fire on a background
thread on every platform, so the UI never blocks, and the same code runs on
desktop and device.

```python
# every second — drive a clock, poll a sensor, tick a game
ticker = app.set_interval(1000, self.on_tick)

# once, after a delay — dismiss a splash, auto-save
app.set_timeout(250, splash.dismiss)

# stop early
ticker.cancel()
```

Every call returns a `TimerHandle` with `.cancel()` and `.cancelled`. An
exception inside a callback is logged and does **not** stop a repeating
timer. All timers are cancelled automatically when the app stops, but you
should still cancel a repeating timer in `on_unmount()` so a popped screen
does not keep ticking:

```python
def on_unmount(self) -> None:
    self.ticker.cancel()
```

### Intervals do not drift

Ticks are scheduled against a fixed timeline — tick *n* is due at
`start + n × interval` — so the time your callback spends working is not added
to the next wait. A one-second timer is still on the second an hour later,
which matters for clocks, metronomes and games.

```python
app.set_interval(1000, self.tick)                          # aligned (default)
app.set_interval(1000, self.poll, drift_correction=False)  # fixed pause between runs
```

Deadlines missed while the device was asleep are skipped rather than fired as
a burst, so a metronome stays in phase instead of stuttering to catch up. Use
`drift_correction=False` for a poller that must not overlap itself.

---

## Configuration reference

Everything lives in `pymobile.toml` (or a `[tool.pymobile]` table inside
`pyproject.toml`).

```toml
[app]
# --- identity ---
name = "My App"                 # shown under the launcher icon
package = "com.example.myapp"   # reverse-DNS, lowercase segments
version = "1.0.0"
version_code = 1                # integer; must increase for each Play upload

# --- entry point ---
entrypoint = "main.py"
source_dir = "."

# --- Android platform ---
min_sdk = 21                    # Android 5.0
target_sdk = 34                 # Android 14
orientation = "portrait"        # portrait | landscape | sensor | user

# Every permission requested at runtime must be listed here.
permissions = [
    "android.permission.INTERNET",
    "android.permission.VIBRATE",
    "android.permission.POST_NOTIFICATIONS",
]

# --- resources ---
icon = "assets/icon.png"        # optional; default icon used otherwise

# --- build ---
abis = ["arm64-v8a"]
output_dir = "build"
optimize = true                 # ship bytecode instead of sources
strip_debug = true              # -OO: drop docstrings and asserts
exclude = ["tests/**", "**/__pycache__/**"]
```

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | `PyMobile App` | display name |
| `package` | `org.pymobile.app` | unique application id |
| `version` | `0.1.0` | user-visible version |
| `version_code` | `1` | internal build number |
| `entrypoint` | `main.py` | module to execute |
| `source_dir` | `.` | root of your sources |
| `min_sdk` | `21` | oldest supported Android |
| `target_sdk` | `34` | Android version you target |
| `orientation` | `portrait` | screen orientation |
| `permissions` | `["…INTERNET"]` | manifest permissions |
| `icon` | *(none)* | path to a square PNG |
| `abis` | `["arm64-v8a"]` | architectures |
| `output_dir` | `build` | where the APK is written |
| `optimize` | `true` | package `.pyc` |
| `strip_debug` | `true` | compile with `-OO` |
| `exclude` | see above | glob patterns to skip |

Every value is validated **before** the build starts, and each error carries a
fix:

```
✗ Invalid package name 'Bad_Package'
  hint: Use reverse-DNS with lowercase segments, e.g. com.example.myapp
```

Inspect the resolved configuration with `pymobile info` or
`pymobile info --json`.

---

## Building an APK

```bash
pymobile build --native                    # incremental
pymobile build --native --clean            # ignore the cache
pymobile build --native -v                 # per-stage timings
pymobile build --native --icon logo.png    # override the icon
pymobile build --native --output dist      # different directory
pymobile build --native --no-optimize      # ship .py for debugging
pymobile build --native --minimal-stdlib   # drop desktop-only stdlib
pymobile build --native --no-ssl           # drop OpenSSL (no HTTPS)
```

> Without `--native` you get a lightweight structural package used for quick
> checks. **It does not install on a device.**

A rebuild with no changes finishes instantly:

```
✓ up to date: my-app-1.0.0.apk (16.6 MB)
```

The cache tracks every input: sources, configuration and icon.

**Inside the APK:**

```
AndroidManifest.xml          generated from your config
classes.dex                  launcher activity and the view renderer
resources.arsc               compiled resources
lib/arm64-v8a/*.so           CPython, OpenSSL, SQLite, the JNI bridge
assets/app/                  your code and the pymobile package
assets/python/               standard library and CA certificates
res/mipmap-*/icon.png        icons, five densities
META-INF/                    signature (v1+v2+v3)
```

Builds are reproducible: identical inputs produce a byte-identical APK. The
file is written to a temporary path and moved into place, so an interrupted
build never leaves a corrupt artifact.

### Size

A hello-world APK is **16.6 MB**, down from 21.6 MB in 0.2.0. The official
CPython Android runtime ships every support library twice — `libcrypto.so`
and `libcrypto_python.so` are byte-identical, and only the `_python` names are
actually linked — so 5 MB of each APK was the same three libraries repeated.
That is fixed for every build; no flag needed.

Two opt-in flags trim further:

| Flag | Saves | Cost |
| --- | --- | --- |
| `--minimal-stdlib` | ~1.7 MB | no `pydoc`, `unittest`, `venv`, `pdb`, `xmlrpc` on device |
| `--no-ssl` | ~4.7 MB | no HTTPS at all — `HttpClient` over TLS stops working |

With both, the same app is **11.7 MB**. `--no-ssl` only makes sense for an app
that talks to nothing, or over plain HTTP on a local network.

```
21.6 MB   0.2.0
16.6 MB   0.3.0                              duplicate libraries removed
11.7 MB   0.3.0 --minimal-stdlib --no-ssl
```

---

## Application icon

```toml
icon = "assets/icon.png"
```

Provide a square PNG, JPG or WebP — 512×512 works best. It is resized into all
five densities (48, 72, 96, 144 and 192 px). Install the `icons` extra for
high-quality resampling:

```bash
pip install "py-mobile[icons]"
```

Without it the icon is copied unscaled; the build still succeeds. With no icon
configured, a bundled default is used, so a build never fails over a missing
asset.

---

## Installing on a phone

**Without a cable:** copy the `.apk` to your device through cloud storage or a
messenger, open it there and allow installation from unknown sources.

**Over USB**, with USB debugging enabled:

```bash
adb install -r build/my-app-1.0.0.apk
```

`adb` lives in `~/.andro/sdk/platform-tools/`.

---

## Debugging

Everything your app prints, including tracebacks, goes to logcat:

```bash
adb logcat -s pymobile pymobile.stdout pymobile.stderr
```

| Tag | Contents |
| --- | --- |
| `pymobile` | framework and renderer messages |
| `pymobile.stdout` | your `print()` output |
| `pymobile.stderr` | exceptions and tracebacks |

If a single widget fails to render, it is replaced by red text naming the
error while the rest of the screen keeps working.

---

## Testing your app

`StubBridge` records every platform call, so no emulator is needed and tests
run in milliseconds.

```python
from pymobile import App, Button, Column, Label, Screen, Widget
from pymobile.core.bridge import StubBridge


class ProfileScreen(Screen):
    def build(self) -> Widget:
        # Save explicit references to widgets for direct test access
        self.status_label = Label("Offline")
        self.login_btn = Button("Log In", on_press=self.on_login)
        return Column(self.status_label, self.login_btn)

    def on_login(self) -> None:
        self.status_label.text = "Online"
        self.app.notify("Welcome", "You have logged in successfully")


def test_login_updates_ui_and_notifies():
    bridge = StubBridge(verbose=False)
    app = App("Test", bridge=bridge)
    screen = ProfileScreen()
    app.run(screen)

    # Trigger action directly on the widget reference
    screen.login_btn.press()

    # Verify UI state change
    assert screen.status_label.text == "Online"

    # Verify platform notification was sent via StubBridge
    assert bridge.calls_named("notify")
    spec = list(bridge.notifications.values())[0]
    assert spec.title == "Welcome"


def test_permission_denial_is_handled():
    denying = StubBridge(grant_permissions=False, verbose=False)
    app = App("Test", bridge=denying)
    assert app.permissions.request("CAMERA") == {"android.permission.CAMERA": False}
```

Useful members: `calls`, `calls_named(name)`, `notifications`, `granted`,
`reset()`, and the `grant_permissions=False` constructor flag.

---

## Error handling

Every exception derives from `PyMobileError` and carries a `message` and an
actionable `hint`.

```python
from pymobile.errors import PyMobileError, NetworkError, ConfigError

try:
    response = client.get("/items")
except NetworkError as error:
    print(error.message)   # what happened
    print(error.hint)      # how to fix it
except PyMobileError:
    ...                    # catch anything from the framework
```

| Exception | Raised when |
| --- | --- |
| `ConfigError` | configuration missing or invalid |
| `NetworkError` | request failed, host unreachable, invalid JSON |
| `PermissionError_` | the user declined a permission |
| `ResourceError` | an icon or template could not be read |
| `BridgeError` | a call into Android failed |
| `PlatformError` | feature unavailable on this platform |

The CLI prints only the message and hint. Add `-v` for a full traceback.

---

## Desktop preview

`pymobile preview` renders the first screen into a picture right on your
laptop — no emulator, no phone. It runs your entry point with the stub
bridge and draws the resulting widget tree:

```bash
pymobile preview            # text picture in the terminal
pymobile preview --ids      # annotate each widget with its id
pymobile preview --png ui.png   # save a raster image (needs Pillow)
```

The text picture shows the real layout — `Row` children sit side by side,
`ProgressBar` is drawn as a filled bar, `Switch` shows its state:

```text
┌──────────────────────────────┐
│ Pomodoro Focus               │
├──────────────────────────────┤
🎯 Focus
25:00
[░░░░░░░░░░░░░░░░] 0%
(Start)  (Reset)
Vibrate when done  [●] on
└──────────────────────────────┘
```

The same renderer is importable, so tests and notebooks can snapshot a
screen too:

```python
from pymobile.core.ui.preview import render_ascii
print(render_ascii(app.screen.build(), title="Home"))
```

### An interactive window

`pymobile run --gui` opens a real window instead of printing once. Buttons run
their callbacks, switches and text fields feed events back through the same
path the phone uses, and navigation works — a back button appears as soon as
the stack is deeper than one screen. Toasts and vibration show up in the
status strip.

```bash
pymobile run --gui
```

It is built on Tkinter, which ships with CPython, so it costs no dependency.
Trees are patched into the existing widgets when the structure has not
changed, so typing in a field does not lose focus.

### In a browser

`pymobile run --web` serves the same interactive preview over HTTP, which is
what you want on a remote machine, in a container, or when Tk is unavailable:

```bash
pymobile run --web                 # http://127.0.0.1:8765
pymobile run --web --port 9000
pymobile run --web --host 0.0.0.0  # open it from your phone on the same Wi-Fi
```

The page is plain HTML built from the same serialised tree the phone receives,
so it cannot drift from the real renderer. Buttons, switches and text fields
post back to the app, and the page polls for updates, so a timer tick appears
on its own. Widget ids are carried into `data-wid` attributes, so the browser
inspector tells you exactly which widget a node is.

### Hot reload

`pymobile watch` re-renders every time you save:

```bash
pymobile watch                  # text picture on every save
pymobile watch --png ui.png     # write an image instead
pymobile watch --interval 0.1   # poll faster
```

Editing an imported helper module counts too, not just `main.py`. A syntax
error prints the exception and keeps watching, so a half-typed line does not
end the session.

```text
• watching /home/me/pomodoro — press Ctrl+C to stop
✓ rendered in 12 ms

• changed: main.py
✓ rendered in 11 ms
```

---

## CLI reference

| Command | Description |
| --- | --- |
| `pymobile init [dir]` | create a project (`-n` name, `-p` package, `-f` force) |
| `pymobile setup-sdk` | install the Android toolchain (`--with-ndk`, `--path`) |
| `pymobile build --native` | build a signed, installable APK (`--minimal-stdlib`, `--no-ssl`) |
| `pymobile run` | run the app on your machine (`--gui` window, `--web` browser) |
| `pymobile watch` | re-render on every save (`--png`, `--ids`, `--interval`) |
| `pymobile preview` | draw the first screen as a picture (`--png`, `--ids`) |
| `pymobile info` | show the resolved configuration (`--json`) |
| `pymobile doctor` | check environment and project health |
| `pymobile clean` | remove build artifacts |

Global flags `-v` (verbose) and `-c PATH` (project directory) work both before
and after the sub-command.

---

## Extending the framework

The architecture is designed so that additions never touch existing code.

**A new widget** — subclass `Widget`, set `type_name`, override `props()`, then
add a branch to `ViewBuilder.java`:

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

**A new Android API** — add a method to `Bridge`, implement it in
`AndroidBridge` and `StubBridge`, wrap it in a small class under `core/api/`.

**A new build stage** — write a method and add one line to
`BuildPipeline.run()`; timing and logging come for free.

**A new platform** — implement `Bridge` once; nothing else changes.

---

## Limitations

- **arm64-v8a only.** Covers roughly 99% of active devices; x86_64 is planned.
- **APK size is about 16.6 MB** (11.7 MB with `--minimal-stdlib --no-ssl`),
  dominated by the interpreter and standard library.
- **Android 5.0 (API 21) minimum.**
- The renderer covers the components documented here; more are being added.

---

## FAQ

**Why doesn't my UI update?**
It should: assigning to a widget property redraws the screen by itself. If the
*structure* changed — rows added or removed — call `self.refresh()` to rebuild
through `build()`. See [Updating the screen](#updating-the-screen).

**Why does `pymobile run` show no window?**
By default it runs your logic through the stub bridge without native views,
which is what makes apps testable without an emulator. Use `pymobile run --gui`
for a real, clickable window, `pymobile preview` for a text picture, or
`pymobile watch` to re-render on every save.
See [Desktop preview](#desktop-preview).

**Why doesn't a 404 raise an exception?**
Because it is a valid HTTP response. Use `response.ok` or
`response.raise_for_status()`.

**Why is no permission dialog shown?**
Either the permission is missing from `pymobile.toml`, or you have already
denied it twice and Android has blocked further prompts. See
[Permissions](#permissions).

**Why doesn't my button respond?**
Check `enabled` — a disabled button ignores taps.

**Why does `push()` raise an error?**
The same screen object cannot be pushed twice. Create a new instance.

**Where did my `print()` output go?**
To logcat: `adb logcat -s pymobile.stdout`.

**How do I make the APK smaller?**
Keep `optimize = true` and `strip_debug = true`, trim files with `exclude`, and
list a single ABI.

**Can I keep the config in `pyproject.toml`?**
Yes, under `[tool.pymobile]`. If both files exist, `pymobile.toml` wins.

**Do I need Android Studio?**
No. `pymobile setup-sdk` downloads only the command-line tools it needs.

---

## Contributing

```bash
git clone https://github.com/Maksum867/py-mobile.git
cd pymobile
pip install -e ".[dev]"

pytest                  # 331 tests
ruff check pymobile     # linting
mypy pymobile           # strict type checking
```

To rebuild the native artifacts from source (requires
`pymobile setup-sdk --with-ndk`):

```bash
PYMOBILE_BUILD_JAVA=1 PYMOBILE_BUILD_JNI=1 pymobile build --native --clean
```

Issues and pull requests are welcome.

---

## Documentation

- **[GUIDE.md](https://github.com/Maksum867/py-mobile/blob/main/GUIDE.md)** — extended guide with worked examples
- **[CHANGELOG.md](https://github.com/Maksum867/py-mobile/blob/main/CHANGELOG.md)** — release history

## License

MIT — see [LICENSE](https://github.com/Maksum867/py-mobile/blob/main/LICENSE).