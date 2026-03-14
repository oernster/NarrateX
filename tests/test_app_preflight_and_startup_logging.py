from __future__ import annotations

import builtins
import io
import types
from pathlib import Path

import pytest

import app


def _set_argv_exe(monkeypatch: pytest.MonkeyPatch, exe_path: Path) -> None:
    # app.main() uses sys.argv[0] to derive the startup log directory.
    monkeypatch.setattr(app.sys, "argv", [str(exe_path)])


def test_main_preflight_ok_creates_stdio_files_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_argv_exe(monkeypatch, tmp_path / "NarrateX.exe")

    # Ensure we cover the GUI-build edge case where stdio starts as None.
    monkeypatch.setattr(app.sys, "stdout", None)
    monkeypatch.setattr(app.sys, "stderr", None)

    monkeypatch.setenv("NARRATEX_PREFLIGHT", "1")

    # Keep the preflight deterministic and fast.
    monkeypatch.setattr(app, "configure_packaged_runtime", lambda: None)

    def fake_import_module(name: str):
        return types.ModuleType(name)

    monkeypatch.setattr(app.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(app.importlib.metadata, "version", lambda _: "0.0")

    rc = app.main()

    assert rc == 0
    assert (tmp_path / "NarrateX.runtime.out.txt").exists()
    assert (tmp_path / "NarrateX.runtime.err.txt").exists()
    assert (tmp_path / "NarrateX.startup.log.txt").exists()


def test_main_preflight_heavy_ok_exercises_heavy_imports_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_argv_exe(monkeypatch, tmp_path / "NarrateX.exe")
    monkeypatch.setenv("NARRATEX_PREFLIGHT", "true")
    monkeypatch.setenv("NARRATEX_PREFLIGHT_HEAVY", "yes")

    monkeypatch.setattr(app, "configure_packaged_runtime", lambda: None)

    imported: list[str] = []

    def fake_import_module(name: str):
        imported.append(name)
        return types.ModuleType(name)

    monkeypatch.setattr(app.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(app.importlib.metadata, "version", lambda _: "0.0")

    rc = app.main()

    assert rc == 0
    # Ensure both the light and heavy module lists are exercised.
    assert set(["site", "regex"]).issubset(imported)
    assert set(["spacy", "thinc", "torch", "transformers", "kokoro"]).issubset(imported)


def test_main_preflight_failure_returns_2_and_writes_startup_err(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_argv_exe(monkeypatch, tmp_path / "NarrateX.exe")
    monkeypatch.setenv("NARRATEX_PREFLIGHT", "1")

    monkeypatch.setattr(app, "configure_packaged_runtime", lambda: None)

    def fake_import_module(name: str):
        if name == "regex":
            raise ImportError("missing regex")
        return types.ModuleType(name)

    monkeypatch.setattr(app.importlib, "import_module", fake_import_module)
    # Also fail a dist lookup so the DIST-exception formatting branch is covered.
    def fake_version(dist: str) -> str:
        if dist == "regex":
            raise app.importlib.metadata.PackageNotFoundError(dist)
        return "0.0"

    monkeypatch.setattr(app.importlib.metadata, "version", fake_version)

    rc = app.main()

    assert rc == 2
    err_path = tmp_path / "NarrateX.startup.err.txt"
    assert err_path.exists()
    assert "IMPORT regex" in err_path.read_text(encoding="utf-8", errors="replace")


def test_startup_log_write_failure_is_swallowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cover the best-effort logging guard: failing to log must not crash."""

    _set_argv_exe(monkeypatch, tmp_path / "NarrateX.exe")
    monkeypatch.setenv("NARRATEX_PREFLIGHT", "1")

    monkeypatch.setattr(app, "configure_packaged_runtime", lambda: None)
    monkeypatch.setattr(app.importlib, "import_module", lambda name: types.ModuleType(name))
    monkeypatch.setattr(app.importlib.metadata, "version", lambda _: "0.0")

    real_open = builtins.open

    def selective_open(file, *args, **kwargs):
        if str(file).endswith("NarrateX.startup.log.txt"):
            raise OSError("disk full")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", selective_open)

    rc = app.main()
    assert rc == 0


def test_main_logs_unhandled_exception_to_startup_err_and_reraises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_argv_exe(monkeypatch, tmp_path / "NarrateX.exe")

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(app, "configure_packaged_runtime", boom)

    with pytest.raises(RuntimeError, match="boom"):
        app.main()

    err_path = tmp_path / "NarrateX.startup.err.txt"
    assert err_path.exists()
    txt = err_path.read_text(encoding="utf-8", errors="replace")
    assert "RuntimeError" in txt
    assert "boom" in txt


def test_main_reraises_system_exit_without_writing_startup_err(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cover the explicit `except SystemExit: raise` branch in app.main()."""

    _set_argv_exe(monkeypatch, tmp_path / "NarrateX.exe")

    def boom() -> None:
        raise SystemExit(123)

    monkeypatch.setattr(app, "configure_packaged_runtime", boom)

    with pytest.raises(SystemExit) as e:
        app.main()

    assert e.value.code == 123
    assert not (tmp_path / "NarrateX.startup.err.txt").exists()


def test_program_base_dir_falls_back_to_cwd_when_sys_argv_is_invalid_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Force _program_base_dir() to take the exception path (TypeError -> cwd).
    monkeypatch.setattr(app.sys, "argv", [None])

    # Avoid writing logs into the repo root when using Path.cwd().
    monkeypatch.setattr(app.Path, "cwd", classmethod(lambda cls: tmp_path))

    monkeypatch.setenv("NARRATEX_PREFLIGHT", "1")
    monkeypatch.setattr(app, "configure_packaged_runtime", lambda: None)
    monkeypatch.setattr(app.importlib, "import_module", lambda name: types.ModuleType(name))
    monkeypatch.setattr(app.importlib.metadata, "version", lambda _: "0.0")

    rc = app.main()
    assert rc == 0
    assert (tmp_path / "NarrateX.startup.log.txt").exists()


def test_ensure_stdio_open_failures_are_swallowed_but_print_failure_is_logged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cover the guarded open() failures in _ensure_stdio().

    If stdout/stderr cannot be opened, the subsequent print will fail, which
    should be captured by the outer exception handler and logged.
    """

    _set_argv_exe(monkeypatch, tmp_path / "NarrateX.exe")
    monkeypatch.setattr(app.sys, "stdout", None)
    monkeypatch.setattr(app.sys, "stderr", None)

    real_open = builtins.open

    def selective_open(file, *args, **kwargs):
        s = str(file)
        if s.endswith("NarrateX.runtime.out.txt") or s.endswith("NarrateX.runtime.err.txt"):
            raise OSError("cannot open")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", selective_open)

    with pytest.raises(Exception):
        app.main()

    assert (tmp_path / "NarrateX.startup.err.txt").exists()

