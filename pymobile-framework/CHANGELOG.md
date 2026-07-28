# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [semantic versioning](https://semver.org/).

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
