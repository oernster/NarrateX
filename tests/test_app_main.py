from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Callable
import runpy
import sys
import types
import pytest

import app


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks: list[Callable[[], None]] = []

    def connect(self, cb):
        self._callbacks.append(cb)

    def emit(self) -> None:
        for cb in list(self._callbacks):
            cb()


class _FakeQApplication:
    def __init__(self, argv) -> None:
        del argv
        self.aboutToQuit = _FakeSignal()
        self._exec_called = False

    def exec(self) -> int:
        self._exec_called = True
        # Simulate the app quitting immediately.
        self.aboutToQuit.emit()
        return 0


class _FakeWindow:
    def __init__(self) -> None:
        self.shown = False

    def show(self) -> None:
        self.shown = True


class _FakeUiController:
    def __init__(self, **kwargs) -> None:
        # Ensure wiring passes the essential dependencies.
        self.kwargs = kwargs


def test_main_preserve_cache_skips_rmtree(monkeypatch, tmp_path: Path) -> None:
    # Arrange: Patch Path(__file__).resolve().parent by overriding app.__file__.
    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))

    monkeypatch.setenv("NARRATEX_PRESERVE_CACHE", "1")

    rmtree_calls: list[Path] = []

    def fake_rmtree(p, ignore_errors: bool):
        del ignore_errors
        rmtree_calls.append(Path(p))

    monkeypatch.setattr(app.shutil, "rmtree", fake_rmtree)

    # Patch Qt/app wiring.
    monkeypatch.setattr(app, "QApplication", _FakeQApplication)
    monkeypatch.setattr(app, "MainWindow", _FakeWindow)
    monkeypatch.setattr(app, "UiController", _FakeUiController)

    class _FakeConfig:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                voices_dir=tmp_path / "voices",
                temp_books_dir=tmp_path / "temp_books",
            )
            self.tts_model_name = "m"
            self.default_language = "en"

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(app.Config, "from_project_root", lambda project_root: _FakeConfig())

    # Patch infra construction to avoid importing heavy deps.
    monkeypatch.setattr(app, "CalibreConverter", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "BookParser", lambda: SimpleNamespace())
    monkeypatch.setattr(
        app,
        "LocalBookRepository",
        lambda **kwargs: SimpleNamespace(load=lambda p: SimpleNamespace(title="t", normalized_text="x")),
    )
    monkeypatch.setattr(app, "FilesystemCacheRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "FilesystemVoiceProfileRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "VoiceProfileService", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "SoundDeviceAudioStreamer", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "ChunkingService", lambda **kwargs: SimpleNamespace())

    class _FakeDDS:
        def detect(self) -> str:
            return "cpu"

    monkeypatch.setattr(app, "DeviceDetectionService", _FakeDDS)

    class _FakeFactory:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def create(self):
            return SimpleNamespace(engine_name="fake")

    monkeypatch.setattr(app, "TTSEngineFactory", _FakeFactory)

    stop_calls = {"n": 0}

    class _FakeNarrationService:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def stop(self) -> None:
            stop_calls["n"] += 1

    monkeypatch.setattr(app, "NarrationService", _FakeNarrationService)

    # Act
    rc = app.main()

    # Assert
    assert rc == 0
    assert rmtree_calls == []
    assert stop_calls["n"] == 1


