# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [semantic versioning](https://semver.org/).

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
  than shipping an APK that fails with "No module named _ssl" on device.

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

- The missing-`INTERNET` build warning no longer fires for apps that never use
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
