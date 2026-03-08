from __future__ import annotations

from pathlib import Path

from types import SimpleNamespace

import voice_reader.shared.resources as res
import voice_reader.shared.windows_integration as win


def test_find_app_icon_path_prefers_project_root(tmp_path: Path) -> None:
    ico = tmp_path / "narratex.ico"
    ico.write_bytes(b"fake-ico")
    assert res.find_app_icon_path(project_root=tmp_path) == ico


def test_find_app_icon_path_returns_none_when_missing(tmp_path: Path, monkeypatch) -> None:
    # Ensure we don't hit the repo-root fallback based on this module's __file__.
    monkeypatch.setattr(res, "__file__", None)
    # Ensure we don't hit the sys.executable fallback.
    monkeypatch.setattr(res.sys, "executable", None)

    # Ensure cwd doesn't contain the icon so the final fallback doesn't hit.
    monkeypatch.chdir(tmp_path)
    assert res.find_app_icon_path(project_root=tmp_path) is None


def test_set_app_user_model_id_noop_when_empty() -> None:
    # Should not raise.
    win.set_app_user_model_id("")


def test_set_app_user_model_id_noop_on_non_windows(monkeypatch) -> None:
    # On non-Windows, should return early and not try to import/use ctypes.
    monkeypatch.setattr(win.os, "name", "posix")
    win.set_app_user_model_id("com.example.app")


def test_set_app_user_model_id_swallow_ctypes_errors_on_windows(monkeypatch) -> None:
    # Cover the exception handler path on Windows.
    monkeypatch.setattr(win.os, "name", "nt")

    class _FakeShell32:
        def SetCurrentProcessExplicitAppUserModelID(self, _):  # noqa: N802
            raise RuntimeError("boom")

    fake_ctypes = SimpleNamespace(windll=SimpleNamespace(shell32=_FakeShell32()))
    monkeypatch.setitem(__import__("sys").modules, "ctypes", fake_ctypes)
    win.set_app_user_model_id("com.example.app")


def test_find_app_icon_path_handles_bad_candidates(monkeypatch) -> None:
    # Force the sys.executable and __file__ candidate creation code paths to raise.
    monkeypatch.setattr(res.sys, "executable", None)
    monkeypatch.setattr(res, "__file__", None)

    class _BadPath:
        def exists(self) -> bool:
            raise OSError("nope")

        def is_file(self) -> bool:
            raise OSError("nope")

    class _BadCwd:
        def __truediv__(self, _):
            return _BadPath()

    monkeypatch.setattr(res.Path, "cwd", lambda: _BadCwd())
    assert res.find_app_icon_path(project_root=None) is None


def test_config_user_dirs_flag_covered(tmp_path: Path, monkeypatch) -> None:
    # Cover both branches: frozen/user-dirs and dev (project-root) paths.
    from voice_reader.shared.config import Config

    monkeypatch.setenv("NARRATEX_USER_DIRS", "1")
    cfg = Config.from_project_root(tmp_path)
    assert "NarrateX" in str(cfg.paths.voices_dir)

    monkeypatch.delenv("NARRATEX_USER_DIRS", raising=False)
    cfg2 = Config.from_project_root(tmp_path)
    assert cfg2.paths.voices_dir == tmp_path / "voices"

