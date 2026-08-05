"""ABI-neutral launcher dex regression coverage."""

from __future__ import annotations

from pathlib import Path

from pymobile.compiler.backends.native import NativeBackend


def test_x86_64_reuses_architecture_neutral_prebuilt_dex(tmp_path: Path) -> None:
    backend = object.__new__(NativeBackend)
    backend.abi = "x86_64"
    target = backend._use_prebuilt_dex(tmp_path)
    assert target == tmp_path / "dex" / "classes.dex"
    assert target.exists()
    assert target.read_bytes()[:4] == b"dex\n"