def test_main_clears_cache_and_registers_quit_handler(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))
    monkeypatch.delenv("NARRATEX_PRESERVE_CACHE", raising=False)

    class _FakeConfig:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                voices_dir=tmp_path / "voices",
                temp_books_dir=tmp_path / "temp_books",
            )
            self.tts_model_name = "m"
            self.default_language = "en"

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(app.Config, "from_project_root", lambda project_root: _FakeConfig())

    monkeypatch.setattr(app, "CalibreConverter", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "BookParser", lambda: SimpleNamespace())
    monkeypatch.setattr(
        app,
        "LocalBookRepository",
        lambda **kwargs: SimpleNamespace(load=lambda p: SimpleNamespace(title="t", normalized_text="x")),
    )
    monkeypatch.setattr(app, "FilesystemCacheRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "FilesystemVoiceProfileRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "VoiceProfileService", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "SoundDeviceAudioStreamer", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "ChunkingService", lambda **kwargs: SimpleNamespace())

    # Make cache dir exist so mkdir isn't the only operation.
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)

    rmtree_calls: list[Path] = []

    def fake_rmtree(p, ignore_errors: bool):
        del ignore_errors
        rmtree_calls.append(Path(p))

    monkeypatch.setattr(app.shutil, "rmtree", fake_rmtree)

    fake_qapp = _FakeQApplication([])
    monkeypatch.setattr(app, "QApplication", lambda argv: fake_qapp)
    monkeypatch.setattr(app, "MainWindow", _FakeWindow)
    monkeypatch.setattr(app, "UiController", _FakeUiController)

    class _FakeDDS:
        def detect(self) -> str:
            return "cpu"

    monkeypatch.setattr(app, "DeviceDetectionService", _FakeDDS)

    class _FakeFactory:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def create(self):
            return SimpleNamespace(engine_name="fake")

    monkeypatch.setattr(app, "TTSEngineFactory", _FakeFactory)

    stop_calls = {"n": 0}

    class _FakeNarrationService:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def stop(self) -> None:
            stop_calls["n"] += 1

    monkeypatch.setattr(app, "NarrationService", _FakeNarrationService)

    rc = app.main()

    assert rc == 0
    assert rmtree_calls, "Expected cache clearing via shutil.rmtree"
    assert stop_calls["n"] == 1, "Expected quit hook to call narration_service.stop()"


