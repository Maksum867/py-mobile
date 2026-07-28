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
        self.counter = Label("Taps: 0")

    def build(self) -> Widget:
        return Column(
            Label("Hello, Android!"),
            self.counter,
            Button("Tap me", on_press=self.on_tap),
            spacing=12,
        )

    def on_tap(self) -> None:
        self.taps += 1
        self.counter.set_text(f"Taps: {self.taps}")
        self.app.render()


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
- [Configuration reference](#configuration-reference)
- [Building an APK](#building-an-apk)
- [Application icon](#application-icon)
- [Installing on a phone](#installing-on-a-phone)
- [Debugging](#debugging)
- [Testing your app](#testing-your-app)
- [Error handling](#error-handling)
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
pip install py-mobile
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

Seven components. All of them accept `id`, `style`, `visible` and `enabled`.

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

---

## Layout

Four containers, freely nestable.

```python
Column(a, b, c, spacing=12)                # vertical stack
Row(a, b, spacing=8, align=Align.CENTER)   # horizontal stack
ScrollView(content)                        # scrollable region
Stack(background, foreground)              # layered, last on top
```

```python
Column(
    Label("Heading"),
    Row(Button("Yes"), Button("No"), spacing=8),
    ScrollView(Column(*[Label(f"Row {i}") for i in range(50)])),
    spacing=12,
)
```

Alignment options: `Align.START`, `Align.CENTER`, `Align.END`,
`Align.SPACE_BETWEEN`.

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

    def on_mount(self):   ...   # once, when pushed onto the stack
    def on_show(self):    ...   # every time it becomes visible
    def on_hide(self):    ...   # when another screen covers it
    def on_unmount(self): ...   # once, when popped
```

Navigation is a stack:

```python
app.push(Settings())            # on_hide(current) → on_mount → on_show
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

This is the one concept newcomers stumble on. `build()` runs **once** and its
result is cached, so a redraw must be requested explicitly.

```python
class Home(Screen):
    def __init__(self):
        super().__init__()
        self.taps = 0
        self.counter = Label("Taps: 0")     # keep a reference

    def build(self) -> Widget:
        return Column(self.counter, Button("Tap", on_press=self.on_tap))

    def on_tap(self) -> None:
        self.taps += 1
        self.counter.set_text(f"Taps: {self.taps}")   # 1. change a property
        self.app.render()                              # 2. redraw
```

| Method | When to use | Cost |
| --- | --- | --- |
| `self.app.render()` | properties changed, structure is the same | cheap; keeps scroll position and keyboard focus |
| `self.refresh()` | the tree itself changed (rows added or removed) | rebuilds through `build()` |

```python
def on_data_loaded(self) -> None:
    self.items = fetch_items()
    self.refresh()          # the number of rows changed
```

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
```

> Without `--native` you get a lightweight structural package used for quick
> checks. **It does not install on a device.**

A rebuild with no changes finishes instantly:

```
✓ up to date: my-app-1.0.0.apk (21.0 MB)
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
from pymobile import App
from pymobile.core.bridge import StubBridge


def test_button_posts_a_notification():
    bridge = StubBridge(verbose=False)
    app = App("Test", bridge=bridge)
    app.run(Home())

    app.screen.find("btn").press()

    assert bridge.calls_named("notify")
    spec = list(bridge.notifications.values())[0]
    assert spec.title == "Hello"


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

## CLI reference

| Command | Description |
| --- | --- |
| `pymobile init [dir]` | create a project (`-n` name, `-p` package, `-f` force) |
| `pymobile setup-sdk` | install the Android toolchain (`--with-ndk`, `--path`) |
| `pymobile build --native` | build a signed, installable APK |
| `pymobile run` | run the app on your machine |
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
- **APK size is about 21 MB**, dominated by the interpreter and standard
  library.
- **Android 5.0 (API 21) minimum.**
- The renderer covers the components documented here; more are being added.

---

## FAQ

**Why doesn't my UI update?**
Call `self.app.render()` after changing properties, or `self.refresh()` when
the tree structure changed. See [Updating the screen](#updating-the-screen).

**Why does `pymobile run` show no window?**
That is expected. On a desktop the stub bridge logs the widget tree instead of
drawing it — it verifies logic, not appearance.

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