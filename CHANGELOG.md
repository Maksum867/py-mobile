# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [semantic versioning](https://semver.org/).

## [0.6.4] — 2026-09-05

### Fixed

- **The package could not be imported on Python 3.10 at all.** `core/config.py`
  imported `tomllib`, which is standard only from 3.11, while the metadata
  advertised `requires-python = ">=3.10"` and a 3.10 classifier. The import now
  falls back to the `tomli` backport, which is declared as a conditional
  dependency for 3.10 only.
- **`.gitignore` swallowed the prebuilt JNI bridge.** A blanket `*.so` rule kept
  `resources/android/prebuilt/arm64-v8a/libpymobile.so` out of git, so a fresh
  clone could not run `pymobile build --native`. The path is now excluded from
  the rule.
- **`pytest` failed at collection on a fresh clone.** `test_release_audit.py`
  imported `tools.release_audit`, and `tools/` is gitignored; the import is now
  skipped when unavailable instead of breaking the whole run.

- **The build mode is part of the cache key.** `pymobile build` followed by
  `pymobile build --native` reported "up to date" and handed back the
  structural package — a 52 KB artifact that cannot be installed on a device,
  presented as a finished APK. The two modes are now cached separately.
- **`storage_path` accepts a directory.** The environment override
  `PYMOBILE_STORAGE_DIR` is a directory, so `App(storage_path=...)` was read as
  one too and failed with a bare `IsADirectoryError` from inside `save()`.
  Directories now get the default filename appended, and the remaining disk
  errors are raised as `ResourceError` with a hint.
- **Desktop stores are per application.** Every project shared
  `~/.pymobile/pymobile_store.json` and overwrote its neighbours' settings; the
  file is now named after the application id. An existing shared store is
  adopted once so no data appears to vanish.
- **`preview --png` renders non-Latin text.** Pillow's ASCII-only default font
  turned Cyrillic and Greek interfaces into rows of boxes; a Unicode TrueType
  face is located on the system instead, overridable with
  `PYMOBILE_PREVIEW_FONT`.
- **One broken widget no longer takes down a desktop render.** Failing widgets
  are replaced by red error text everywhere, as the device renderer already
  did, and exceptions raised by widget callbacks are logged rather than
  propagated out of the event loop.
- **Malformed values from a front end are ignored, not fatal.** A `Stepper`
  receiving `"abc"` logs a warning instead of raising `ValueError` out of
  `handle_ui_event`.
- **Builds no longer embed the wall clock.** Entries added to the native APK
  kept their source mtime, so two identical builds differed; every entry now
  uses the fixed timestamp already used by the structural packager.
- `Dropdown` and `SegmentedButtons` raise `ValueError` when constructed with a
  `value` that is not among the options, instead of silently selecting the
  first one — matching `set_value()` and the rest of the fail-fast API.
- The `pymobile init` template imports `Align` and `Color` from `pymobile`
  rather than the internal `pymobile.core.ui`.

### Added

- `Storage.transaction()`, `Storage.update()`, `Storage.increment()` and
  `Storage.setdefault()` for read-modify-write sequences that must not race
  with jobs, timers or HTTP callbacks.
- `ListTile(on_long_press=...)` — a second per-row action, wired through the
  Android renderer (with haptic feedback), the Tk window and the browser
  preview.

## [0.6.3] — 2026-09-02

### Fixed

- CPython Android runtime archives are now pinned by SHA-256 before extract,
  matching the JDK and SDK command-line tools.
- `notify()` creates the notification channel in Java, so a default
  `pymobile build --native` is enough. `PYMOBILE_BUILD_JNI=1` is no longer
  documented as a requirement for notifications.

### Changed

- Package metadata includes an author email and an Issues URL.

## [0.6.2] — 2026-08-31

### Fixed

- App updates now re-extract Python assets: `PythonRuntime` stamps `.extracted`
  with the installed `versionCode` instead of unpacking only once.
- CI quality gate no longer imports a non-existent `notion.tools.release_audit`
  module. `tools/release_audit.py` and `examples/device-smoke` ship in the repo.
- `JobHandle.then(on_success=...)` works (alias of `on_done`).
- `JobHandle.wait(timeout=)` and `HttpFuture.get(timeout=)` raise `TimeoutError`.
- Cancelling a one-shot job skips `fn` if it has not started.
- `Storage.__getitem__` raises `KeyError` for missing keys (matching `del`).
- `ValidationError` subclasses `PyMobileError`; `PermissionError_` is exported.
- `Avatar("MK")` is initials; `image=` is accepted as an alias of `source`.
- `RadioButton.press()` updates the parent `RadioGroup`.
- Web preview renders the 0.6.0 widgets, dark theme chrome, multiline
  `TextInput` as `<textarea>`, and binds `--host 0.0.0.0` by default.