def test_main_cache_clear_failure_is_logged_and_continues(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))
    monkeypatch.delenv("NARRATEX_PRESERVE_CACHE", raising=False)

    class _FakeLogger:
        def __init__(self) -> None:
            self.exception_calls = 0

        def warning(self, *a, **k):
            return

        def debug(self, *a, **k):
            return

        def exception(self, *a, **k):
            self.exception_calls += 1

    fake_logger = _FakeLogger()
    # Patch `app.logging` without mutating the global `logging` module used by pytest.
    monkeypatch.setattr(
        app,
        "logging",
        SimpleNamespace(INFO=20, getLogger=lambda name=None: fake_logger),
    )
    monkeypatch.setattr(app, "configure_logging", lambda level=None: None)

    class _FakeConfig:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                voices_dir=tmp_path / "voices",
                temp_books_dir=tmp_path / "temp_books",
            )
            self.tts_model_name = "m"
            self.default_language = "en"

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(app.Config, "from_project_root", lambda project_root: _FakeConfig())

    # Patch `app.shutil` without mutating the global shutil module used by pytest.
    monkeypatch.setattr(
        app,
        "shutil",
        SimpleNamespace(
            rmtree=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        ),
    )

    monkeypatch.setattr(app, "QApplication", _FakeQApplication)
    monkeypatch.setattr(app, "MainWindow", _FakeWindow)
    monkeypatch.setattr(app, "UiController", _FakeUiController)

    monkeypatch.setattr(app, "CalibreConverter", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "BookParser", lambda: SimpleNamespace())
    monkeypatch.setattr(app, "LocalBookRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "FilesystemCacheRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "FilesystemVoiceProfileRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "VoiceProfileService", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "SoundDeviceAudioStreamer", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "ChunkingService", lambda **kwargs: SimpleNamespace())

    class _FakeDDS:
        def detect(self) -> str:
            return "cpu"

    monkeypatch.setattr(app, "DeviceDetectionService", _FakeDDS)
    monkeypatch.setattr(app, "TTSEngineFactory", lambda model_name: SimpleNamespace(create=lambda: SimpleNamespace(engine_name="e")))
    monkeypatch.setattr(app, "NarrationService", lambda **kwargs: SimpleNamespace(stop=lambda: None))

    rc = app.main()
    assert rc == 0
    assert fake_logger.exception_calls >= 1


def test_main_about_to_quit_connect_failure_is_logged(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))
    monkeypatch.setenv("NARRATEX_PRESERVE_CACHE", "1")

    class _FakeLogger:
        def __init__(self) -> None:
            self.exception_calls = 0

        def warning(self, *a, **k):
            return

        def debug(self, *a, **k):
            return

        def exception(self, *a, **k):
            self.exception_calls += 1

    fake_logger = _FakeLogger()
    monkeypatch.setattr(
        app,
        "logging",
        SimpleNamespace(INFO=20, getLogger=lambda name=None: fake_logger),
    )
    monkeypatch.setattr(app, "configure_logging", lambda level=None: None)

    class _FakeConfig:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                voices_dir=tmp_path / "voices",
                temp_books_dir=tmp_path / "temp_books",
            )
            self.tts_model_name = "m"
            self.default_language = "en"

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(app.Config, "from_project_root", lambda project_root: _FakeConfig())

    class _BadQuitSig:
        def emit(self) -> None:
            # If exec() triggers a quit, the signal should still be callable.
            return

        def connect(self, cb):
            del cb
            raise RuntimeError("no")

    class _Q(_FakeQApplication):
        def __init__(self, argv) -> None:
            super().__init__(argv)
            self.aboutToQuit = _BadQuitSig()

    monkeypatch.setattr(app, "QApplication", _Q)
    monkeypatch.setattr(app, "MainWindow", _FakeWindow)
    monkeypatch.setattr(app, "UiController", _FakeUiController)

    monkeypatch.setattr(app, "CalibreConverter", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "BookParser", lambda: SimpleNamespace())
    monkeypatch.setattr(app, "LocalBookRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "FilesystemCacheRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "FilesystemVoiceProfileRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "VoiceProfileService", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "SoundDeviceAudioStreamer", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "ChunkingService", lambda **kwargs: SimpleNamespace())

    class _FakeDDS:
        def detect(self) -> str:
            return "cpu"

    monkeypatch.setattr(app, "DeviceDetectionService", _FakeDDS)
    monkeypatch.setattr(app, "TTSEngineFactory", lambda model_name: SimpleNamespace(create=lambda: SimpleNamespace(engine_name="e")))
    monkeypatch.setattr(app, "NarrationService", lambda **kwargs: SimpleNamespace(stop=lambda: None))

    assert app.main() == 0
    assert fake_logger.exception_calls >= 1


def test_main_on_quit_stop_failure_is_logged(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app, "__file__", str(tmp_path / "app.py"))
    monkeypatch.setenv("NARRATEX_PRESERVE_CACHE", "1")

    class _FakeLogger:
        def __init__(self) -> None:
            self.exception_calls = 0

        def warning(self, *a, **k):
            return

        def debug(self, *a, **k):
            return

        def exception(self, *a, **k):
            self.exception_calls += 1

    fake_logger = _FakeLogger()
    monkeypatch.setattr(
        app,
        "logging",
        SimpleNamespace(INFO=20, getLogger=lambda name=None: fake_logger),
    )
    monkeypatch.setattr(app, "configure_logging", lambda level=None: None)

    class _FakeConfig:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                voices_dir=tmp_path / "voices",
                temp_books_dir=tmp_path / "temp_books",
            )
            self.tts_model_name = "m"
            self.default_language = "en"

        def ensure_directories(self) -> None:
            self.paths.cache_dir.mkdir(parents=True, exist_ok=True)
            self.paths.voices_dir.mkdir(parents=True, exist_ok=True)
            self.paths.temp_books_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(app.Config, "from_project_root", lambda project_root: _FakeConfig())

    monkeypatch.setattr(app, "QApplication", _FakeQApplication)
    monkeypatch.setattr(app, "MainWindow", _FakeWindow)
    monkeypatch.setattr(app, "UiController", _FakeUiController)

    monkeypatch.setattr(app, "CalibreConverter", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(app, "BookParser", lambda: SimpleNamespace())
    monkeypatch.setattr(app, "LocalBookRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "FilesystemCacheRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "FilesystemVoiceProfileRepository", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "VoiceProfileService", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "SoundDeviceAudioStreamer", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(app, "ChunkingService", lambda **kwargs: SimpleNamespace())

    class _FakeDDS:
        def detect(self) -> str:
            return "cpu"

    monkeypatch.setattr(app, "DeviceDetectionService", _FakeDDS)
    monkeypatch.setattr(app, "TTSEngineFactory", lambda model_name: SimpleNamespace(create=lambda: SimpleNamespace(engine_name="e")))

    def _stop_boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(app, "NarrationService", lambda **kwargs: SimpleNamespace(stop=_stop_boom))

    assert app.main() == 0
    assert fake_logger.exception_calls >= 1


def test_running_as_main_raises_system_exit(monkeypatch, tmp_path: Path) -> None:
    # Execute app.py as `__main__` under coverage to cover the guard.
    # Provide minimal fake modules to satisfy imports.
    fake_qtw = types.ModuleType("PySide6.QtWidgets")

    class _QApp:
        def __init__(self, argv) -> None:
            del argv
            self.aboutToQuit = _FakeSignal()

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
        monkeypatch.setitem(sys.modules, modname, sys.modules.get(modname) or types.ModuleType(modname))

    def _m(path: str):
        m = types.ModuleType(path)
        monkeypatch.setitem(sys.modules, path, m)
        return m

    _m("voice_reader.application.services.device_detection_service").DeviceDetectionService = (
        lambda: SimpleNamespace(detect=lambda: "cpu")
    )
    _m("voice_reader.application.services.narration_service").NarrationService = (
        lambda **kwargs: SimpleNamespace(stop=lambda: None)
    )
    _m("voice_reader.application.services.tts_engine_factory").TTSEngineFactory = (
        lambda model_name: SimpleNamespace(create=lambda: SimpleNamespace(engine_name="e"))
    )
    _m("voice_reader.application.services.voice_profile_service").VoiceProfileService = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.domain.services.chunking_service").ChunkingService = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.audio.audio_streamer").SoundDeviceAudioStreamer = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.books.converter").CalibreConverter = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.books.parser").BookParser = lambda: SimpleNamespace()
    _m("voice_reader.infrastructure.books.repository").LocalBookRepository = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.cache.filesystem_cache").FilesystemCacheRepository = (
        lambda **kwargs: SimpleNamespace()
    )
    _m("voice_reader.infrastructure.tts.voice_profile_repository").FilesystemVoiceProfileRepository = (
        lambda **kwargs: SimpleNamespace()
    )

    class _Cfg:
        def __init__(self) -> None:
            self.paths = SimpleNamespace(
                cache_dir=tmp_path / "cache",
                voices_dir=tmp_path / "voices",
                temp_books_dir=tmp_path / "temp_books",
            )
            self.tts_model_name = "m"
            self.default_language = "en"

        @staticmethod
        def from_project_root(project_root: Path):
            del project_root
            return _Cfg()

        def ensure_directories(self) -> None:
            return

    _m("voice_reader.shared.config").Config = _Cfg
    _m("voice_reader.shared.logging_utils").configure_logging = lambda level=None: None
    _m("voice_reader.ui.main_window").MainWindow = _FakeWindow
    _m("voice_reader.ui.ui_controller").UiController = _FakeUiController

    monkeypatch.setenv("NARRATEX_PRESERVE_CACHE", "1")
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("app", run_name="__main__")
    assert excinfo.value.code == 0

