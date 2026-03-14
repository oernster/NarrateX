from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import app


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, cb):
        self._callbacks.append(cb)

    def emit(self) -> None:
        for cb in list(self._callbacks):
            cb()


class _FakeQApplication:
    def __init__(self, argv) -> None:
        del argv
        self.aboutToQuit = _FakeSignal()

    def setApplicationName(self, _):
        return

    def setApplicationDisplayName(self, _):
        return

    def setDesktopFileName(self, _):
        return

    def setWindowIcon(self, _):
        return

    def exec(self) -> int:
        self.aboutToQuit.emit()
        return 0


class _FakeShell32:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def SetCurrentProcessExplicitAppUserModelID(
        self, app_id: str
    ) -> None:  # noqa: N802
        self.calls.append(app_id)


def test_main_sets_windows_appusermodelid_via_ctypes_early(
    monkeypatch, tmp_path: Path
) -> None:
    """Ensure the entrypoint sets the explicit AppUserModelID (best-effort).

    We patch `os.name` to force the Windows code path and inject a fake `ctypes`
    module to verify the call without requiring Windows.
    """

    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))

    # Force Windows path.
    monkeypatch.setattr(app.os, "name", "nt")

    fake_shell32 = _FakeShell32()
    fake_ctypes = SimpleNamespace(windll=SimpleNamespace(shell32=fake_shell32))
    monkeypatch.setitem(__import__("sys").modules, "ctypes", fake_ctypes)

    class _FakeConfig:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                temp_books_dir=tmp_path / "temp_books",
                bookmarks_dir=tmp_path / "bookmarks",
            )
            self.default_language = "en"

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)
            self.paths.bookmarks_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        app.Config, "from_project_root", lambda project_root: _FakeConfig()
    )
    monkeypatch.setattr(app, "QApplication", _FakeQApplication)
    monkeypatch.setattr(
        app,
        "MainWindow",
        lambda: SimpleNamespace(setWindowIcon=lambda *_: None, show=lambda: None),
    )
    monkeypatch.setattr(app, "UiController", lambda **kwargs: SimpleNamespace(**kwargs))

    monkeypatch.setattr(
        app, "CalibreConverter", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    monkeypatch.setattr(app, "BookParser", lambda: SimpleNamespace())
    monkeypatch.setattr(
        app, "LocalBookRepository", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    monkeypatch.setattr(
        app, "FilesystemCacheRepository", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    monkeypatch.setattr(
        app, "KokoroVoiceProfileRepository", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    monkeypatch.setattr(
        app, "VoiceProfileService", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    monkeypatch.setattr(
        app, "SoundDeviceAudioStreamer", lambda **kwargs: SimpleNamespace(**kwargs)
    )
    monkeypatch.setattr(
        app, "ChunkingService", lambda **kwargs: SimpleNamespace(**kwargs)
    )

    monkeypatch.setattr(
        app,
        "TTSEngineFactory",
        lambda: SimpleNamespace(create=lambda: SimpleNamespace(engine_name="fake")),
    )
    monkeypatch.setattr(
        app, "NarrationService", lambda **kwargs: SimpleNamespace(stop=lambda: None)
    )

    rc = app.main()
    assert rc == 0
    assert (
        fake_shell32.calls
    ), "Expected SetCurrentProcessExplicitAppUserModelID to be called"
    assert fake_shell32.calls[-1] == app.APP_APPUSERMODELID