- `pymobile build --no-optimize` exists; `--optimize` no longer blindly
  overwrites `pymobile.toml`.
- `pymobile build --keystore` / `--ks-pass` / `--key-alias` / `--key-pass`
  sign with a release keystore.
- `setup-sdk` downloads command-line tools on macOS (Intel and Apple Silicon)
  and Temurin JDK 17 for Linux/macOS aarch64.
- `slugify` transliterates Cyrillic so `Скарбничка` is not `app`.
- `doctor` no longer claims "everything looks good" when the Android SDK is
  missing.
- HTTP cache stores bodies as base64; `HttpClient` builds an SSL context with
  certifi; `cache=` accepts a `Storage` for the documented example.
- Default `target_sdk` is 35. Docs name the PyPI package `pymobile-framework`.

### Added

- Trusted Publishing workflow (`.github/workflows/publish.yml`).
- Python 3.14 classifier.

## [0.6.1] 

### Fixed — 2026-08-05

- Prevented deadlocks when a completion callback cancels its own `JobHandle` or
  `HttpFuture`; callbacks now always run after internal locks are released.
- A failed repeating job now completes its handle with the original error.
- `Storage` now rejects non-string keys as its public contract specifies.
- `Image` now accepts validated local `file://` URIs.
- `RatingBar(value=...)` now works as documented.
- `Dropdown` and `SegmentedButtons` accept documented `on_change` as a
  compatibility alias for `on_select`.
- `Validator` now accepts the documented mapping/rule DSL as well as callable
  validators.

### Added

- `App.dispatch(...)` and `UiDispatcher` for explicitly handing background
  results into the next safe UI render.
- Typed serialised UI-tree contract plus a capability registry and parity tests
  for the built-in renderer implementations.
- `HttpSecurityPolicy` with opt-in HTTPS-only and hostname allow-list rules.
- Regression tests for the repaired public contracts.
- A GitHub Actions quality gate and Android API 34 native-APK emulator smoke
  test, with an `examples/device-smoke` fixture.

## [0.6.0] — 2026-08-03

### Added

**UI components**

- `RadioButton` / `RadioGroup` — mutually exclusive selection within a group.
- `SegmentedButtons` — horizontal selection panel (tabs / segmented control).
- `ProgressText` — `ProgressBar` with a text label overlay (e.g. "Downloading 42%").
- `Link` — clickable text that opens a URL in the system browser via the native bridge.
- `DataTable` — simple table with headers and rows.
- `Avatar` — round avatar with initials or an image.
- `Checkbox` — toggle with `on_toggle` callback.
- `Slider` — value slider with `minimum`, `maximum` and `on_change`.
- `RatingBar` — star rating widget.
- `Dropdown` — selection from a list of options.
- `Chip` — compact element for actions, filters or tags.
- `Badge` — small notification counter.
- `Stepper` — increment/decrement numeric value.
- `SearchBar` — text input with search semantics and `on_change`.

**Notifications**

- Fixed notification channel creation: channels are now created reliably on
  all devices. Building with `PYMOBILE_BUILD_JNI=1` ensures the native bridge
  includes the `ensure_channel` entry point.
- Added documentation for the full notification setup: permission declaration,
  runtime request, JNI build flag and device settings check.

## [0.5.1] — 2026-08-02

### Added

**List**

- `List(item_count, builder)` — virtualised list that renders only visible
  rows, so 10 000+ items scroll smoothly.
- `ListTile(title, subtitle, trailing, on_press)` — list row builder.
- Methods: `refresh()`, `scroll_to(index)`. Add/clear are blocked because
  the list is virtualised.

**Plugins**

- `Plugin(name)` base class with `activate(app)`, `on_app_start(app)`,
  `on_app_stop(app)` hooks.
- `PluginRegistry` with `register()`, `activate_all()`, `on_app_start()`,
  `on_app_stop()`.
- Plugins are activated automatically in `App.run()` and stopped in
  `App.stop()`.
- Exported as `Plugin`, `PluginRegistry`, `plugins`.

**Background jobs**

- `JobManager.enqueue(fn)` runs a function once on a background thread;
  `JobManager.every(interval_ms, fn)` repeats until cancelled.
