from __future__ import annotations

from types import SimpleNamespace

import voice_reader.ui._app_icon as _app_icon


class _FakeShell32:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def SetCurrentProcessExplicitAppUserModelID(
        self, app_id: str
    ) -> None:  # noqa: N802
        self.calls.append(app_id)


def test_set_windows_app_identity_calls_ctypes_on_windows(monkeypatch) -> None:
    """Ensure set_windows_app_identity sets the AppUserModelID via ctypes.

    Patches os.name on the _app_icon module only to avoid corrupting pathlib
    behaviour on Linux (Python 3.14 uses os.name to pick WindowsPath vs PosixPath).
    Injects a fake ctypes via sys.modules so no real Win32 API is called.
    """

    # Patch os.name only on the target module, not globally.
    import os as _os_module

    monkeypatch.setattr(_app_icon, "os", SimpleNamespace(name="nt"))

    fake_shell32 = _FakeShell32()
    fake_ctypes = SimpleNamespace(windll=SimpleNamespace(shell32=fake_shell32))
    monkeypatch.setitem(__import__("sys").modules, "ctypes", fake_ctypes)

    _app_icon.set_windows_app_identity()

    assert fake_shell32.calls, "Expected SetCurrentProcessExplicitAppUserModelID to be called"
    assert fake_shell32.calls[-1] == _app_icon.APP_APPUSERMODELID
    del _os_module  # silence unused-import lint; imported only for clarity above


def test_set_windows_app_identity_skips_on_non_windows(monkeypatch) -> None:
    """Ensure set_windows_app_identity is a no-op on non-Windows platforms."""

    monkeypatch.setattr(_app_icon, "os", SimpleNamespace(name="posix"))

    called: list[str] = []
    fake_ctypes = SimpleNamespace(
        windll=SimpleNamespace(
            shell32=SimpleNamespace(
                SetCurrentProcessExplicitAppUserModelID=lambda x: called.append(x)
            )
        )
    )
    monkeypatch.setitem(__import__("sys").modules, "ctypes", fake_ctypes)

    _app_icon.set_windows_app_identity()

    assert not called, "Expected no ctypes call on non-Windows"


def test_set_windows_app_identity_swallows_ctypes_exception(monkeypatch) -> None:
    """ctypes raising must be silently swallowed."""

    monkeypatch.setattr(_app_icon, "os", SimpleNamespace(name="nt"))

    def _boom(app_id: str) -> None:
        raise OSError("ctypes exploded")

    fake_ctypes = SimpleNamespace(
        windll=SimpleNamespace(
            shell32=SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=_boom)
        )
    )
    monkeypatch.setitem(__import__("sys").modules, "ctypes", fake_ctypes)

    _app_icon.set_windows_app_identity()  # must not raise


def test_exe_dir_returns_executable_parent_when_frozen(monkeypatch) -> None:
    """exe_dir() must return sys.executable's parent in frozen (PyInstaller) builds."""
    import sys as _sys
    from pathlib import Path

    fake_exe = "/some/frozen/dir/NarrateX"
    monkeypatch.setattr(_sys, "frozen", True, raising=False)
    monkeypatch.setattr(_sys, "executable", fake_exe, raising=False)

    result = _app_icon.exe_dir()

    assert result == Path(fake_exe).resolve().parent
