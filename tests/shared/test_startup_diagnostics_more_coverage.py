from __future__ import annotations

import io
from pathlib import Path

from voice_reader.shared import startup_diagnostics


def test_program_base_dir_uses_argv0_when_valid(tmp_path: Path) -> None:
    argv0 = tmp_path / "NarrateX.exe"
    out = startup_diagnostics.program_base_dir(argv0=str(argv0), cwd=lambda: tmp_path)
    assert out == tmp_path


def test_program_base_dir_falls_back_to_cwd(tmp_path: Path) -> None:
    out = startup_diagnostics.program_base_dir(argv0=None, cwd=lambda: tmp_path)
    assert out == tmp_path


def test_append_startup_log_writes_line(tmp_path: Path) -> None:
    base = tmp_path

    def _open(path, mode, encoding=None, errors=None):  # noqa: ANN001
        del encoding, errors
        return open(path, mode, encoding="utf-8")

    startup_diagnostics.append_startup_log(
        base_dir=base,
        filename="NarrateX.startup.log.txt",
        text="hello",
        open_fn=_open,
    )
    assert (tmp_path / "NarrateX.startup.log.txt").read_text(encoding="utf-8").strip() == "hello"


def test_ensure_stdio_returns_existing_streams_unchanged(tmp_path: Path) -> None:
    s = io.StringIO()
    out, err = startup_diagnostics.ensure_stdio(
        base_dir=tmp_path,
        stdout=s,
        stderr=s,
        open_fn=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not open")),
    )
    assert out is s
    assert err is s


def test_preflight_imports_ok() -> None:
    rc, report = startup_diagnostics.preflight_imports(
        heavy=False,
        import_module=lambda name: object(),
        dist_version=lambda name: "0.0",
    )
    assert rc == 0
    assert report == "OK"


def test_preflight_imports_failure_includes_import_and_dist(monkeypatch) -> None:
    class _Boom(Exception):
        pass

    def _import(name: str) -> object:
        if name == "regex":
            raise _Boom("no")
        return object()

    def _ver(name: str) -> str:
        raise _Boom("missing")

    rc, report = startup_diagnostics.preflight_imports(
        heavy=False,
        import_module=_import,
        dist_version=_ver,
    )
    assert rc == 2
    assert "IMPORT regex" in report
    assert "DIST regex" in report


def test_append_startup_log_swallow_failures(tmp_path: Path) -> None:
    def _boom(*a, **k):  # noqa: ANN001
        raise OSError("no")

    # Must not raise.
    startup_diagnostics.append_startup_log(
        base_dir=tmp_path,
        filename="x.txt",
        text="x",
        open_fn=_boom,
    )


def test_preflight_imports_dist_success_branch_is_covered() -> None:
    def _import(name: str) -> object:
        if name == "regex":
            raise ImportError("missing")
        return object()

    rc, report = startup_diagnostics.preflight_imports(
        heavy=False,
        import_module=_import,
        dist_version=lambda name: "1.2.3",
    )
    assert rc == 2
    assert "DIST regex: 1.2.3" in report


def test_program_base_dir_invalid_type_falls_back(tmp_path: Path) -> None:
    out = startup_diagnostics.program_base_dir(argv0=object(), cwd=lambda: tmp_path)
    assert out == tmp_path