- `JobHandle` with `.then(on_success, on_error)`, `.wait(timeout)`,
  `.cancel()`, `.done`, `.cancelled`, `.result`, `.error`.
- `App.run_job(fn)` and `App.repeat_job(ms, fn)` convenience methods.

**Logger**

- `configure(level, color, log_file=)` — optional file logger with
  timestamps.
- `get_diagnostics()` — returns framework version, platform, Python version,
  log level and active handlers.
- `App(log_file="app.log")` parameter.

**Build**

- NativeBackend accepts `abi=` parameter; hardcoded `arm64-v8a` replaced
  with `self.abi`. Enables `x86_64` builds for emulators and Chromebooks.
- Pipeline passes `config.abis[0]` to the backend.

## [0.5.0] — 2026-08-01

### Added

**Themes**

- `Theme(name, colors)` — semantic colour palette.
- `Theme.light()` and `Theme.dark()` built-in themes.
- `App(theme="light"|"dark"|Theme)` — sets the initial theme.
- `app.set_theme("dark")` — switches at runtime and redraws the visible
  screen (like a language change).
- `app.theme.is_dark`, `app.theme["PRIMARY"]`, `theme.color("TEXT")`.
- Exported as `Theme` from `pymobile` and `pymobile.core.ui`.

**Storage**

- `Storage` — JSON key-value store with atomic writes (temp + rename).
- `App(storage_path=...)` → `app.storage`.
- API: `get`, `set`, `delete`, `contains`, `clear`, `keys`, `items`, `[]`
  operator.
- `default_storage_path()` — Android private files / desktop `~/.pymobile`.
- Override with `PYMOBILE_STORAGE_DIR` environment variable.

**Async HTTP**

- `HttpFuture` — non-blocking HTTP requests.
- `HttpClient.get_async`, `post_async`, `put_async`, `delete_async` — run
  on a daemon thread, UI never blocks.
- `future.then(on_success, on_error)` callbacks.
- `future.get(timeout)` — block until result.
- `future.cancel()` — suppress callbacks.
- `future.done`, `future.cancelled`.
- Exported as `HttpFuture` from `pymobile`.

## [0.4.0] — 2026-07-31

### Added

**Input validation**

- `Validator(fields)` — declarative form/input validation.
- `validate()` returns `dict[str, list[str]]` of errors.
- `validate_or_raise()` raises `ValidationError` on first failure.
- Validators: `required`, `optional`, `email`, `length`, `min_length`,
  `max_length`, `integer`, `number`, `between`, `min`, `max`, `matches`,
  `one_of`, `regex`, `boolean`.
- Pure logic, no UI dependency. Exported as `Validator`, `ValidationError`.

**HTTP cache / offline**

- `HttpCache` — disk-backed cache for GET responses, based on `Storage`.
- `HttpClient(cache=...)` parameter.
- `get_cached(url, ttl=300)` — returns cached response if fresh, stores
  new responses, falls back to stale cache on network failure (offline
  mode).
- `Response.from_cache` flag.

**Snapshot testing**

- `snapshot_path(test_file, name)` — resolves golden file path.
- `assert_snapshot(widget_or_tree, __file__, name=...)` — first run writes
  golden file to `snapshots/`; subsequent runs compare and raise
  `AssertionError` with diff on mismatch.
- `update=True` regenerates the golden file.

**App metadata**

- `App(version=, package=)` parameters.
- `app.info` dict with `name`, `version`, `package`, `platform`.

## [0.3.0] — 2026-07-29

Ten pieces of friction reported from building a real Pomodoro app, addressed
end to end.

### Added

**Layout**

- `Grid(columns=N)` — equal-width cells for cards, galleries and menus.
  Column widths are computed across the whole grid, so two stat cards stay
  aligned whatever they contain; `Row(weight=1)` could never guarantee that.
  Supports `spacing`, `row_spacing` and `column_spacing`.
- `Expanded(child, flex=n)` and `Flexible(child, flex=n)` — Flutter-style
  shares of the free space on the main axis, tight and loose respectively.
- `Divider()` — a hairline between sections, horizontal or vertical, with an
  optional `inset` and `thickness`.
- `SafeArea(content)` — pads content by the real window insets, per edge, so
  it clears the notch, status bar and gesture bar on any device.
- `Row`/`Column` accept `cross_align` (`start`, `center`, `end`, `stretch`),
  so children no longer align differently across the axis by accident.
- `Style` gains `min_width`, `max_width`, `min_height`, `max_height` and
  `aspect_ratio`. Contradictory bounds raise instead of clipping silently.

