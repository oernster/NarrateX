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
        self.window_icons: list[object] = []

    def setApplicationName(self, _):
        return

    def setApplicationDisplayName(self, _):
        return

    def setWindowIcon(self, icon) -> None:
        self.window_icons.append(icon)

    def setDesktopFileName(self, _):
        return

    def exec(self) -> int:
        self.aboutToQuit.emit()
        return 0


class _FakeQIcon:
    """A fake QIcon that fails for .ico but succeeds for .png."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or ""

    def isNull(self) -> bool:
        return self._path.lower().endswith(".ico") or not self._path


def test_main_falls_back_when_ico_exists_but_qt_cant_load_it(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))

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

    # Minimal wiring.
    fake_qapp = _FakeQApplication([])
    monkeypatch.setattr(app, "QApplication", lambda argv: fake_qapp)
    monkeypatch.setattr(app, "QIcon", _FakeQIcon)
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

    # The runtime icon must be a PNG (Qt may not decode ICO in frozen builds).
    (tmp_path / "narratex_256.png").write_bytes(b"fake-png")

    # Ensure app.py finds our fake icon.
    monkeypatch.chdir(tmp_path)

    rc = app.main()
    assert rc == 0
    assert fake_qapp.window_icons, "Expected QApplication.setWindowIcon to be called"

    chosen = fake_qapp.window_icons[-1]
    assert isinstance(chosen, _FakeQIcon)
    assert chosen._path.lower().endswith(
        ".png"
    ), "Expected fallback to a PNG-based icon"
