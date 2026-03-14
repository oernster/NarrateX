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
        self.app_display_name_calls: list[str] = []

    def setApplicationName(self, _):
        return

    def setApplicationDisplayName(self, name: str):
        self.app_display_name_calls.append(name)

    def setWindowIcon(self, _):
        return

    def exec(self) -> int:
        self.aboutToQuit.emit()
        return 0


def test_main_sets_application_display_name_when_supported(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))

    class _FakeConfig:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                temp_books_dir=tmp_path / "temp_books",
            )
            self.default_language = "en"

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(app.Config, "from_project_root", lambda project_root: _FakeConfig())
    monkeypatch.setattr(app, "QApplication", _FakeQApplication)
    monkeypatch.setattr(app, "MainWindow", lambda: SimpleNamespace(setWindowIcon=lambda *_: None, show=lambda: None))
    monkeypatch.setattr(app, "UiController", lambda **kwargs: SimpleNamespace(**kwargs))

    monkeypatch.setattr(app, "CalibreConverter", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "BookParser", lambda: SimpleNamespace())
    monkeypatch.setattr(app, "LocalBookRepository", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "FilesystemCacheRepository", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "KokoroVoiceProfileRepository", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "VoiceProfileService", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "SoundDeviceAudioStreamer", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "ChunkingService", lambda **kwargs: SimpleNamespace(**kwargs))

    monkeypatch.setattr(app, "TTSEngineFactory", lambda: SimpleNamespace(create=lambda: SimpleNamespace(engine_name="fake")))
    monkeypatch.setattr(app, "NarrationService", lambda **kwargs: SimpleNamespace(stop=lambda: None))

    monkeypatch.setattr(app, "find_app_icon_path", lambda **kwargs: None)

    fake_qapp = _FakeQApplication([])
    monkeypatch.setattr(app, "QApplication", lambda argv: fake_qapp)

    rc = app.main()
    assert rc == 0
    assert fake_qapp.app_display_name_calls, "Expected setApplicationDisplayName to be called"