**Reactivity**

- Widgets redraw themselves. `self.counter.text = "5"` schedules a frame; so
  does `set_text()`, and the same applies to `value`, `checked`, `visible` and
  `enabled`. `app.render()` is no longer something you can forget.
- Redraws are coalesced: a UI callback runs inside an implicit batch, and
  `app.batch()` groups updates explicitly, so six changes still draw once.
  Setting an unchanged value draws nothing.
- `App(auto_render=False)` keeps the old manual behaviour; the first missed
  redraw in that mode logs a warning.

**Events**

- `screen.on(event, handler)` subscribes for the lifetime of the screen and is
  cancelled on unmount — including through `replace()` and `reset()`. Pushing
  a screen twice no longer runs its handler twice or keeps the old instance
  alive. `app.on(..., screen=...)` does the same from outside.

**Developer tooling**

- `pymobile watch` re-renders on every save. Change detection is content-based
  rather than mtime-based, because tmpfs and overlayfs report a coarse
  timestamp and quick saves would be missed. Editing an imported helper counts
  too; a syntax error is reported without ending the session.
- `pymobile run --gui` opens an interactive Tkinter window: buttons run their
  callbacks, switches and fields feed events back through the device code
  path, navigation works and a back button appears when the stack allows it.
  Trees are patched in place, so typing does not lose focus.
- `App.current()` returns the running application.

**Internationalisation**

- `pymobile.core.i18n`: JSON catalogues per language, `{}` interpolation,
  region → language → default fallback, and plural forms with
  `zero`/`one`/`few`/`many`/`other` — Ukrainian's 1 / 2-4 / 5+ pattern works,
  not just English. Missing keys render as the key and are logged once.
- `device_language()` reads the real system locale on Android, honouring
  Android 13 per-app language overrides, and environment variables elsewhere.
- `translations.install_gettext()` for projects with an existing `.mo`
  workflow. Exported as `t`, `translations`, `Translations`.

- `pymobile run --web` serves the interactive preview over HTTP instead of Tk,
  for remote machines, containers and phones on the same network. The page is
  built from the same serialised tree, and widget ids appear as `data-wid`
  attributes for the browser inspector.
- `translations.subscribe()` notifies listeners when the language changes;
  `App` uses it to rebuild the visible screen, so `translations.use("uk")`
  updates the UI immediately.

**Build**

- `pymobile build --minimal-stdlib` drops desktop-only stdlib packages
  (~1.7 MB) and `--no-ssl` drops OpenSSL and the CA bundle (~4.7 MB).
- `--no-ssl` now warns at build time when the sources use `HttpClient`, rather
  than shipping an APK that fails with "No module named *ssl*" on device.

### Fixed

- **APK size: 21.6 MB → 16.6 MB with no flags.** The official CPython Android
  runtime ships each support library twice — `libcrypto.so` and
  `libcrypto_python.so` are byte-identical, as are the ssl and sqlite3 pairs —
  and only the `_python` names appear in the extension modules' `DT_NEEDED`
  entries. The duplicates are no longer packaged. With both new flags the same
  app is 11.7 MB.
- The `config-3.14` stdlib exclude never matched the real directory name
  (`config-3.14-aarch64-linux-android`), so 262 KB of build headers shipped in
  every APK. Excludes now match by prefix.
- `set_interval()` no longer drifts: ticks are scheduled against a fixed
  timeline instead of pausing between runs, so a callback that takes 15 ms no
  longer pushes a 30 ms timer out to 45 ms. Deadlines missed while the device
  slept are skipped rather than fired as a burst.
  `drift_correction=False` restores the old behaviour.
- Widget ids no longer shift when an unrelated widget is added. A widget
  assigned to `self` in `build()` takes the attribute name (`self.counter` →
  `"counter"`); anonymous widgets are numbered per screen and per type.
- Plural lookup preferred `one` over `other` for counts above 1 when both were
  present.
- `Style(margin=...)` was silently ignored on device. `applyStyle()` runs while
  the view is still detached, so `getLayoutParams()` returned `null` and the
  margins were dropped; they are now written where the layout params are
  created. A widget's margin **adds** to its container's `spacing`, which is
  how to give one neighbour a different gap from the rest.
- `Style(width=...)`, `Style(height=...)` and `Style(elevation=...)` were
  documented but never implemented in the renderer. Sizes accept a number in
  dp or the names `"match"`/`"fill"`/`"wrap"`; elevation gets an opaque
  background so the shadow is actually visible.
