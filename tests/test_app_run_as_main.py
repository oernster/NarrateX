from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import runpy
import sys
import types

import pytest

from tests.app_main_testkit import FakeSignal, FakeUiController, FakeWindow


def test_running_as_main_raises_system_exit(monkeypatch, tmp_path: Path) -> None:
    # Execute app.py as `__main__` under coverage to cover the guard.
    # Provide minimal fake modules to satisfy imports.
    fake_qtw = types.ModuleType("PySide6.QtWidgets")

    class _QApp:
        def __init__(self, argv) -> None:
            del argv
            self.aboutToQuit = FakeSignal()

        def setWindowIcon(self, _):
            return

        def exec(self) -> int:
            return 0

        @staticmethod
        def instance():
            return None

    fake_qtw.QApplication = _QApp
    fake_pyside6 = types.ModuleType("PySide6")
    monkeypatch.setitem(sys.modules, "PySide6", fake_pyside6)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", fake_qtw)

    # Fake minimal voice_reader module tree required by top-level imports.
    for modname in [
        "voice_reader",
        "voice_reader.application",
        "voice_reader.application.services",
        "voice_reader.domain",
        "voice_reader.domain.services",
        "voice_reader.infrastructure",
        "voice_reader.infrastructure.audio",
        "voice_reader.infrastructure.books",
        "voice_reader.infrastructure.tts",
        "voice_reader.infrastructure.cache",
        "voice_reader.shared",
        "voice_reader.ui",
    ]:
        monkeypatch.setitem(
            sys.modules, modname, sys.modules.get(modname) or types.ModuleType(modname)
        )

    def _m(path: str):
        m = types.ModuleType(path)
        monkeypatch.setitem(sys.modules, path, m)
        return m

    # Device detection was only needed for torch-based engines; app is Kokoro-only now.
    _m("voice_reader.application.services.narration_service").NarrationService = (
        lambda **kwargs: SimpleNamespace(stop=lambda: None)
    )
    _m("voice_reader.infrastructure.tts.tts_engine_factory").TTSEngineFactory = (
        lambda: SimpleNamespace(create=lambda: SimpleNamespace(engine_name="e"))
    )
    _m(
        "voice_reader.application.services.voice_profile_service"
    ).VoiceProfileService = lambda **kwargs: SimpleNamespace()
    _m("voice_reader.domain.services.chunking_service").ChunkingService = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.audio.audio_streamer").SoundDeviceAudioStreamer = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.books.converter").CalibreConverter = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.books.parser").BookParser = (
        lambda: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.books.repository").LocalBookRepository = (
        lambda **kwargs: SimpleNamespace()
    )
    _m(
        "voice_reader.infrastructure.cache.filesystem_cache"
    ).FilesystemCacheRepository = lambda **kwargs: SimpleNamespace()
    _m(
        "voice_reader.infrastructure.tts.voice_profile_repository"
    ).KokoroVoiceProfileRepository = lambda **kwargs: SimpleNamespace()
    _m("voice_reader.application.services.bookmark_service").BookmarkService = (
        lambda **kwargs: SimpleNamespace()
    )
    _m(
        "voice_reader.infrastructure.bookmarks.json_bookmark_repository"
    ).JSONBookmarkRepository = lambda **kwargs: SimpleNamespace()

    class _Cfg:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                voices_dir=tmp_path / "voices",
                temp_books_dir=tmp_path / "temp_books",
                bookmarks_dir=tmp_path / "bookmarks",
            )
            self.default_language = "en"

        @staticmethod
        def from_project_root(project_root: Path):
            del project_root
            return _Cfg()

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)
            self.paths.bookmarks_dir.mkdir(parents=True, exist_ok=True)

    _m("voice_reader.shared.config").Config = _Cfg
    _m("voice_reader.shared.logging_utils").configure_logging = lambda level=None: None
    _m("voice_reader.ui.main_window").MainWindow = FakeWindow
    _m("voice_reader.ui.ui_controller").UiController = FakeUiController

    monkeypatch.setenv("NARRATEX_PRESERVE_CACHE", "1")
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("app", run_name="__main__")
    assert excinfo.value.code == 0