- `ScrollView` laid its children out itself, ignoring margins and flex shares.
  It now reuses the same sizing rules as `Row`/`Column` and accepts `spacing`.
- A horizontal `ScrollView` was drawn as a vertical stack in both the ASCII
  and the GUI preview.

### Changed

- `Navigator.push`/`replace`/`reset` are generic, so `app.push(Details())`
  keeps its concrete type for type checkers and editors.
- `StubBridge` accepts `language=` and implements `device_language()`.
- The prebuilt `classes.dex` is rebuilt for the new widgets and the
  `deviceLanguage` entry point.

## [0.2.0] — 2026-07-29

### Added

**Timers**

- `app.set_interval(ms, callback)` and `app.set_timeout(ms, callback)` schedule
  work on background threads on every platform, so a clock or poller no longer
  needs `threading` boilerplate. Each returns a `TimerHandle` with `.cancel()`
  and `.cancelled`; all timers are cancelled automatically by `app.stop()`.
- New `pymobile.core.scheduler` module (`Scheduler`, `TimerHandle`), exported
  from the package root.

**Desktop preview**

- `pymobile preview` renders the first screen into a picture on the laptop —
  no emulator. `--png PATH` writes a raster image (needs Pillow), `--ids`
  annotates widgets with their id.
- `pymobile.core.ui.preview.render_ascii()` draws a real 2D layout in text
  (`Row` children sit side by side, `ProgressBar` and `Switch` show their
  state); `render_png()` produces an image. Both accept a live widget or a
  `to_dict` node.
- `StubBridge.last_tree` exposes the most recently rendered tree, which the
  preview command and tests read.

**Ergonomics**

- `Button.set_text()`, mirroring `Label.set_text()`.

### Fixed

- The missing `INTERNET` build warning no longer fires for apps that never use
  the network; the validator now scans the sources for `HttpClient` /
  `app.http` usage first.
- `pymobile.__version__` is now guarded by a test against `pyproject.toml`, so
  the package version cannot silently drift from the distribution version.
- Tests that read source files resolve paths via `__file__` instead of the
  working directory, so the suite passes from any directory (previously 3–9
  failures outside the repository root).

### Changed

- Tests that need the git-ignored `libpymobile.so` prebuilt bridge are now
  skipped, not failed, in a clean source checkout — `pytest` on a fresh clone
  reports green.
- Test count: 316 → 336.

## [0.1.1] — 2026-07-29

### Fixed

- Corrected the project's PyPI badges in the README.

## [0.1.0] — 2026-07-28

First public release.

### Added

**APK build**

- Native backend: `aapt2` → `d8` → `zipalign` → `apksigner`, producing a signed
  (v1+v2+v3) APK that installs on a device.
- Embedded CPython 3.14 for arm64, using the official python.org builds.
- `pymobile setup-sdk` downloads JDK 17 and the Android SDK (~800 MB). The NDK
  is not required: a prebuilt JNI bridge ships with the package.
- Incremental cache — an unchanged rebuild finishes instantly.
- Reproducible output: identical inputs produce a byte-identical APK.

**UI**

- Native renderer: widgets become real Android views.
- Components: `Label`, `Button`, `TextInput`, `Image`, `Switch`, `ProgressBar`,
  `Spacer`.
- Containers: `Column`, `Row`, `ScrollView`, `Stack`.
- Styling: colours, fonts, padding, corner radius.
- Screens with lifecycle hooks and stack navigation; hardware back button.
- In-place view updates that preserve scroll position and keyboard focus.

**Android APIs**

- Local notifications with channels.
- Vibration: one-shot, patterns and six presets.
- Runtime permissions that wait for the user's answer.

**Networking**

- HTTP client on the standard library: GET/POST/PUT/DELETE, JSON, timeouts and
  retries with exponential backoff.
- A root certificate bundle is packaged into the APK, so HTTPS works
  immediately.

**Tooling**

- CLI: `init`, `build`, `run`, `info`, `clean`, `doctor`, `setup-sdk`.
- `python -m pymobile` as a fallback when the scripts directory is not on
  `PATH`.
- Build-time warning for permissions missing from the manifest.
- `StubBridge` for testing applications without an emulator.

**Packaging**

- Modern `pyproject.toml`, typed package (`py.typed`).
- 316 tests; `ruff` and `mypy --strict` report no issues.

### Known limitations

- Only `arm64-v8a` is supported.
- APK size is around 21 MB (interpreter and standard library).
- Minimum supported release is Android 5.0 (API 21).
